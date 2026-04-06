"""Workflow helpers for the Video Indexer end-to-end UI."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .build_final_output import (
    build_final_output,
    build_final_output_path,
    save_local,
)
from .helper.video_indexer_helpers import (
    VideoIndexRequest,
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
