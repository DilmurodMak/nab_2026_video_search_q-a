"""Streamlit UI for the Video Indexer bulk sync workflow."""

from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
from typing import Any

try:
    import streamlit as st
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: streamlit. Install with "
        "'python -m pip install -r requirements.txt'."
    ) from exc

from src.video_index_workflow import (
    WorkflowStepOutcome,
    build_all_final_outputs_step,
    download_all_video_indexes_step,
    get_account_token_step,
    index_all_final_outputs_step,
)


APP_TITLE = "Video Index Bulk Sync"
SEARCH_INDEX_NAME = os.getenv(
    "AZURE_SEARCH_INDEX_NAME",
    "nab-video-segments",
)
STEP_ORDER = [
    "get_token",
    "download_video_indexes",
    "build_all_final_outputs",
    "index_all_final_outputs",
]
STEP_TITLES = {
    "get_token": "1. Get Account Token",
    "download_video_indexes": "2. Download All Video Indexes",
    "build_all_final_outputs": "3. Build All Final Outputs",
    "index_all_final_outputs": "4. Index All In Azure AI Search",
}
STEP_DESCRIPTIONS = {
    "get_token": (
        "Fetch the Video Indexer reader token used for listing videos and "
        "downloading raw VI JSON payloads."
    ),
    "download_video_indexes": (
        "Enumerate all processed videos in the Video Indexer account and save "
        "each raw VI JSON file locally."
    ),
    "build_all_final_outputs": (
        "Build every final output JSON from the saved VI JSON files in the "
        "artifact directory."
    ),
    "index_all_final_outputs": (
        "Embed and upload all final output documents to Azure AI Search in a "
        "single bulk run."
    ),
}


def _discover_artifact_files(
    video_index_dir: str,
    pattern: str,
) -> list[str]:
    artifact_dir = Path(video_index_dir).expanduser()
    if not artifact_dir.exists():
        return []
    return sorted(
        str(path.resolve())
        for path in artifact_dir.glob(pattern)
        if path.is_file()
    )


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 24:
        return token
    return f"{token[:12]}...{token[-8:]}"


def _status_badge(status: str) -> str:
    classes = {
        "success": "status-success",
        "failed": "status-failed",
        "running": "status-running",
        "idle": "status-idle",
    }
    class_name = classes.get(status, "status-idle")
    label = status.replace("_", " ").title()
    return f"<span class='status-pill {class_name}'>{label}</span>"


def _init_state() -> None:
    defaults = {
        "video_index_dir": "video_index",
        "last_synced_video_index_dir": "video_index",
        "recreate_index": False,
        "token": "",
        "token_permission": "",
        "downloaded_vi_paths": _discover_artifact_files(
            "video_index",
            "*_vi_output.json",
        ),
        "final_output_paths": _discover_artifact_files(
            "video_index",
            "*_final_output.json",
        ),
        "step_results": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _sync_workspace_dir() -> None:
    current_dir = st.session_state.video_index_dir.strip() or "video_index"
    st.session_state.video_index_dir = current_dir

    if current_dir == st.session_state.last_synced_video_index_dir:
        return

    st.session_state.downloaded_vi_paths = _discover_artifact_files(
        current_dir,
        "*_vi_output.json",
    )
    st.session_state.final_output_paths = _discover_artifact_files(
        current_dir,
        "*_final_output.json",
    )
    st.session_state.step_results = {}
    st.session_state.last_synced_video_index_dir = current_dir


def _refresh_local_artifacts() -> None:
    artifact_dir = st.session_state.video_index_dir
    st.session_state.downloaded_vi_paths = _discover_artifact_files(
        artifact_dir,
        "*_vi_output.json",
    )
    st.session_state.final_output_paths = _discover_artifact_files(
        artifact_dir,
        "*_final_output.json",
    )


def _result_for(step_key: str) -> dict[str, Any] | None:
    return st.session_state.step_results.get(step_key)


def _save_result(outcome: WorkflowStepOutcome) -> None:
    st.session_state.step_results[outcome.step_key] = asdict(outcome)

    if outcome.step_key == "get_token" and outcome.details:
        st.session_state.token = outcome.details.get("token", "")
        st.session_state.token_permission = outcome.details.get(
            "permission",
            "",
        )

    if outcome.step_key == "download_video_indexes" and outcome.details:
        st.session_state.downloaded_vi_paths = list(
            outcome.details.get("outputPaths") or []
        )

    if outcome.step_key == "build_all_final_outputs" and outcome.details:
        st.session_state.final_output_paths = list(
            outcome.details.get("outputPaths") or []
        )


def _run_step(
    step_key: str,
    *,
    should_rerun: bool = True,
) -> WorkflowStepOutcome:
    with st.status(STEP_TITLES[step_key], expanded=True) as status_box:
        logs_seen = 0

        def logger(message: str) -> None:
            nonlocal logs_seen
            logs_seen += 1
            status_box.write(f"{logs_seen}. {message}")

        if step_key == "get_token":
            outcome = get_account_token_step(
                allow_edit=False,
                logger=logger,
            )
        elif step_key == "download_video_indexes":
            outcome = download_all_video_indexes_step(
                video_index_dir=st.session_state.video_index_dir,
                access_token=st.session_state.token or None,
                logger=logger,
            )
        elif step_key == "build_all_final_outputs":
            outcome = build_all_final_outputs_step(
                vi_json_paths=st.session_state.downloaded_vi_paths or None,
                video_index_dir=st.session_state.video_index_dir,
                logger=logger,
            )
        elif step_key == "index_all_final_outputs":
            outcome = index_all_final_outputs_step(
                final_output_paths=st.session_state.final_output_paths or None,
                final_output_dir=st.session_state.video_index_dir,
                recreate_index=st.session_state.recreate_index,
                logger=logger,
            )
        else:
            raise RuntimeError(f"Unsupported step: {step_key}")

        status_box.update(
            label=outcome.message,
            state="complete" if outcome.success else "error",
            expanded=not outcome.success,
        )

    _save_result(outcome)
    _refresh_local_artifacts()
    if should_rerun:
        st.rerun()
    return outcome


def _run_all_steps() -> None:
    for step_key in STEP_ORDER:
        outcome = _run_step(step_key, should_rerun=False)
        if not outcome.success:
            break


def _render_step(step_key: str) -> None:
    result = _result_for(step_key)
    status = "idle"
    if result:
        status = "success" if result.get("success") else "failed"

    with st.container(border=True):
        st.markdown(
            f"### {STEP_TITLES[step_key]} {_status_badge(status)}",
            unsafe_allow_html=True,
        )
        st.write(STEP_DESCRIPTIONS[step_key])

        button_label = "Run Step"
        if result and result.get("success"):
            button_label = "Run Again"
        elif result and not result.get("success"):
            button_label = "Retry Step"

        if st.button(button_label, key=f"run_{step_key}"):
            _run_step(step_key)

        if result:
            st.write(result.get("message", ""))
            details = dict(result.get("details") or {})
            if "token" in details:
                details["token"] = _mask_token(details["token"])
            if details:
                st.json(details)
            logs = result.get("logs") or []
            if logs:
                st.code("\n".join(logs[-25:]), language="text")


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Inputs")
        _sync_workspace_dir()
        st.text_input("Local artifact directory", key="video_index_dir")
        st.caption(
            "Raw VI JSON files and final output JSON files are written to "
            "this directory."
        )

        st.markdown("## Workflow controls")
        st.checkbox("Recreate AI Search index", key="recreate_index")
        st.caption(f"Azure AI Search index: {SEARCH_INDEX_NAME}")

        if st.button("Refresh Local Files"):
            _refresh_local_artifacts()
            st.rerun()

        if st.button("Reset Step Status"):
            st.session_state.step_results = {}
            st.rerun()


def _render_summary() -> None:
    _refresh_local_artifacts()
    download_result = _result_for("download_video_indexes") or {}
    index_result = _result_for("index_all_final_outputs") or {}

    download_details = dict(download_result.get("details") or {})
    index_details = dict(index_result.get("details") or {})

    processed_video_count = download_details.get("processedVideoCount")
    uploaded_count = index_details.get("uploadedCount")
    artifact_dir = (
        Path(st.session_state.video_index_dir).expanduser().resolve()
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Processed Videos",
        processed_video_count if processed_video_count is not None else "-",
    )
    col2.metric("Saved VI JSONs", len(st.session_state.downloaded_vi_paths))
    col3.metric("Final Outputs", len(st.session_state.final_output_paths))
    col4.metric(
        "Indexed Docs",
        uploaded_count if uploaded_count is not None else "-",
    )

    st.caption(f"Artifact directory: {artifact_dir}")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(
                    circle at top left,
                    rgba(255, 212, 163, 0.35),
                    transparent 35%
                ),
                linear-gradient(180deg, #f7f1e5 0%, #f4f7fb 52%, #eef4ea 100%);
        }
        .status-pill {
            display: inline-block;
            margin-left: 0.6rem;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .status-success {
            background: #dff6dd;
            color: #14532d;
        }
        .status-failed {
            background: #fde2e1;
            color: #7f1d1d;
        }
        .status-running {
            background: #fff2cc;
            color: #854d0e;
        }
        .status-idle {
            background: #e5e7eb;
            color: #374151;
        }
        h1, h2, h3 {
            font-family: Georgia, "Iowan Old Style", serif;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _init_state()
    _render_sidebar()

    st.title(APP_TITLE)
    st.write(
        "Sync all processed videos from Azure Video Indexer, save the raw VI "
        "JSON payloads locally, build every final output JSON, and upload all "
        "documents to Azure AI Search in one bulk run."
    )

    _render_summary()

    run_all_col, spacer_col = st.columns([1, 3])
    with run_all_col:
        if st.button(
            "Run Full Sync",
            type="primary",
            use_container_width=True,
        ):
            _run_all_steps()

    for step_key in STEP_ORDER:
        _render_step(step_key)


if __name__ == "__main__":
    main()
