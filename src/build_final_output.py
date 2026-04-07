"""
build_final_output.py

Build one final output file from a Video Indexer JSON file and an optional
Content Understanding JSON file.

Each document is one VI scene with grounded signals merged in:
    - optional Content Understanding scene description
    - transcript phrases overlapping the scene window
    - speaker tags from transcript or speaker timelines
    - OCR or on-screen text
    - visual labels
    - brands detected via OCR
    - named locations
    - keywords extracted from speech
    - topics
    - detected objects

VI stays the base schema for timing and structured fields. When provided,
Content Understanding contributes only an aligned scene description.

Usage:
    python src/build_final_output.py \
        video_index/flight_simulator_vi_output.json \
        --cu-json video_index/flight_simulator_cu_output.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from src.helper.video_indexer_helpers import normalize_output_video_name
except ImportError:
    from helper.video_indexer_helpers import normalize_output_video_name


VI_OUTPUT_SUFFIX = "_vi_output"
CU_OUTPUT_SUFFIX = "_cu_output"
FINAL_OUTPUT_SUFFIX = "_final_output.json"
LEGACY_OUTPUT_SUFFIXES = ("_final_segments", "_segments")


def ts_to_ms(ts: str) -> int:
    """Convert VI timestamp '0:00:33.76' to milliseconds."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    secs = float(parts[2])
    return int((hours * 3600 + minutes * 60 + secs) * 1000)


def overlap_ms(
    inst_start_ms: int, inst_end_ms: int, win_start_ms: int, win_end_ms: int
) -> int:
    """Return the overlap duration in milliseconds between two windows."""
    return max(
        0,
        min(inst_end_ms, win_end_ms) - max(inst_start_ms, win_start_ms),
    )


def overlaps(
    inst_start_ms: int, inst_end_ms: int, win_start_ms: int, win_end_ms: int
) -> bool:
    """True if [inst_start, inst_end) overlaps [win_start, win_end)."""
    return overlap_ms(inst_start_ms, inst_end_ms, win_start_ms, win_end_ms) > 0


def normalize_text(text: str) -> str:
    """Collapse internal whitespace so indexed text is cleaner and stable."""
    return " ".join(text.split()).strip()


def ordered_unique(values: list[str]) -> list[str]:
    """Deduplicate while preserving order, ignoring case."""
    unique = []
    seen = set()
    for value in values:
        cleaned = normalize_text(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique


def first_present(item: dict, keys: list[str]) -> str:
    """Return the first populated string-like field from the provided keys."""
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def format_seek_seconds(milliseconds: int) -> str:
    """Format milliseconds as a compact seconds string for seek URLs."""
    seconds = f"{milliseconds / 1000:.3f}".rstrip("0").rstrip(".")
    return seconds or "0"


def derive_video_name(file_path: str | Path) -> str:
    """Derive the video name from known pipeline file naming conventions."""
    file_stem = Path(file_path).stem
    for suffix in (
        VI_OUTPUT_SUFFIX,
        CU_OUTPUT_SUFFIX,
        *LEGACY_OUTPUT_SUFFIXES,
    ):
        if file_stem.endswith(suffix):
            return file_stem[: -len(suffix)]
    if file_stem.endswith(FINAL_OUTPUT_SUFFIX.removesuffix(".json")):
        return file_stem[: -len(FINAL_OUTPUT_SUFFIX.removesuffix(".json"))]
    return file_stem


def build_final_output_path(
    video_name: str, base_dir: str | Path | None
) -> Path:
    """Build the canonical final output path for a video."""
    output_dir = Path(base_dir) if base_dir else Path.cwd()
    normalized_video_name = normalize_output_video_name(video_name)
    return output_dir / f"{normalized_video_name}{FINAL_OUTPUT_SUFFIX}"


def collect_insights(
    insight_list: list,
    win_start_ms: int,
    win_end_ms: int,
    value_keys: list[str],
    min_confidence: float = 0.0,
) -> list[str]:
    """
    Return VI insight values whose instances overlap the time window.

    Results are ranked by overlap duration and confidence, then deduplicated.
    """
    ranked_results = []
    for item in insight_list:
        confidence = item.get("confidence", 1.0)
        if confidence < min_confidence:
            continue
        value = normalize_text(first_present(item, value_keys))
        if not value:
            continue
        total_overlap_ms = 0
        for inst in item.get("instances", []):
            start_ts = inst.get("adjustedStart") or inst.get("start")
            end_ts = inst.get("adjustedEnd") or inst.get("end")
            if not start_ts or not end_ts:
                continue
            start_ms = ts_to_ms(start_ts)
            end_ms = ts_to_ms(end_ts)
            total_overlap_ms += overlap_ms(
                start_ms,
                end_ms,
                win_start_ms,
                win_end_ms,
            )

        if total_overlap_ms > 0:
            ranked_results.append((value, total_overlap_ms, confidence))

    ranked_results.sort(
        key=lambda item: (-item[1], -item[2], item[0].casefold())
    )
    return ordered_unique([value for value, _, _ in ranked_results])


def collect_transcript_entries(
    transcript_list: list, win_start_ms: int, win_end_ms: int
) -> list[dict]:
    """Collect overlapping transcript items with ordering and speaker tags."""
    entries = []
    for item in transcript_list:
        text = normalize_text(item.get("text", ""))
        if not text:
            continue

        speaker_id = item.get("speakerId")
        speaker = f"Speaker #{speaker_id}" if speaker_id else ""
        first_overlap_ms = None

        for inst in item.get("instances", []):
            start_ts = inst.get("adjustedStart") or inst.get("start")
            end_ts = inst.get("adjustedEnd") or inst.get("end")
            if not start_ts or not end_ts:
                continue

            start_ms = ts_to_ms(start_ts)
            end_ms = ts_to_ms(end_ts)
            if not overlaps(start_ms, end_ms, win_start_ms, win_end_ms):
                continue

            overlap_start_ms = max(start_ms, win_start_ms)
            if first_overlap_ms is None or overlap_start_ms < first_overlap_ms:
                first_overlap_ms = overlap_start_ms

        if first_overlap_ms is not None:
            entries.append(
                {
                    "speaker": speaker,
                    "text": text,
                    "startMs": first_overlap_ms,
                }
            )

    entries.sort(key=lambda item: item["startMs"])

    unique_entries = []
    seen = set()
    for entry in entries:
        key = (entry["speaker"], entry["text"])
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append(entry)

    return unique_entries


def collect_transcript(
    transcript_list: list, win_start_ms: int, win_end_ms: int
) -> str:
    """Collect transcript phrases that overlap this window as one sentence."""
    entries = collect_transcript_entries(
        transcript_list,
        win_start_ms,
        win_end_ms,
    )
    return " ".join(entry["text"] for entry in entries)


def build_search_text(
    description: str,
    transcript: str,
    speakers: list[str],
    ocr_text: list[str],
    brands: list[str],
    locations: list[str],
    objects: list[str],
    labels: list[str],
    keywords: list[str],
    topics: list[str],
) -> str:
    """Build the retrieval text used for embeddings and semantic ranking."""
    search_parts = []
    if description:
        search_parts.append(f"Scene description: {description}")
    if transcript:
        search_parts.append(f"Dialogue: {transcript}")
    if speakers:
        search_parts.append(f"Speakers: {', '.join(speakers[:3])}")
    if ocr_text:
        search_parts.append(f"On-screen text: {', '.join(ocr_text[:4])}")
    if brands:
        search_parts.append(f"Brands and logos: {', '.join(brands[:4])}")
    if locations:
        search_parts.append(f"Named locations: {', '.join(locations[:4])}")
    if objects:
        search_parts.append(f"Detected objects: {', '.join(objects[:6])}")
    if labels:
        search_parts.append(f"Visual elements: {', '.join(labels[:8])}")
    if keywords:
        search_parts.append(f"Speech keywords: {', '.join(keywords[:6])}")
    if topics:
        search_parts.append(f"Topics: {', '.join(topics[:4])}")
    return " ".join(f"{part.rstrip('.')}" + "." for part in search_parts)


def load_content_understanding_segments(cu_json_path: str) -> list[dict]:
    """Load CU segments into a normalized list for overlap matching."""
    with open(cu_json_path, "r") as file_handle:
        data = json.load(file_handle)

    contents = data.get("result", {}).get("contents", [])
    if not contents:
        return []

    content = contents[0]
    normalized_segments = []

    for segment in content.get("segments", []):
        description = normalize_text(segment.get("description", ""))
        if not description:
            continue
        normalized_segments.append(
            {
                "segmentId": str(segment.get("segmentId", "")),
                "startTimeMs": int(segment["startTimeMs"]),
                "endTimeMs": int(segment["endTimeMs"]),
                "description": description,
            }
        )

    if normalized_segments:
        return normalized_segments

    fields_segments = (
        content.get("fields", {})
        .get("Segments", {})
        .get("valueArray", [])
    )

    for segment in fields_segments:
        value_object = segment.get("valueObject", {})
        description = normalize_text(
            value_object.get("Description", {}).get("valueString", "")
        )
        if not description:
            continue
        normalized_segments.append(
            {
                "segmentId": str(
                    value_object.get("SegmentId", {}).get("valueString", "")
                ),
                "startTimeMs": int(
                    value_object.get("StartTimeMs", {}).get("valueInteger", 0)
                ),
                "endTimeMs": int(
                    value_object.get("EndTimeMs", {}).get("valueInteger", 0)
                ),
                "description": description,
            }
        )

    return normalized_segments


def select_best_cu_description(
    cu_segments: list[dict], win_start_ms: int, win_end_ms: int
) -> str:
    """Return the CU description with the strongest overlap to the VI scene."""
    best_description = ""
    best_overlap_ms = 0
    best_start_ms = sys.maxsize

    for segment in cu_segments:
        description = segment.get("description", "")
        if not description:
            continue

        current_overlap_ms = overlap_ms(
            segment["startTimeMs"],
            segment["endTimeMs"],
            win_start_ms,
            win_end_ms,
        )
        if current_overlap_ms <= 0:
            continue

        segment_start_ms = segment["startTimeMs"]
        if current_overlap_ms > best_overlap_ms:
            best_description = description
            best_overlap_ms = current_overlap_ms
            best_start_ms = segment_start_ms
        elif (
            current_overlap_ms == best_overlap_ms
            and segment_start_ms < best_start_ms
        ):
            best_description = description
            best_start_ms = segment_start_ms

    return best_description


def build_final_output(
    vi_json_path: str, cu_json_path: str | None = None
) -> tuple[str, list[dict]]:
    """Build a single final output document list from VI and optional CU."""
    with open(vi_json_path, "r") as file_handle:
        data = json.load(file_handle)

    output_video_name = normalize_output_video_name(
        derive_video_name(vi_json_path)
    )

    vi_account_id = data.get("accountId", "")
    vi_video_id = str(data.get("id") or "")
    video = data["videos"][0]
    video_name = normalize_output_video_name(
        str(video.get("name") or data.get("name") or output_video_name)
    )
    document_id_prefix = (
        normalize_output_video_name(vi_video_id)
        if vi_video_id
        else video_name
    )
    insights = video["insights"]

    scenes = insights.get("scenes", [])
    transcript_list = insights.get("transcript", [])
    labels_list = insights.get("labels", [])
    brands_list = insights.get("brands", [])
    locations_list = insights.get("namedLocations", [])
    keywords_list = insights.get("keywords", [])
    topics_list = insights.get("topics", [])
    ocr_list = insights.get("ocr", [])
    speakers_list = insights.get("speakers", [])
    objects_list = insights.get("detectedObjects", [])
    cu_segments = (
        load_content_understanding_segments(cu_json_path)
        if cu_json_path
        else []
    )

    documents = []

    for scene in scenes:
        scene_id = scene["id"]
        inst = scene["instances"][0]
        start_ms = ts_to_ms(inst["adjustedStart"])
        end_ms = ts_to_ms(inst["adjustedEnd"])
        seek_time = format_seek_seconds(start_ms)

        transcript_entries = collect_transcript_entries(
            transcript_list, start_ms, end_ms
        )
        transcript = " ".join(entry["text"] for entry in transcript_entries)
        speakers = ordered_unique(
            [
                entry["speaker"]
                for entry in transcript_entries
                if entry["speaker"]
            ]
        )
        if not speakers:
            speakers = collect_insights(
                speakers_list,
                start_ms,
                end_ms,
                value_keys=["name"],
                min_confidence=0.0,
            )

        ocr_text = collect_insights(
            ocr_list, start_ms, end_ms, value_keys=["text"], min_confidence=0.8
        )
        labels = collect_insights(
            labels_list,
            start_ms,
            end_ms,
            value_keys=["name"],
            min_confidence=0.0,
        )
        brands = collect_insights(
            brands_list,
            start_ms,
            end_ms,
            value_keys=["name"],
            min_confidence=0.0,
        )
        locations = collect_insights(
            locations_list,
            start_ms,
            end_ms,
            value_keys=["name"],
            min_confidence=0.0,
        )
        keywords = collect_insights(
            keywords_list,
            start_ms,
            end_ms,
            value_keys=["text"],
            min_confidence=0.5,
        )
        topics = collect_insights(
            topics_list,
            start_ms,
            end_ms,
            value_keys=["name"],
            min_confidence=0.6,
        )
        objects = collect_insights(
            objects_list,
            start_ms,
            end_ms,
            value_keys=["displayName", "type", "name", "text"],
            min_confidence=0.0,
        )
        description = select_best_cu_description(cu_segments, start_ms, end_ms)

        search_text = build_search_text(
            description=description,
            transcript=transcript,
            speakers=speakers,
            ocr_text=ocr_text,
            brands=brands,
            locations=locations,
            objects=objects,
            labels=labels,
            keywords=keywords,
            topics=topics,
        )

        player_url = (
            "https://www.videoindexer.ai/embed/player/"
            f"{vi_account_id}/{vi_video_id}"
            f"?t={seek_time}&location=trial"
        )
        insights_url = (
            "https://www.videoindexer.ai/embed/insights/"
            f"{vi_account_id}/{vi_video_id}/"
            f"?t={seek_time}"
        )

        documents.append(
            {
                "id": f"{document_id_prefix}_scene_{scene_id}",
                "videoName": video_name,
                "sceneId": str(scene_id),
                "startTimeMs": start_ms,
                "endTimeMs": end_ms,
                "description": description,
                "transcript": transcript,
                "speakers": speakers,
                "ocrText": ocr_text,
                "labels": labels,
                "brands": brands,
                "locations": locations,
                "keywords": keywords,
                "topics": topics,
                "objects": objects,
                "searchText": search_text,
                "url": player_url,
                "viInsightsUrl": insights_url,
            }
        )

    return output_video_name, documents


def save_local(
    video_name: str,
    documents: list[dict],
    output_path: str | None = None,
) -> str:
    """Write final output documents to disk."""
    out_path = (
        Path(output_path)
        if output_path
        else build_final_output_path(video_name, None)
    )
    out_path.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved → {out_path}  ({len(documents)} scenes)")
    return str(out_path)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for building one final output file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("vi_json_file")
    parser.add_argument("--cu-json")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    video_name, docs = build_final_output(args.vi_json_file, args.cu_json)
    output_path = args.output
    if not output_path:
        output_path = str(
            build_final_output_path(video_name, Path(args.vi_json_file).parent)
        )

    save_local(video_name, docs, output_path=output_path)

    print("\nSample - scene 1:")
    print(json.dumps(docs[0], indent=2))

    print("\nAll scenes summary:")
    for document in docs:
        print(
            f"  scene {document['sceneId']} "
            f"{document['startTimeMs']/1000:.1f}s-"
            f"{document['endTimeMs']/1000:.1f}s"
        )
        if document["description"]:
            print(f"    description: {document['description'][:80]}...")
        print(f"    labels:    {document['labels']}")
        print(f"    brands:    {document['brands']}")
        print(f"    locations: {document['locations']}")
        print(f"    topics:    {document['topics'][:2]}")
        print(f"    transcript: {document['transcript'][:80]}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
