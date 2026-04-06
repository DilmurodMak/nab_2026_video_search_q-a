"""Run one local video through Video Indexer end to end."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from time import sleep

if __package__:
    from .helper.video_indexer_helpers import (
        VideoIndexRequest,
        VideoUploadRequest,
        build_video_index_output_path,
        save_json_output,
    )
    from .video_indexer_api import (
        VideoIndexerApiClient,
        VideoIndexerApiError,
        VideoIndexerConfig,
    )
else:
    from helper.video_indexer_helpers import (
        VideoIndexRequest,
        VideoUploadRequest,
        build_video_index_output_path,
        save_json_output,
    )
    from video_indexer_api import (
        VideoIndexerApiClient,
        VideoIndexerApiError,
        VideoIndexerConfig,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the end-to-end Video Indexer runner."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video-file",
        type=Path,
        required=True,
        help="Path to the local video file under video/ to process.",
    )
    parser.add_argument(
        "--output-video-name",
        help=(
            "Output name used for the saved file in video_index/. Defaults to "
            "the local file stem."
        ),
    )
    parser.add_argument(
        "--video-indexer-name",
        help=(
            "Display name used in Video Indexer. Defaults to a unique name "
            "derived from the output name."
        ),
    )
    parser.add_argument(
        "--video-index-dir",
        default="video_index",
        help="Directory where the raw VI JSON should be saved.",
    )
    parser.add_argument(
        "--description",
        help="Optional Video Indexer description for the uploaded video.",
    )
    parser.add_argument(
        "--language",
        help="Optional source language for the uploaded video.",
    )
    parser.add_argument(
        "--privacy",
        help=(
            "Optional Video Indexer privacy mode. Defaults to Public when "
            "omitted."
        ),
    )
    parser.add_argument(
        "--indexing-preset",
        help="Optional Video Indexer indexing preset.",
    )
    parser.add_argument(
        "--streaming-preset",
        help="Optional Video Indexer streaming preset.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=15,
        help="Seconds between status checks while indexing is in progress.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Maximum time to wait for indexing to complete.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        help=(
            "Optional per-request timeout override for the underlying Video "
            "Indexer client."
        ),
    )
    parser.add_argument(
        "--upload-attempts",
        type=int,
        default=2,
        help="Number of upload attempts before the script gives up.",
    )
    parser.add_argument(
        "--upload-retry-delay-seconds",
        type=int,
        default=10,
        help="Seconds to wait before retrying a failed upload attempt.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the destination file in video_index/ if it exists.",
    )
    return parser


def build_default_video_indexer_name(output_video_name: str) -> str:
    """Use the output video name as the default Video Indexer display name."""
    return output_video_name


def resolve_output_path(
    video_file: Path,
    output_video_name: str | None,
    video_index_dir: str,
    overwrite: bool,
) -> tuple[str, Path]:
    """Resolve and validate the output path for the raw VI JSON."""
    resolved_output_video_name = output_video_name or video_file.stem
    output_path = build_video_index_output_path(
        resolved_output_video_name,
        video_index_dir,
    )

    if output_path.exists() and not overwrite:
        raise SystemExit(
            "ERROR: Output file already exists: "
            f"{output_path}. Use --overwrite or choose a different "
            "--output-video-name."
        )

    return resolved_output_video_name, output_path


def print_json(payload: dict[str, object]) -> None:
    """Print a stable JSON payload for CLI output."""
    print(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    """Upload one video, wait for indexing, and save the raw VI JSON."""
    parser = build_parser()
    args = parser.parse_args(argv)

    video_file = args.video_file.expanduser()
    if not video_file.is_file():
        raise SystemExit(f"ERROR: Video file not found: {video_file}")

    resolved_output_video_name, output_path = resolve_output_path(
        video_file,
        args.output_video_name,
        args.video_index_dir,
        args.overwrite,
    )
    video_indexer_name = (
        args.video_indexer_name
        or build_default_video_indexer_name(resolved_output_video_name)
    )

    config = VideoIndexerConfig.from_env()
    if args.request_timeout_seconds is not None:
        if args.request_timeout_seconds < 1:
            raise SystemExit(
                "ERROR: --request-timeout-seconds must be at least 1."
            )
        config = replace(config, timeout_seconds=args.request_timeout_seconds)

    if args.upload_attempts < 1:
        raise SystemExit("ERROR: --upload-attempts must be at least 1.")
    if args.upload_retry_delay_seconds < 0:
        raise SystemExit(
            "ERROR: --upload-retry-delay-seconds cannot be negative."
        )

    client = VideoIndexerApiClient(config)

    upload_request = VideoUploadRequest(
        name=video_indexer_name,
        file_path=video_file,
        description=args.description,
        language=args.language,
        privacy=args.privacy,
        indexing_preset=args.indexing_preset,
        streaming_preset=args.streaming_preset,
    )

    try:
        print_json(
            {
                "operation": "start-process-video-indexer-end-to-end",
                "videoFile": str(video_file),
                "videoIndexerName": video_indexer_name,
                "outputVideoName": resolved_output_video_name,
                "outputPath": str(output_path),
                "requestTimeoutSeconds": config.timeout_seconds,
                "uploadAttempts": args.upload_attempts,
            }
        )

        upload_response: dict[str, object] | None = None
        for attempt in range(1, args.upload_attempts + 1):
            try:
                print(
                    f"Upload attempt {attempt}/{args.upload_attempts}: "
                    f"{video_file.name}"
                )
                upload_response = client.upload_video(upload_request)
                break
            except VideoIndexerApiError:
                if attempt >= args.upload_attempts:
                    raise
                print(
                    f"Upload attempt {attempt} failed. Retrying in "
                    f"{args.upload_retry_delay_seconds} seconds..."
                )
                sleep(args.upload_retry_delay_seconds)

        if upload_response is None:
            raise VideoIndexerApiError("Upload did not return a response.")

        video_id = str(upload_response.get("id") or "")
        if not video_id:
            raise VideoIndexerApiError(
                "Upload response did not include a video id."
            )

        print_json(
            {
                "operation": "upload-video",
                "videoFile": str(video_file),
                "videoIndexerName": video_indexer_name,
                "outputVideoName": resolved_output_video_name,
                "videoId": video_id,
                "state": upload_response.get("state"),
                "processingProgress": upload_response.get(
                    "processingProgress"
                ),
            }
        )

        index_request = VideoIndexRequest(video_id=video_id)
        last_reported_state: tuple[str | None, str | None] | None = None

        def report_progress(status_snapshot: object) -> None:
            nonlocal last_reported_state
            state = getattr(status_snapshot, "state", None)
            progress = getattr(status_snapshot, "processing_progress", None)
            current_state = (state, progress)
            if current_state == last_reported_state:
                return
            last_reported_state = current_state
            printable_state = state or "Unknown"
            printable_progress = progress or "unknown"
            print(
                f"Polling {video_id}: state={printable_state}, "
                f"progress={printable_progress}"
            )

        status_snapshot, index_payload = client.wait_for_video_index_result(
            index_request,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
            on_poll=report_progress,
        )
        saved_path = save_json_output(index_payload, output_path)

        print_json(
            {
                "operation": "process-video-indexer-end-to-end",
                **status_snapshot.to_dict(),
                "videoFile": str(video_file),
                "videoIndexerName": video_indexer_name,
                "outputVideoName": resolved_output_video_name,
                "outputPath": str(saved_path),
            }
        )
        return 0
    except VideoIndexerApiError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
