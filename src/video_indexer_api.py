"""
video_indexer_api.py

Reusable Azure Video Indexer REST client.

The client supports account access token retrieval and local file uploads. The
request pipeline and account-scoped path builders are reusable for future
polling and index download operations.

Usage:
    .venv/bin/python src/video_indexer_api.py get-account-access-token
    .venv/bin/python src/video_indexer_api.py get-account-access-token \
        --allow-edit --print-token
    .venv/bin/python src/video_indexer_api.py upload-video \
        --file video/flight_simulator.mp4
    .venv/bin/python src/video_indexer_api.py get-video-status \
        --video-id swo33fsr52
    .venv/bin/python src/video_indexer_api.py wait-for-video-index \
        --video-id swo33fsr52 \
        --output-video-name flight_simulator
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable

try:
    import requests
    from dotenv import load_dotenv
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python dependencies for Azure Video Indexer API calls. "
        "Use '.venv/bin/python' or install requests and python-dotenv first."
    ) from exc

if __package__:
    from .helper.video_indexer_helpers import (
        VideoIndexRequest,
        VideoStatusSnapshot,
        VideoUploadRequest,
        add_reader_access_token_argument,
        add_upload_parser_arguments,
        add_video_id_argument,
        add_video_index_output_arguments,
        add_video_index_request_arguments,
        build_video_index_output_path,
        build_upload_request_from_args,
        build_video_index_request_from_args,
        peek_access_token_permission,
        resolve_output_video_name,
        save_json_output,
    )
else:
    from helper.video_indexer_helpers import (
        VideoIndexRequest,
        VideoStatusSnapshot,
        VideoUploadRequest,
        add_reader_access_token_argument,
        add_upload_parser_arguments,
        add_video_id_argument,
        add_video_index_output_arguments,
        add_video_index_request_arguments,
        build_video_index_output_path,
        build_upload_request_from_args,
        build_video_index_request_from_args,
        peek_access_token_permission,
        resolve_output_video_name,
        save_json_output,
    )


SRC_DIR = Path(__file__).resolve().parent

load_dotenv(SRC_DIR / ".env")


DEFAULT_API_BASE_URL = "https://api.videoindexer.ai"
UPLOAD_RESPONSE_STATUSES = (200, 201, 202)


class VideoIndexerApiError(RuntimeError):
    """Raised when a Video Indexer REST call fails."""


@dataclass(frozen=True)
class VideoIndexerConfig:
    """Configuration for Azure Video Indexer REST calls."""

    location: str
    account_id: str
    subscription_key: str
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout_seconds: int = 300

    @classmethod
    def from_env(cls) -> "VideoIndexerConfig":
        """Load the Video Indexer configuration from environment variables."""
        required_env_vars = [
            "AZURE_VIDEO_INDEXER_LOCATION",
            "AZURE_VIDEO_INDEXER_ACCOUNT_ID",
            "AZURE_VIDEO_INDEXER_SUBSCRIPTION_KEY",
        ]
        missing = [name for name in required_env_vars if not os.getenv(name)]
        if missing:
            raise SystemExit(
                "ERROR: Missing Video Indexer env values: "
                f"{', '.join(missing)}"
            )

        timeout_seconds = os.getenv(
            "AZURE_VIDEO_INDEXER_TIMEOUT_SECONDS",
            "300",
        )
        try:
            parsed_timeout = int(timeout_seconds)
        except ValueError as exc:
            raise SystemExit(
                "ERROR: AZURE_VIDEO_INDEXER_TIMEOUT_SECONDS "
                "must be an integer."
            ) from exc

        return cls(
            location=os.environ["AZURE_VIDEO_INDEXER_LOCATION"],
            account_id=os.environ["AZURE_VIDEO_INDEXER_ACCOUNT_ID"],
            subscription_key=os.environ[
                "AZURE_VIDEO_INDEXER_SUBSCRIPTION_KEY"
            ],
            api_base_url=os.getenv(
                "AZURE_VIDEO_INDEXER_API_BASE_URL",
                DEFAULT_API_BASE_URL,
            ),
            timeout_seconds=parsed_timeout,
        )


class VideoIndexerApiClient:
    """Thin, extendable wrapper around the Azure Video Indexer REST API."""

    def __init__(
        self,
        config: VideoIndexerConfig,
        session: requests.Session | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()

    def _build_url(self, path: str) -> str:
        normalized_base_url = self._config.api_base_url.rstrip("/")
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{normalized_base_url}{normalized_path}"

    def _auth_path(self, *segments: str) -> str:
        joined_segments = "/".join(
            str(segment).strip("/") for segment in segments
        )
        return (
            f"/Auth/{self._config.location}/Accounts/"
            f"{self._config.account_id}/{joined_segments}"
        )

    def _account_path(self, *segments: str) -> str:
        joined_segments = "/".join(
            str(segment).strip("/") for segment in segments
        )
        return (
            f"/{self._config.location}/Accounts/"
            f"{self._config.account_id}/{joined_segments}"
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        files: Any = None,
        expected_status: tuple[int, ...] = (200,),
        include_subscription_key: bool = False,
    ) -> requests.Response:
        request_headers = dict(headers or {})
        if include_subscription_key:
            request_headers["Ocp-Apim-Subscription-Key"] = (
                self._config.subscription_key
            )

        try:
            response = self._session.request(
                method=method,
                url=self._build_url(path),
                headers=request_headers,
                params=params,
                data=data,
                files=files,
                timeout=self._config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise VideoIndexerApiError(
                f"{method} {path} request failed: {exc}"
            ) from exc

        if response.status_code not in expected_status:
            snippet = response.text.strip().replace("\n", " ")[:500]
            raise VideoIndexerApiError(
                f"{method} {path} failed with status {response.status_code}: "
                f"{snippet}"
            )

        return response

    def request_text(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> str:
        """Run a REST call and return the response body as text."""
        return self._request(method, path, **kwargs).text

    def request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any]:
        """Run a REST call and return the response body as JSON."""
        return self._request(method, path, **kwargs).json()

    @staticmethod
    def _expect_json_object(
        response_body: dict[str, Any] | list[Any],
        operation_name: str,
    ) -> dict[str, Any]:
        """Validate that a REST call returned a JSON object payload."""
        if isinstance(response_body, dict):
            return response_body

        raise VideoIndexerApiError(
            f"{operation_name} returned a JSON array instead of an object."
        )

    @staticmethod
    def _extract_video_list_items(
        response_body: dict[str, Any] | list[Any],
        operation_name: str,
    ) -> list[dict[str, Any]]:
        """Normalize the list-videos payload into a list of objects."""
        if isinstance(response_body, list):
            return [item for item in response_body if isinstance(item, dict)]

        payload = VideoIndexerApiClient._expect_json_object(
            response_body,
            operation_name,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise VideoIndexerApiError(
                f"{operation_name} response did not contain a 'results' "
                "array."
            )

        return [item for item in results if isinstance(item, dict)]

    @staticmethod
    def _find_video_in_list_payload(
        payload: dict[str, Any] | list[Any],
        video_id: str,
    ) -> dict[str, Any] | None:
        """Find a video entry in a list-videos payload by its id."""
        for item in VideoIndexerApiClient._extract_video_list_items(
            payload,
            "List videos",
        ):
            if str(item.get("id") or "") == video_id:
                return item

        return None

    def list_videos(
        self,
        *,
        access_token: str | None = None,
    ) -> list[VideoStatusSnapshot]:
        """List videos available in the configured Video Indexer account."""
        effective_access_token = (
            access_token or self.get_account_access_token()
        )
        response_body = self.request_json(
            "GET",
            self._account_path("Videos"),
            params={"accessToken": effective_access_token},
        )

        snapshots = [
            VideoStatusSnapshot.from_api_response(item)
            for item in self._extract_video_list_items(
                response_body,
                "List videos",
            )
        ]
        snapshots.sort(
            key=lambda snapshot: (
                (snapshot.name or "").casefold(),
                snapshot.video_id,
            )
        )
        return snapshots

    def get_account_access_token(self, *, allow_edit: bool = False) -> str:
        """Get a Video Indexer account access token."""
        params = {"allowEdit": "true"} if allow_edit else None
        token = self.request_text(
            "GET",
            self._auth_path("AccessToken"),
            params=params,
            include_subscription_key=True,
        )
        return token.strip().strip('"')

    def upload_video(
        self,
        request: VideoUploadRequest,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Upload a local or remote video to Video Indexer."""
        effective_access_token = access_token or self.get_account_access_token(
            allow_edit=True
        )

        if (
            access_token
            and peek_access_token_permission(access_token) == "Reader"
        ):
            raise VideoIndexerApiError(
                "The supplied access token is reader-scoped. Upload requires "
                "a contributor token. Re-run 'get-account-access-token "
                "--allow-edit' or omit '--access-token' to let the client "
                "request a write-scoped token automatically."
            )

        params = request.to_query_params(effective_access_token)
        upload_path = self._account_path("Videos")

        if request.file_path is None:
            response_body = self.request_json(
                "POST",
                upload_path,
                params=params,
                expected_status=UPLOAD_RESPONSE_STATUSES,
            )
        else:
            resolved_file_path = request.file_path.expanduser()
            if not resolved_file_path.is_file():
                raise VideoIndexerApiError(
                    f"Video file not found: {resolved_file_path}"
                )

            file_name = request.file_name or resolved_file_path.name
            content_type = (
                mimetypes.guess_type(resolved_file_path.name)[0]
                or "application/octet-stream"
            )

            with resolved_file_path.open("rb") as file_stream:
                response_body = self.request_json(
                    "POST",
                    upload_path,
                    params=params,
                    files={
                        "file": (file_name, file_stream, content_type),
                    },
                    expected_status=UPLOAD_RESPONSE_STATUSES,
                )

        return self._expect_json_object(response_body, "Upload video")

    def get_video_status(
        self,
        video_id: str,
        *,
        access_token: str | None = None,
    ) -> VideoStatusSnapshot:
        """Get the current indexing state and progress for a video id."""
        effective_access_token = (
            access_token or self.get_account_access_token()
        )
        try:
            response_body = self.request_json(
                "GET",
                self._account_path("Videos", video_id),
                params={"accessToken": effective_access_token},
            )
        except VideoIndexerApiError as exc:
            if "status 404" not in str(exc):
                raise

            list_response = self.request_json(
                "GET",
                self._account_path("Videos"),
                params={"accessToken": effective_access_token},
            )
            list_payload = self._expect_json_object(
                list_response,
                "List videos",
            )
            listed_video = self._find_video_in_list_payload(
                list_payload,
                video_id,
            )
            if listed_video is None:
                raise VideoIndexerApiError(
                    f"Video {video_id} was not found in the account video "
                    "list."
                ) from exc

            return VideoStatusSnapshot.from_api_response(listed_video)

        payload = self._expect_json_object(response_body, "Get video status")
        return VideoStatusSnapshot.from_api_response(payload)

    def get_video_index(
        self,
        request: VideoIndexRequest,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Get the full Video Indexer JSON for a processed video."""
        effective_access_token = (
            access_token or self.get_account_access_token()
        )
        response_body = self.request_json(
            "GET",
            self._account_path("Videos", request.video_id, "Index"),
            params=request.to_query_params(effective_access_token),
        )
        return self._expect_json_object(response_body, "Get video index")

    def wait_for_video_index_result(
        self,
        request: VideoIndexRequest,
        *,
        access_token: str | None = None,
        poll_interval_seconds: int = 15,
        timeout_seconds: int = 3600,
        on_poll: Callable[[VideoStatusSnapshot], None] | None = None,
    ) -> tuple[VideoStatusSnapshot, dict[str, Any]]:
        """Poll until indexing finishes, then return the final index JSON."""
        if poll_interval_seconds < 1:
            raise VideoIndexerApiError(
                "poll_interval_seconds must be at least 1 second."
            )
        if timeout_seconds < 1:
            raise VideoIndexerApiError(
                "timeout_seconds must be at least 1 second."
            )

        deadline = monotonic() + timeout_seconds
        last_status: VideoStatusSnapshot | None = None

        while True:
            last_status = self.get_video_status(
                request.video_id,
                access_token=access_token,
            )
            if on_poll is not None:
                on_poll(last_status)

            if last_status.is_failure:
                failure_message = last_status.failure_message or (
                    "No failure message returned."
                )
                raise VideoIndexerApiError(
                    f"Video {request.video_id} failed indexing: "
                    f"{failure_message}"
                )

            if last_status.is_complete:
                try:
                    index_payload = self.get_video_index(
                        request,
                        access_token=access_token,
                    )
                except VideoIndexerApiError as exc:
                    if "status 404" not in str(exc) or monotonic() >= deadline:
                        raise
                else:
                    return last_status, index_payload

            if monotonic() >= deadline:
                final_state = last_status.state if last_status else "Unknown"
                final_progress = (
                    last_status.processing_progress if last_status else None
                ) or "unknown"
                raise VideoIndexerApiError(
                    f"Timed out after {timeout_seconds} seconds waiting for "
                    f"video {request.video_id} to finish indexing. Last "
                    f"known state: {final_state}, progress: {final_progress}."
                )

            sleep(poll_interval_seconds)


def save_video_index_payload(
    args: argparse.Namespace,
    status_snapshot: VideoStatusSnapshot,
    index_payload: dict[str, Any],
) -> Path:
    """Save the downloaded Video Indexer JSON using the repo convention."""
    output_video_name = resolve_output_video_name(args, status_snapshot)
    output_path = build_video_index_output_path(
        output_video_name,
        args.video_index_dir,
    )
    return save_json_output(index_payload, output_path)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for Video Indexer API operations."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_parser = subparsers.add_parser("get-account-access-token")
    token_parser.add_argument(
        "--allow-edit",
        action="store_true",
        help=(
            "Request a contributor-scoped token for write operations such as "
            "video upload."
        ),
    )
    token_parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the raw token to stdout instead of a safe summary.",
    )

    upload_parser = subparsers.add_parser("upload-video")
    add_upload_parser_arguments(upload_parser)

    status_parser = subparsers.add_parser("get-video-status")
    add_video_id_argument(status_parser)
    add_reader_access_token_argument(status_parser)

    download_parser = subparsers.add_parser("download-video-index")
    add_video_id_argument(download_parser)
    add_reader_access_token_argument(download_parser)
    add_video_index_request_arguments(download_parser)
    add_video_index_output_arguments(download_parser)

    wait_parser = subparsers.add_parser("wait-for-video-index")
    add_video_id_argument(wait_parser)
    add_reader_access_token_argument(wait_parser)
    add_video_index_request_arguments(wait_parser)
    add_video_index_output_arguments(wait_parser)
    wait_parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=15,
        help="Seconds between status checks while waiting for indexing.",
    )
    wait_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Maximum time to wait for indexing before failing.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for Video Indexer API operations."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config = VideoIndexerConfig.from_env()
    client = VideoIndexerApiClient(config)

    try:
        if args.command == "get-account-access-token":
            token = client.get_account_access_token(
                allow_edit=args.allow_edit,
            )
            if args.print_token:
                print(token)
            else:
                response_payload = {
                    "operation": args.command,
                    "location": config.location,
                    "accountId": config.account_id,
                    "tokenLength": len(token),
                }
                permission = peek_access_token_permission(token)
                if permission:
                    response_payload["permission"] = permission

                print(json.dumps(response_payload, indent=2))
            return 0

        if args.command == "upload-video":
            upload_request = build_upload_request_from_args(args, parser)
            upload_response = client.upload_video(
                upload_request,
                access_token=args.access_token,
            )
            print(json.dumps(upload_response, indent=2))
            return 0

        if args.command == "get-video-status":
            status_snapshot = client.get_video_status(
                args.video_id,
                access_token=args.access_token,
            )
            print(json.dumps(status_snapshot.to_dict(), indent=2))
            return 0

        if args.command == "download-video-index":
            index_request = build_video_index_request_from_args(args, parser)
            status_snapshot = client.get_video_status(
                index_request.video_id,
                access_token=args.access_token,
            )
            index_payload = client.get_video_index(
                index_request,
                access_token=args.access_token,
            )
            output_path = save_video_index_payload(
                args,
                status_snapshot,
                index_payload,
            )
            print(
                json.dumps(
                    {
                        "operation": args.command,
                        **status_snapshot.to_dict(),
                        "outputPath": str(output_path),
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "wait-for-video-index":
            index_request = build_video_index_request_from_args(args, parser)

            last_reported_state: tuple[str | None, str | None] | None = None

            def report_progress(status_snapshot: VideoStatusSnapshot) -> None:
                nonlocal last_reported_state
                current_state = (
                    status_snapshot.state,
                    status_snapshot.processing_progress,
                )
                if current_state == last_reported_state:
                    return
                last_reported_state = current_state

                printable_state = status_snapshot.state or "Unknown"
                printable_progress = (
                    status_snapshot.processing_progress or "unknown"
                )
                print(
                    f"Polling {status_snapshot.video_id}: "
                    f"state={printable_state}, "
                    f"progress={printable_progress}"
                )

            status_snapshot, index_payload = (
                client.wait_for_video_index_result(
                    index_request,
                    access_token=args.access_token,
                    poll_interval_seconds=args.poll_interval_seconds,
                    timeout_seconds=args.timeout_seconds,
                    on_poll=report_progress,
                )
            )
            output_path = save_video_index_payload(
                args,
                status_snapshot,
                index_payload,
            )
            print(
                json.dumps(
                    {
                        "operation": args.command,
                        **status_snapshot.to_dict(),
                        "outputPath": str(output_path),
                    },
                    indent=2,
                )
            )
            return 0
    except VideoIndexerApiError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    parser.error(f"Unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
