"""
build_all_final_outputs.py

Build enriched final output files for all videos by pairing:
    - video_index/<video_name>_vi_output.json
    - video_index/<video_name>_cu_output.json

The final output is written as:
    - video_index/<video_name>_final_output.json

VI remains the base schema. CU contributes only the aligned scene
description.
"""

import argparse
from pathlib import Path

try:
    from src.build_final_output import (
        CU_OUTPUT_SUFFIX,
        VI_OUTPUT_SUFFIX,
        build_final_output,
        build_final_output_path,
        derive_video_name,
        save_local,
    )
except ImportError:
    from build_final_output import (
        CU_OUTPUT_SUFFIX,
        VI_OUTPUT_SUFFIX,
        build_final_output,
        build_final_output_path,
        derive_video_name,
        save_local,
    )


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}


def discover_video_names(video_dir: Path, video_index_dir: Path) -> list[str]:
    """Discover video names from the video folder and VI output files."""
    video_names = set()

    if video_dir.exists():
        for video_file in video_dir.iterdir():
            if (
                video_file.is_file()
                and video_file.suffix.lower() in VIDEO_EXTENSIONS
            ):
                video_names.add(video_file.stem)

    if video_index_dir.exists():
        for vi_output in video_index_dir.glob(f"*{VI_OUTPUT_SUFFIX}.json"):
            video_names.add(derive_video_name(vi_output))

    return sorted(video_names)


def build_for_video(
    video_name: str, video_index_dir: Path
) -> tuple[Path, int, int]:
    """Create one final output file for a video name."""
    vi_output_path = video_index_dir / f"{video_name}{VI_OUTPUT_SUFFIX}.json"
    cu_output_path = video_index_dir / f"{video_name}{CU_OUTPUT_SUFFIX}.json"
    final_output_path = build_final_output_path(video_name, video_index_dir)

    if not vi_output_path.exists():
        raise FileNotFoundError(f"Missing VI output: {vi_output_path}")

    cu_json_path = str(cu_output_path) if cu_output_path.exists() else None
    resolved_video_name, documents = build_final_output(
        str(vi_output_path),
        cu_json_path,
    )
    save_local(resolved_video_name, documents, str(final_output_path))

    described_segments = sum(
        1 for document in documents if document["description"]
    )
    return final_output_path, len(documents), described_segments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-dir", default="video")
    parser.add_argument("--video-index-dir", default="video_index")
    parser.add_argument("--video-name", action="append")
    args = parser.parse_args(argv)

    video_dir = Path(args.video_dir)
    video_index_dir = Path(args.video_index_dir)

    requested_video_names = args.video_name or []
    video_names = (
        requested_video_names
        if requested_video_names
        else discover_video_names(video_dir, video_index_dir)
    )

    if not video_names:
        print("No videos or VI outputs found to process.")
        return 1

    missing_vi_outputs = []
    for video_name in video_names:
        vi_output_path = (
            video_index_dir / f"{video_name}{VI_OUTPUT_SUFFIX}.json"
        )
        if not vi_output_path.exists():
            missing_vi_outputs.append(str(vi_output_path))
            continue

        final_output_path, segment_count, described_segments = build_for_video(
            video_name,
            video_index_dir,
        )
        print(
            f"Built {final_output_path.name}: {segment_count} segments, "
            f"{described_segments} with CU descriptions"
        )

    if missing_vi_outputs:
        print("Skipped videos with missing VI outputs:")
        for missing_path in missing_vi_outputs:
            print(f"  - {missing_path}")

    return 0 if len(missing_vi_outputs) < len(video_names) else 1


if __name__ == "__main__":
    raise SystemExit(main())
