"""Helper utilities for Video Indexer request modeling and CLI support."""

from __future__ import annotations

import argparse
import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VIDEO_INDEX_OUTPUT_SUFFIX = "_vi_output.json"


def parse_bool_arg(value: str) -> bool:
    """Parse a CLI boolean flag expressed as text."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(
        "Expected one of: true, false, yes, no, 1, 0."
    )


UPLOAD_OPTION_SPECS = (
    ("privacy", "privacy", "--privacy", str),
    ("priority", "priority", "--priority", str),
    ("description", "description", "--description", str),
    ("partition", "partition", "--partition", str),
    ("external_id", "externalId", "--external-id", str),
    ("external_url", "externalUrl", "--external-url", str),
    ("callback_url", "callbackUrl", "--callback-url", str),
    ("metadata", "metadata", "--metadata", str),
    ("language", "language", "--language", str),
    ("video_url", "videoUrl", "--video-url", str),
    ("file_name", "fileName", "--file-name", str),
    ("excluded_ai", "excludedAI", "--excluded-ai", str),
    (
        "is_searchable",
        "isSearchable",
        "--is-searchable",
        parse_bool_arg,
    ),
    (
        "indexing_preset",
        "indexingPreset",
        "--indexing-preset",
        str,
    ),
    (
        "streaming_preset",
        "streamingPreset",
        "--streaming-preset",
        str,
    ),
    (
        "linguistic_model_id",
        "linguisticModelId",
        "--linguistic-model-id",
        str,
    ),
    ("person_model_id", "personModelId", "--person-model-id", str),
    (
        "send_success_email",
        "sendSuccessEmail",
        "--send-success-email",
        parse_bool_arg,
    ),
    (
        "brands_categories",
        "brandsCategories",
        "--brands-categories",
        str,
    ),
    (
        "custom_languages",
        "customLanguages",
        "--custom-languages",
        str,
    ),
    ("logo_group_id", "logoGroupId", "--logo-group-id", str),
    (
        "use_managed_identity_to_download_video",
        "useManagedIdentityToDownloadVideo",
        "--use-managed-identity-to-download-video",
        parse_bool_arg,
    ),
    (
        "prevent_duplicates",
        "preventDuplicates",
        "--prevent-duplicates",
        parse_bool_arg,
    ),
    ("retention_period", "retentionPeriod", "--retention-period", int),
    (
        "punctuation_mode",
        "punctuationMode",
        "--punctuation-mode",
        str,
    ),
    (
        "profanity_filter_mode",
        "profanityFilterMode",
        "--profanity-filter-mode",
        str,
    ),
)

UPLOAD_QUERY_PARAM_MAP = {
    field_name: query_name
    for field_name, query_name, _flag, _value_type in UPLOAD_OPTION_SPECS
}


VIDEO_INDEX_OPTION_SPECS = (
    ("language", "language", "--language", str),
    ("re_translate", "reTranslate", "--re-translate", parse_bool_arg),
    (
        "include_streaming_urls",
        "includeStreamingUrls",
        "--include-streaming-urls",
        parse_bool_arg,
    ),
    (
        "included_insights",
        "includedInsights",
        "--included-insights",
        str,
    ),
    (
        "excluded_insights",
        "excludedInsights",
        "--excluded-insights",
        str,
    ),
    (
        "include_summarized_insights",
        "includeSummarizedInsights",
        "--include-summarized-insights",
        parse_bool_arg,
    ),
)

VIDEO_INDEX_QUERY_PARAM_MAP = {
    field_name: query_name
    for field_name, query_name, _flag, _value_type in VIDEO_INDEX_OPTION_SPECS
}


def serialize_query_value(value: Any) -> str:
    """Convert a Python value into the expected query-string format."""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode a JWT payload without signature validation for diagnostics."""
    token_parts = token.split(".")
    if len(token_parts) < 2:
        return None

    payload_segment = token_parts[1]
    payload_segment += "=" * (-len(payload_segment) % 4)

    try:
        decoded_payload = base64.urlsafe_b64decode(
            payload_segment.encode("ascii")
        ).decode("utf-8")
        parsed_payload = json.loads(decoded_payload)
    except (OSError, UnicodeDecodeError, ValueError):
        return None

    if isinstance(parsed_payload, dict):
        return parsed_payload
    return None


def peek_access_token_permission(token: str) -> str | None:
    """Read the unverified permission claim from a Video Indexer token."""
    payload = decode_jwt_payload(token)
    permission = payload.get("Permission") if payload else None
    return str(permission) if permission else None


@dataclass(frozen=True)
class VideoUploadRequest:
    """Typed request model for uploading a video to Video Indexer."""

    name: str
    file_path: Path | None = None
    privacy: str | None = None
    priority: str | None = None
    description: str | None = None
    partition: str | None = None
    external_id: str | None = None
    external_url: str | None = None
    callback_url: str | None = None
    metadata: str | None = None
    language: str | None = None
    video_url: str | None = None
    file_name: str | None = None
    excluded_ai: str | None = None
    is_searchable: bool | None = None
    indexing_preset: str | None = None
    streaming_preset: str | None = None
    linguistic_model_id: str | None = None
    person_model_id: str | None = None
    send_success_email: bool | None = None
    brands_categories: str | None = None
    custom_languages: str | None = None
    logo_group_id: str | None = None
    use_managed_identity_to_download_video: bool | None = None
    prevent_duplicates: bool | None = None
    retention_period: int | None = None
    punctuation_mode: str | None = None
    profanity_filter_mode: str | None = None

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValueError("Video upload name cannot be empty.")
        object.__setattr__(self, "name", normalized_name)

        has_file_path = self.file_path is not None
        has_video_url = bool(self.video_url)
        if has_file_path == has_video_url:
            raise ValueError(
                "Provide exactly one of file_path or video_url for upload."
            )

    def to_query_params(self, access_token: str) -> dict[str, str]:
        """Serialize the upload request into query-string parameters."""
        params = {
            "name": self.name,
            "accessToken": access_token,
        }

        for field_name, query_name in UPLOAD_QUERY_PARAM_MAP.items():
            value = getattr(self, field_name)
            if value is None:
                continue
            params[query_name] = serialize_query_value(value)

        return params


@dataclass(frozen=True)
class VideoIndexRequest:
    """Typed request model for retrieving the full Video Indexer JSON."""

    video_id: str
    language: str | None = None
    re_translate: bool | None = None
    include_streaming_urls: bool | None = None
    included_insights: str | None = None
    excluded_insights: str | None = None
    include_summarized_insights: bool | None = None

    def __post_init__(self) -> None:
        normalized_video_id = self.video_id.strip()
        if not normalized_video_id:
            raise ValueError("Video id cannot be empty.")
        object.__setattr__(self, "video_id", normalized_video_id)

    def to_query_params(self, access_token: str) -> dict[str, str]:
        """Serialize the index request into query-string parameters."""
        params = {"accessToken": access_token}

        for field_name, query_name in VIDEO_INDEX_QUERY_PARAM_MAP.items():
            value = getattr(self, field_name)
            if value is None:
                continue
            params[query_name] = serialize_query_value(value)

        return params


@dataclass(frozen=True)
class VideoStatusSnapshot:
    """Compact status view extracted from a Video Indexer video response."""

    video_id: str
    name: str | None
    state: str | None
    processing_progress: str | None
    failure_message: str | None
    raw_response: dict[str, Any]

    @classmethod
    def from_api_response(
        cls,
        payload: dict[str, Any],
    ) -> "VideoStatusSnapshot":
        primary_video = extract_primary_video_payload(payload)
        video_id = str(payload.get("id") or primary_video.get("id") or "")

        return cls(
            video_id=video_id,
            name=_coerce_optional_text(
                payload.get("name") or primary_video.get("name")
            ),
            state=_coerce_optional_text(
                payload.get("state") or primary_video.get("state")
            ),
            processing_progress=_coerce_optional_text(
                payload.get("processingProgress")
                or primary_video.get("processingProgress")
            ),
            failure_message=_coerce_optional_text(
                payload.get("failureMessage")
                or primary_video.get("failureMessage")
            ),
            raw_response=payload,
        )

    @property
    def processing_progress_percent(self) -> int | None:
        """Return the numeric processing percentage when available."""
        return parse_processing_progress_percent(self.processing_progress)

    @property
    def is_success(self) -> bool:
        """True when Video Indexer reports indexing is complete."""
        return (self.state or "").casefold() == "processed"

    @property
    def is_failure(self) -> bool:
        """True when Video Indexer reports a terminal failure state."""
        return (self.state or "").casefold() in {"failed", "error"}

    @property
    def is_complete(self) -> bool:
        """True when indexing is complete or progress reached 100 percent."""
        return self.is_success or self.processing_progress_percent == 100

    def to_dict(self) -> dict[str, Any]:
        """Serialize the compact status snapshot for CLI output."""
        return {
            "videoId": self.video_id,
            "name": self.name,
            "state": self.state,
            "processingProgress": self.processing_progress,
            "processingProgressPercent": self.processing_progress_percent,
            "failureMessage": self.failure_message,
            "isComplete": self.is_complete,
        }


def _coerce_optional_text(value: Any) -> str | None:
    """Convert a populated value to text while preserving None."""
    if value in (None, ""):
        return None
    return str(value)


def extract_primary_video_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the first nested video payload when the response contains one."""
    nested_videos = payload.get("videos")
    if isinstance(nested_videos, list) and nested_videos:
        first_video = nested_videos[0]
        if isinstance(first_video, dict):
            return first_video
    return {}


def parse_processing_progress_percent(
    processing_progress: str | None,
) -> int | None:
    """Parse values such as '40%' into an integer percentage."""
    if not processing_progress:
        return None

    match = re.search(r"(\d+)", processing_progress)
    if not match:
        return None

    return int(match.group(1))


def normalize_output_video_name(video_name: str) -> str:
    """Normalize a video name for canonical `video_index/` filenames."""
    normalized_name = re.sub(r"[^0-9A-Za-z]+", "_", video_name.strip())
    normalized_name = re.sub(r"_+", "_", normalized_name).strip("_")
    if not normalized_name:
        raise ValueError("Output video name cannot be empty.")
    return normalized_name


def build_video_index_output_path(
    video_name: str,
    video_index_dir: str | Path,
) -> Path:
    """Build the canonical Video Indexer output path for a video."""
    normalized_video_name = normalize_output_video_name(video_name)
    return Path(video_index_dir) / (
        f"{normalized_video_name}{VIDEO_INDEX_OUTPUT_SUFFIX}"
    )


def save_json_output(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Persist JSON output to disk using stable formatting."""
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return resolved_output_path


def add_upload_parser_arguments(
    upload_parser: argparse.ArgumentParser,
) -> None:
    """Register the supported upload CLI arguments."""
    upload_parser.add_argument(
        "--file",
        dest="file_path",
        type=Path,
        help="Path to a local video file to upload.",
    )
    upload_parser.add_argument(
        "--name",
        help="Video name in Video Indexer. Defaults to the local file stem.",
    )
    upload_parser.add_argument(
        "--access-token",
        help=(
            "Optional contributor-scoped access token. If omitted, the client "
            "requests one automatically."
        ),
    )

    for field_name, query_name, flag, value_type in UPLOAD_OPTION_SPECS:
        upload_parser.add_argument(
            flag,
            dest=field_name,
            type=value_type,
            help=f"Upload query parameter '{query_name}'.",
        )


def add_video_id_argument(parser: argparse.ArgumentParser) -> None:
    """Register the common `--video-id` CLI argument."""
    parser.add_argument(
        "--video-id",
        required=True,
        help="Video Indexer video id returned by the upload operation.",
    )


def add_reader_access_token_argument(
    parser: argparse.ArgumentParser,
) -> None:
    """Register an optional reader token override for read operations."""
    parser.add_argument(
        "--access-token",
        help=(
            "Optional reader-scoped access token for read operations. If "
            "omitted, the client requests one automatically."
        ),
    )


def add_video_index_request_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register the supported query parameters for `GET .../Index`."""
    for field_name, query_name, flag, value_type in VIDEO_INDEX_OPTION_SPECS:
        parser.add_argument(
            flag,
            dest=field_name,
            type=value_type,
            help=f"Index query parameter '{query_name}'.",
        )


def add_video_index_output_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register CLI arguments that control where the VI JSON is saved."""
    parser.add_argument(
        "--video-index-dir",
        default="video_index",
        help="Directory where the downloaded VI JSON should be saved.",
    )
    parser.add_argument(
        "--output-video-name",
        help=(
            "Optional output name for the saved file. Use this when the "
            "uploaded display name differs from the pipeline's local file "
            "stem."
        ),
    )


def build_upload_request_from_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> VideoUploadRequest:
    """Construct a typed upload request from parsed CLI arguments."""
    file_path = args.file_path.expanduser() if args.file_path else None
    name = args.name or (file_path.stem if file_path else None)

    if not name:
        parser.error("--name is required when uploading from --video-url.")

    upload_kwargs = {
        field_name: getattr(args, field_name)
        for field_name, _query_name, _flag, _value_type in UPLOAD_OPTION_SPECS
    }

    try:
        return VideoUploadRequest(
            name=name,
            file_path=file_path,
            **upload_kwargs,
        )
    except ValueError as exc:
        parser.error(str(exc))

    raise AssertionError("Argument parser error should have exited already.")


def build_video_index_request_from_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> VideoIndexRequest:
    """Construct a typed index request from parsed CLI arguments."""
    index_kwargs = {
        field_name: getattr(args, field_name)
        for (
            field_name,
            _query_name,
            _flag,
            _value_type,
        ) in VIDEO_INDEX_OPTION_SPECS
    }

    try:
        return VideoIndexRequest(
            video_id=args.video_id,
            **index_kwargs,
        )
    except ValueError as exc:
        parser.error(str(exc))

    raise AssertionError("Argument parser error should have exited already.")


def resolve_output_video_name(
    args: argparse.Namespace,
    status_snapshot: VideoStatusSnapshot,
) -> str:
    """Resolve the canonical output name for a saved VI JSON file."""
    candidate_name = (
        args.output_video_name
        or status_snapshot.name
        or status_snapshot.video_id
    )
    return normalize_output_video_name(candidate_name)
