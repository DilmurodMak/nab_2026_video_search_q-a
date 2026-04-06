"""Streamlit UI for the Video Indexer end-to-end workflow."""

from __future__ import annotations

from dataclasses import asdict
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
    build_final_output_step,
    get_account_token_step,
    get_video_index_step,
    index_in_ai_search_step,
    upload_video_step,
)
from src.helper.video_indexer_helpers import normalize_output_video_name


APP_TITLE = "Video Index Workflow"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
STEP_ORDER = [
    "get_token",
    "upload_video",
    "get_video_index",
    "build_final_output",
    "index_in_search",
]
STEP_TITLES = {
    "get_token": "1. Get Account Token",
    "upload_video": "2. Upload Video",
    "get_video_index": "3. Get Video Index",
    "build_final_output": "4. Build Final Output",
    "index_in_search": "5. Index In Azure AI Search",
}
STEP_DESCRIPTIONS = {
    "get_token": "Fetch the Video Indexer token used by the workflow.",
    "upload_video": (
        "Upload the selected video file and capture the returned "
        "Video Indexer id."
    ),
    "get_video_index": (
        "Poll processing state, retry if needed, and save the raw VI JSON."
    ),
    "build_final_output": (
        "Normalize the VI JSON into the final_output shape "
        "without CU descriptions."
    ),
    "index_in_search": (
        "Embed and upload the final output documents into "
        "Azure AI Search."
    ),
}


def _discover_local_videos() -> list[str]:
    video_dir = Path("video")
    if not video_dir.exists():
        return []
    return sorted(
        str(path)
        for path in video_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def _default_output_name(video_file: str) -> str:
    if not video_file:
        return ""
    try:
        return normalize_output_video_name(Path(video_file).stem)
    except ValueError:
        return ""


def _default_raw_vi_path(video_index_dir: str, output_video_name: str) -> str:
    if not output_video_name:
        return ""
    return str(Path(video_index_dir) / f"{output_video_name}_vi_output.json")


def _default_final_output_path(
    video_index_dir: str,
    output_video_name: str,
) -> str:
    if not output_video_name:
        return ""
    return str(
        Path(video_index_dir) / f"{output_video_name}_final_output.json"
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
    return (
        f"<span class='status-pill {class_name}'>{label}</span>"
    )


def _init_state() -> None:
    local_videos = _discover_local_videos()
    default_video_file = local_videos[0] if local_videos else ""
    defaults = {
        "video_file": default_video_file,
        "output_video_name": _default_output_name(default_video_file),
        "video_id": "",
        "video_id_input": "",
        "raw_vi_path": _default_raw_vi_path(
            "video_index",
            _default_output_name(default_video_file),
        ),
        "final_output_path": _default_final_output_path(
            "video_index",
            _default_output_name(default_video_file),
        ),
        "video_index_dir": "video_index",
        "poll_interval_seconds": 15,
        "timeout_seconds": 3600,
        "allow_edit_token": True,
        "recreate_index": False,
        "token": "",
        "token_permission": "",
        "last_synced_video_file": default_video_file,
        "step_results": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _sync_video_id_input() -> None:
    """Mirror the internal video id into the sidebar text input state."""
    st.session_state.video_id_input = st.session_state.video_id


def _on_video_id_change() -> None:
    """Persist manual edits from the sidebar video id text input."""
    st.session_state.video_id = st.session_state.video_id_input.strip()


def _sync_derived_paths() -> None:
    current_video_file = st.session_state.video_file.strip()
    output_video_name = _default_output_name(current_video_file)

    if current_video_file != st.session_state.last_synced_video_file:
        st.session_state.video_id = ""
        st.session_state.step_results = {}
        st.session_state.last_synced_video_file = current_video_file

    st.session_state.output_video_name = output_video_name
    st.session_state.raw_vi_path = _default_raw_vi_path(
        st.session_state.video_index_dir,
        output_video_name,
    )
    st.session_state.final_output_path = _default_final_output_path(
        st.session_state.video_index_dir,
        output_video_name,
    )


def _result_for(step_key: str) -> dict[str, Any] | None:
    return st.session_state.step_results.get(step_key)


def _save_result(outcome: WorkflowStepOutcome) -> None:
    st.session_state.step_results[outcome.step_key] = asdict(outcome)

    if outcome.step_key == "get_token" and outcome.success:
        st.session_state.token = outcome.details.get("token", "")
        st.session_state.token_permission = outcome.details.get(
            "permission",
            "",
        )

    if outcome.step_key == "upload_video" and outcome.success:
        st.session_state.video_id = outcome.details.get("videoId", "")
        st.session_state.output_video_name = outcome.details.get(
            "outputVideoName",
            st.session_state.output_video_name,
        )
        st.session_state.raw_vi_path = _default_raw_vi_path(
            st.session_state.video_index_dir,
            st.session_state.output_video_name,
        )
        st.session_state.final_output_path = _default_final_output_path(
            st.session_state.video_index_dir,
            st.session_state.output_video_name,
        )

    if outcome.step_key == "get_video_index" and outcome.success:
        st.session_state.video_id = outcome.details.get(
            "videoId",
            st.session_state.video_id,
        )
        st.session_state.raw_vi_path = outcome.details.get(
            "outputPath",
            st.session_state.raw_vi_path,
        )

    if outcome.step_key == "build_final_output" and outcome.success:
        st.session_state.final_output_path = outcome.details.get(
            "outputPath",
            st.session_state.final_output_path,
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
                allow_edit=st.session_state.allow_edit_token,
                logger=logger,
            )
        elif step_key == "upload_video":
            outcome = upload_video_step(
                video_file=st.session_state.video_file,
                output_video_name=st.session_state.output_video_name or None,
                access_token=st.session_state.token or None,
                logger=logger,
            )
        elif step_key == "get_video_index":
            outcome = get_video_index_step(
                video_id=st.session_state.video_id,
                output_video_name=st.session_state.output_video_name or None,
                video_index_dir=st.session_state.video_index_dir,
                poll_interval_seconds=st.session_state.poll_interval_seconds,
                timeout_seconds=st.session_state.timeout_seconds,
                access_token=st.session_state.token or None,
                logger=logger,
            )
        elif step_key == "build_final_output":
            outcome = build_final_output_step(
                vi_json_path=st.session_state.raw_vi_path,
                output_path=st.session_state.final_output_path or None,
                logger=logger,
            )
        elif step_key == "index_in_search":
            outcome = index_in_ai_search_step(
                final_output_path=st.session_state.final_output_path,
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
    if should_rerun:
        st.rerun()
    return outcome


def _run_all_steps() -> None:
    for step_key in STEP_ORDER:
        outcome = _run_step(step_key, should_rerun=False)
        if not outcome.success:
            break
    st.rerun()


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
        local_videos = _discover_local_videos()
        if local_videos:
            selected = st.selectbox(
                "Known local videos",
                options=[""] + local_videos,
                index=0,
            )
            if selected:
                st.session_state.video_file = selected

        _sync_derived_paths()
        _sync_video_id_input()

        st.text_input("Video file path", key="video_file")
        st.text_input(
            "Video id",
            key="video_id_input",
            on_change=_on_video_id_change,
        )

        st.markdown("## Expected output names")
        if st.session_state.output_video_name:
            st.caption(
                "Raw VI JSON: "
                f"{Path(st.session_state.raw_vi_path).name}"
            )
            st.caption(
                "Final output: "
                f"{Path(st.session_state.final_output_path).name}"
            )
        else:
            st.caption("Select a video file to see the expected output names.")

        st.markdown("## Workflow controls")
        st.checkbox("Recreate AI Search index", key="recreate_index")
        if st.button("Reset Step Status"):
            st.session_state.step_results = {}


def _render_summary() -> None:
    mode_label = "One file"
    video_id_label = st.session_state.video_id or "Not uploaded"
    raw_vi_label = st.session_state.raw_vi_path or "Not created"
    final_output_label = st.session_state.final_output_path or "Not created"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mode", mode_label)
    col2.metric("Video Id", video_id_label)
    col3.metric(
        "Raw VI JSON",
        "Ready" if Path(raw_vi_label).exists() else "Missing",
    )
    col4.metric(
        "Final Output",
        "Ready" if Path(final_output_label).exists() else "Missing",
    )


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

    _render_summary()

    run_all_col, spacer_col = st.columns([1, 3])
    with run_all_col:
        if st.button(
            "Run Full Workflow",
            type="primary",
            use_container_width=True,
        ):
            _run_all_steps()

    for step_key in STEP_ORDER:
        _render_step(step_key)


if __name__ == "__main__":
    main()
