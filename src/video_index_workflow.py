"""Workflow helpers for the Video Indexer end-to-end UI."""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .build_final_output import (
    build_final_output,
    build_final_output_path,
    derive_video_name,
    save_local,
)
from .helper.video_indexer_helpers import (
    VideoIndexRequest,
    VideoStatusSnapshot,
    VideoUploadRequest,
    build_video_index_output_path,
    normalize_output_video_name,
    peek_access_token_permission,
    save_json_output,
)
from .index_builder import build as upload_final_output_to_search
from .video_indexer_api import VideoIndexerApiClient, VideoIndexerConfig


StepLogger = Callable[[str], None]


@dataclass
class WorkflowStepOutcome:
    """Structured result for one workflow step."""

    step_key: str
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


def _build_client() -> tuple[VideoIndexerConfig, VideoIndexerApiClient]:
    config = VideoIndexerConfig.from_env()
    return config, VideoIndexerApiClient(config)


def _append_log(
    logs: list[str],
    logger: StepLogger | None,
    message: str,
) -> None:
    logs.append(message)
    if logger is not None:
        logger(message)


@contextlib.contextmanager
def _capture_stdout(
    logs: list[str],
    logger: StepLogger | None,
):
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            yield
    finally:
        for line in buffer.getvalue().splitlines():
            cleaned = line.strip()
            if cleaned:
                _append_log(logs, logger, cleaned)


def _default_video_indexer_name(output_video_name: str) -> str:
    return output_video_name


def _resolve_output_video_name(
    video_file: Path | None,
    output_video_name: str | None,
    fallback_name: str | None = None,
) -> str:
    """Resolve the canonical output name used for saved artifacts."""
    candidate = output_video_name
    if not candidate and video_file is not None:
        candidate = video_file.stem
    if not candidate:
        candidate = fallback_name
    if not candidate:
        raise ValueError("Output video name cannot be empty.")
    return normalize_output_video_name(candidate)


def _read_saved_video_id(output_path: Path) -> str | None:
    """Read the Video Indexer id from an existing saved VI JSON file."""
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    nested_videos = payload.get("videos")
    if isinstance(nested_videos, list) and nested_videos:
        first_video = nested_videos[0]
        if isinstance(first_video, dict) and first_video.get("id"):
            return str(first_video["id"])

    video_id = payload.get("id")
    if video_id:
        return str(video_id)

    return None


def _resolve_saved_vi_output_path(
    video_index_dir: Path,
    status_snapshot: VideoStatusSnapshot,
) -> Path:
    """Resolve a stable local VI JSON path without overwriting other videos."""
    base_output_name = _resolve_output_video_name(
        None,
        status_snapshot.name,
        fallback_name=status_snapshot.video_id,
    )
    suffixed_output_name = normalize_output_video_name(
        f"{base_output_name}_{status_snapshot.video_id}"
    )
    candidate_names = [base_output_name]
    if suffixed_output_name != base_output_name:
        candidate_names.append(suffixed_output_name)

    first_available_path: Path | None = None
    for candidate_name in candidate_names:
        candidate_path = build_video_index_output_path(
            candidate_name,
            video_index_dir,
        )
        if candidate_path.exists():
            existing_video_id = _read_saved_video_id(candidate_path)
            if existing_video_id == status_snapshot.video_id:
                return candidate_path
            continue
        if first_available_path is None:
            first_available_path = candidate_path

    if first_available_path is not None:
        return first_available_path

    return build_video_index_output_path(candidate_names[-1], video_index_dir)


def _resolve_paths(
    path_values: list[str] | None,
    *,
    base_dir: Path,
    pattern: str,
) -> list[Path]:
    """Resolve explicit paths or discover matching files in a directory."""
    if path_values:
        resolved_paths: list[Path] = []
        seen_paths: set[str] = set()
        for path_value in path_values:
            resolved_path = Path(path_value).expanduser().resolve()
            resolved_key = str(resolved_path)
            if resolved_key in seen_paths:
                continue
            seen_paths.add(resolved_key)
            resolved_paths.append(resolved_path)
        return resolved_paths

    return [
        path.resolve()
        for path in sorted(base_dir.glob(pattern))
        if path.is_file()
    ]


def _failure_outcome(
    step_key: str,
    logs: list[str],
    exc: Exception | SystemExit,
) -> WorkflowStepOutcome:
    message = str(exc) or exc.__class__.__name__
    if not logs or logs[-1] != message:
        logs.append(message)
    return WorkflowStepOutcome(
        step_key=step_key,
        success=False,
        message=message,
        logs=logs,
    )


def get_account_token_step(
    *,
    allow_edit: bool = True,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Request a Video Indexer account token for the workflow."""
    logs: list[str] = []
    step_key = "get_token"

    try:
        config, client = _build_client()
        _append_log(
            logs,
            logger,
            f"Requesting {'Contributor' if allow_edit else 'Reader'} token.",
        )
        token = client.get_account_access_token(allow_edit=allow_edit)
        permission = peek_access_token_permission(token) or "Unknown"
        _append_log(
            logs,
            logger,
            f"Token received for account {config.account_id} ({permission}).",
        )
        return WorkflowStepOutcome(
            step_key=step_key,
            success=True,
            message=f"{permission} token retrieved.",
            details={
                "token": token,
                "permission": permission,
                "tokenLength": len(token),
                "location": config.location,
                "accountId": config.account_id,
                "allowEdit": allow_edit,
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def upload_video_step(
    *,
    video_file: str | Path,
    output_video_name: str | None = None,
    video_indexer_name: str | None = None,
    description: str | None = None,
    language: str | None = None,
    privacy: str | None = None,
    indexing_preset: str | None = None,
    streaming_preset: str | None = None,
    access_token: str | None = None,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Upload a video to Video Indexer and return the created video id."""
    logs: list[str] = []
    step_key = "upload_video"

    try:
        _, client = _build_client()
        resolved_video_file = Path(video_file).expanduser().resolve()
        if not resolved_video_file.is_file():
            raise FileNotFoundError(
                f"Video file not found: {resolved_video_file}"
            )

        resolved_output_video_name = _resolve_output_video_name(
            resolved_video_file,
            output_video_name,
        )
        resolved_video_indexer_name = (
            video_indexer_name
            or _default_video_indexer_name(resolved_output_video_name)
        )

        _append_log(logs, logger, f"Uploading {resolved_video_file.name}.")
        upload_request = VideoUploadRequest(
            name=resolved_video_indexer_name,
            file_path=resolved_video_file,
            description=description,
            language=language,
            privacy=privacy,
            indexing_preset=indexing_preset,
            streaming_preset=streaming_preset,
        )
        response = client.upload_video(
            upload_request,
            access_token=access_token,
        )
        video_id = str(response.get("id") or "")
        if not video_id:
            raise RuntimeError("Upload response did not include a video id.")

        _append_log(logs, logger, f"Upload complete. Video id: {video_id}")
        return WorkflowStepOutcome(
            step_key=step_key,
            success=True,
            message=f"Uploaded {resolved_video_file.name}.",
            details={
                "videoFile": str(resolved_video_file),
                "videoId": video_id,
                "state": response.get("state"),
                "processingProgress": response.get("processingProgress"),
                "outputVideoName": resolved_output_video_name,
                "videoIndexerName": resolved_video_indexer_name,
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def get_video_index_step(
    *,
    video_id: str,
    output_video_name: str | None = None,
    video_index_dir: str | Path = "video_index",
    poll_interval_seconds: int = 15,
    timeout_seconds: int = 3600,
    access_token: str | None = None,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Wait for indexing to finish and save the raw VI JSON."""
    logs: list[str] = []
    step_key = "get_video_index"

    try:
        _, client = _build_client()
        request = VideoIndexRequest(video_id=video_id)
        _append_log(
            logs,
            logger,
            f"Waiting for video {video_id} to finish indexing.",
        )

        def on_poll(status_snapshot) -> None:
            state = status_snapshot.state or "Unknown"
            progress = status_snapshot.processing_progress or "unknown"
            _append_log(
                logs,
                logger,
                f"State: {state} | Progress: {progress}",
            )

        status_snapshot, index_payload = client.wait_for_video_index_result(
            request,
            access_token=access_token,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

        resolved_output_video_name = _resolve_output_video_name(
            None,
            output_video_name,
            fallback_name=status_snapshot.name or video_id,
        )
        output_path = build_video_index_output_path(
            resolved_output_video_name,
            video_index_dir,
        )
        saved_path = save_json_output(index_payload, output_path)
        _append_log(logs, logger, f"Saved raw VI JSON to {saved_path}")

        return WorkflowStepOutcome(
            step_key=step_key,
            success=True,
            message="Video index saved.",
            details={
                "videoId": status_snapshot.video_id,
                "name": status_snapshot.name,
                "state": status_snapshot.state,
                "processingProgress": status_snapshot.processing_progress,
                "outputVideoName": resolved_output_video_name,
                "outputPath": str(saved_path),
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def download_all_video_indexes_step(
    *,
    video_index_dir: str | Path = "video_index",
    access_token: str | None = None,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Download every processed VI JSON payload for the current account."""
    logs: list[str] = []
    step_key = "download_video_indexes"

    try:
        _, client = _build_client()
        resolved_video_index_dir = Path(video_index_dir).expanduser().resolve()
        resolved_video_index_dir.mkdir(parents=True, exist_ok=True)
        effective_access_token = (
            access_token or client.get_account_access_token()
        )

        _append_log(
            logs,
            logger,
            "Listing videos in the Video Indexer account.",
        )
        video_snapshots = client.list_videos(
            access_token=effective_access_token,
        )
        if not video_snapshots:
            raise RuntimeError(
                "No videos were found in the Video Indexer account."
            )

        processed_snapshots = [
            snapshot
            for snapshot in video_snapshots
            if snapshot.is_complete and not snapshot.is_failure
        ]
        skipped_snapshots = [
            snapshot
            for snapshot in video_snapshots
            if not (snapshot.is_complete and not snapshot.is_failure)
        ]
        if not processed_snapshots:
            raise RuntimeError(
                "No processed videos were found in the Video Indexer account."
            )

        saved_paths: list[str] = []
        saved_videos: list[dict[str, str]] = []
        failed_downloads: list[str] = []

        for snapshot in processed_snapshots:
            display_name = snapshot.name or snapshot.video_id
            _append_log(
                logs,
                logger,
                f"Downloading {display_name} ({snapshot.video_id}).",
            )
            try:
                index_payload = client.get_video_index(
                    VideoIndexRequest(video_id=snapshot.video_id),
                    access_token=effective_access_token,
                )
                output_path = _resolve_saved_vi_output_path(
                    resolved_video_index_dir,
                    snapshot,
                )
                save_json_output(index_payload, output_path)
            except (Exception, SystemExit) as exc:
                failed_downloads.append(f"{snapshot.video_id}: {exc}")
                _append_log(
                    logs,
                    logger,
                    f"Failed to download {snapshot.video_id}: {exc}",
                )
                continue

            saved_paths.append(str(output_path))
            saved_videos.append(
                {
                    "videoId": snapshot.video_id,
                    "name": display_name,
                    "outputPath": str(output_path),
                }
            )
            _append_log(
                logs,
                logger,
                f"Saved raw VI JSON to {output_path}",
            )

        if not saved_paths:
            raise RuntimeError("No VI JSON files were saved.")

        message = f"Saved {len(saved_paths)} VI JSON files."
        if skipped_snapshots:
            message += (
                f" Skipped {len(skipped_snapshots)} videos that are not "
                "ready for download."
            )
        if failed_downloads:
            message += f" {len(failed_downloads)} downloads failed."

        return WorkflowStepOutcome(
            step_key=step_key,
            success=not failed_downloads,
            message=message,
            details={
                "accountVideoCount": len(video_snapshots),
                "processedVideoCount": len(processed_snapshots),
                "savedVideoCount": len(saved_paths),
                "skippedVideoCount": len(skipped_snapshots),
                "outputPaths": saved_paths,
                "savedVideos": saved_videos,
                "failedDownloads": failed_downloads,
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def build_final_output_step(
    *,
    vi_json_path: str | Path,
    output_path: str | Path | None = None,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Build the normalized final output without CU enrichment."""
    logs: list[str] = []
    step_key = "build_final_output"
    try:
        resolved_vi_json_path = Path(vi_json_path).expanduser().resolve()
        if not resolved_vi_json_path.is_file():
            raise FileNotFoundError(
                f"VI JSON file not found: {resolved_vi_json_path}"
            )

        _append_log(
            logs,
            logger,
            f"Building final output from {resolved_vi_json_path.name}.",
        )
        with _capture_stdout(logs, logger):
            video_name, documents = build_final_output(
                str(resolved_vi_json_path),
                None,
            )
            resolved_output_path = (
                Path(output_path).expanduser().resolve()
                if output_path
                else build_final_output_path(
                    video_name,
                    resolved_vi_json_path.parent,
                ).resolve()
            )
            save_local(video_name, documents, str(resolved_output_path))

        _append_log(
            logs,
            logger,
            f"Built {len(documents)} scenes from raw VI JSON.",
        )
        return WorkflowStepOutcome(
            step_key=step_key,
            success=True,
            message="Final output generated.",
            details={
                "videoName": video_name,
                "outputPath": str(resolved_output_path),
                "sceneCount": len(documents),
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def build_all_final_outputs_step(
    *,
    vi_json_paths: list[str] | None = None,
    video_index_dir: str | Path = "video_index",
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Build final output files for all supplied VI JSON artifacts."""
    logs: list[str] = []
    step_key = "build_all_final_outputs"

    try:
        resolved_video_index_dir = Path(video_index_dir).expanduser().resolve()
        resolved_vi_paths = _resolve_paths(
            vi_json_paths,
            base_dir=resolved_video_index_dir,
            pattern="*_vi_output.json",
        )
        if not resolved_vi_paths:
            raise FileNotFoundError(
                f"No VI JSON files were found in {resolved_video_index_dir}."
            )

        missing_vi_paths = [
            path for path in resolved_vi_paths if not path.is_file()
        ]
        if missing_vi_paths:
            raise FileNotFoundError(
                f"VI JSON file not found: {missing_vi_paths[0]}"
            )

        output_paths: list[str] = []
        failed_builds: list[str] = []
        total_scene_count = 0

        for vi_path in resolved_vi_paths:
            output_path = build_final_output_path(
                derive_video_name(vi_path),
                resolved_video_index_dir,
            ).resolve()
            _append_log(
                logs,
                logger,
                f"Building final output from {vi_path.name}.",
            )
            try:
                with _capture_stdout(logs, logger):
                    resolved_output_name, documents = build_final_output(
                        str(vi_path),
                        None,
                    )
                    save_local(
                        resolved_output_name,
                        documents,
                        str(output_path),
                    )
            except (Exception, SystemExit) as exc:
                failed_builds.append(f"{vi_path.name}: {exc}")
                _append_log(
                    logs,
                    logger,
                    f"Failed to build {vi_path.name}: {exc}",
                )
                continue

            output_paths.append(str(output_path))
            total_scene_count += len(documents)
            _append_log(
                logs,
                logger,
                f"Saved final output to {output_path.name} "
                f"({len(documents)} scenes).",
            )

        if not output_paths:
            raise RuntimeError("No final output files were generated.")

        message = f"Built {len(output_paths)} final output files."
        if failed_builds:
            message += f" {len(failed_builds)} builds failed."

        return WorkflowStepOutcome(
            step_key=step_key,
            success=not failed_builds,
            message=message,
            details={
                "inputViJsonCount": len(resolved_vi_paths),
                "generatedFileCount": len(output_paths),
                "sceneCount": total_scene_count,
                "sourcePaths": [str(path) for path in resolved_vi_paths],
                "outputPaths": output_paths,
                "failedBuilds": failed_builds,
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def index_in_ai_search_step(
    *,
    final_output_path: str | Path,
    recreate_index: bool = False,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Embed and upload the final output file into Azure AI Search."""
    logs: list[str] = []
    step_key = "index_in_search"

    try:
        resolved_final_output_path = (
            Path(final_output_path).expanduser().resolve()
        )
        if not resolved_final_output_path.is_file():
            raise FileNotFoundError(
                f"Final output file not found: {resolved_final_output_path}"
            )

        _append_log(
            logs,
            logger,
            f"Uploading {resolved_final_output_path.name} to Azure AI Search.",
        )
        with _capture_stdout(logs, logger):
            upload_final_output_to_search(
                str(resolved_final_output_path),
                recreate_index=recreate_index,
            )

        return WorkflowStepOutcome(
            step_key=step_key,
            success=True,
            message="Azure AI Search upload finished.",
            details={
                "finalOutputPath": str(resolved_final_output_path),
                "recreateIndex": recreate_index,
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)


def index_all_final_outputs_step(
    *,
    final_output_paths: list[str] | None = None,
    final_output_dir: str | Path = "video_index",
    recreate_index: bool = False,
    logger: StepLogger | None = None,
) -> WorkflowStepOutcome:
    """Embed and upload all final output files into Azure AI Search."""
    logs: list[str] = []
    step_key = "index_all_final_outputs"

    try:
        resolved_final_output_dir = (
            Path(final_output_dir).expanduser().resolve()
        )
        resolved_final_output_paths = _resolve_paths(
            final_output_paths,
            base_dir=resolved_final_output_dir,
            pattern="*_final_output.json",
        )
        if not resolved_final_output_paths:
            raise FileNotFoundError(
                "No final output files were found in "
                f"{resolved_final_output_dir}."
            )

        missing_final_outputs = [
            path for path in resolved_final_output_paths if not path.is_file()
        ]
        if missing_final_outputs:
            raise FileNotFoundError(
                f"Final output file not found: {missing_final_outputs[0]}"
            )

        _append_log(
            logs,
            logger,
            f"Uploading {len(resolved_final_output_paths)} final output "
            "files to Azure AI Search.",
        )
        with _capture_stdout(logs, logger):
            summary = upload_final_output_to_search(
                [str(path) for path in resolved_final_output_paths],
                recreate_index=recreate_index,
            )

        failed_count = int(summary.get("failedCount") or 0)
        uploaded_count = int(summary.get("uploadedCount") or 0)
        message = (
            f"Uploaded {uploaded_count} documents from "
            f"{len(resolved_final_output_paths)} final output files."
        )
        if failed_count:
            message += f" {failed_count} documents failed."

        return WorkflowStepOutcome(
            step_key=step_key,
            success=failed_count == 0,
            message=message,
            details={
                **summary,
                "finalOutputPaths": [
                    str(path) for path in resolved_final_output_paths
                ],
            },
            logs=logs,
        )
    except (Exception, SystemExit) as exc:
        return _failure_outcome(step_key, logs, exc)
