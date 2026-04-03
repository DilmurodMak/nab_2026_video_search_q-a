"""
transform_vi_to_segments.py

Transforms a Video Indexer JSON output into a flat array of scene-level documents
ready for Azure AI Search ingestion (parsingMode: jsonArray).

Each document = one VI scene with grounded signals merged in:
    - transcript phrases overlapping the scene window
    - speaker tags from transcript / speaker timelines
    - OCR / on-screen text
    - visual labels (aircraft, sky, cloud ...)
    - brands detected via OCR (Airbus ...)
    - named locations (Orlando Ground ...)
    - keywords extracted from speech
    - topics (NLP, AI, Machine Learning ...)
    - detected objects

The output stays strictly VI-based. It does not copy or depend on Content
Understanding descriptions. The goal is to produce denser,
better-structured retrieval text for embeddings and LLM grounding while
preserving source fidelity.

Usage:
        python transform_vi_to_segments.py flight_simulator_vi_output.json
"""

import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ts_to_ms(ts: str) -> int:
    """Convert VI timestamp '0:00:33.76' → milliseconds (int)."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    secs = float(parts[2])
    return int((hours * 3600 + minutes * 60 + secs) * 1000)


def overlap_ms(
    inst_start_ms: int, inst_end_ms: int, win_start_ms: int, win_end_ms: int
) -> int:
    """Return the overlap duration in milliseconds between two time windows."""
    return max(0, min(inst_end_ms, win_end_ms) - max(inst_start_ms, win_start_ms))


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


def collect_insights(
    insight_list: list,
    win_start_ms: int,
    win_end_ms: int,
    value_keys: list[str],
    min_confidence: float = 0.0,
) -> list[str]:
    """
    For any VI insight array (labels, brands, locations, keywords, topics),
    return the item values whose instances overlap the time window.
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
            s = ts_to_ms(start_ts)
            e = ts_to_ms(end_ts)
            total_overlap_ms += overlap_ms(s, e, win_start_ms, win_end_ms)

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

            s = ts_to_ms(start_ts)
            e = ts_to_ms(end_ts)
            if not overlaps(s, e, win_start_ms, win_end_ms):
                continue

            overlap_start_ms = max(s, win_start_ms)
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
    """Collect transcript phrases that overlap this window, joined as a sentence."""
    entries = collect_transcript_entries(transcript_list, win_start_ms, win_end_ms)
    return " ".join(entry["text"] for entry in entries)


def build_search_text(
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


# ---------------------------------------------------------------------------
# Main transform
# ---------------------------------------------------------------------------


def transform(vi_json_path: str) -> tuple[str, list[dict]]:
    with open(vi_json_path, "r") as f:
        data = json.load(f)

    # Video name from the VI metadata (or from filename as fallback)
    video_name = data.get("name") or Path(vi_json_path).stem.replace(
        "_vi_output", ""
    )

    # VI account and video IDs for insights embed URLs
    vi_account_id = data.get("accountId", "")
    vi_video_id = data.get("id", "")
    video = data["videos"][0]
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

    documents = []

    for scene in scenes:
        scene_id = scene["id"]
        inst = scene["instances"][0]
        start_ms = ts_to_ms(inst["adjustedStart"])
        end_ms = ts_to_ms(inst["adjustedEnd"])
        seek_time = format_seek_seconds(start_ms)

        # --- collect all signals for this window ---
        transcript_entries = collect_transcript_entries(
            transcript_list, start_ms, end_ms
        )
        transcript = " ".join(entry["text"] for entry in transcript_entries)
        speakers = ordered_unique(
            [entry["speaker"] for entry in transcript_entries if entry["speaker"]]
        )
        if not speakers:
            speakers = collect_insights(
                speakers_list, start_ms, end_ms, value_keys=["name"], min_confidence=0.0
            )

        ocr_text = collect_insights(
            ocr_list, start_ms, end_ms, value_keys=["text"], min_confidence=0.8
        )
        labels = collect_insights(
            labels_list, start_ms, end_ms, value_keys=["name"], min_confidence=0.0
        )
        brands = collect_insights(
            brands_list, start_ms, end_ms, value_keys=["name"], min_confidence=0.0
        )
        locations = collect_insights(
            locations_list, start_ms, end_ms, value_keys=["name"], min_confidence=0.0
        )
        keywords = collect_insights(
            keywords_list, start_ms, end_ms, value_keys=["text"], min_confidence=0.5
        )
        topics = collect_insights(
            topics_list, start_ms, end_ms, value_keys=["name"], min_confidence=0.6
        )
        objects = collect_insights(
            objects_list,
            start_ms,
            end_ms,
            value_keys=["displayName", "type", "name", "text"],
            min_confidence=0.0,
        )

        search_text = build_search_text(
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
            f"https://www.videoindexer.ai/embed/player/{vi_account_id}/{vi_video_id}"
            f"?t={seek_time}&location=trial"
        )
        insights_url = (
            f"https://www.videoindexer.ai/embed/insights/{vi_account_id}/{vi_video_id}/"
            f"?t={seek_time}"
        )

        doc = {
            "id": f"{video_name}_scene_{scene_id}",
            "videoName": video_name,
            "sceneId": str(scene_id),
            "startTimeMs": start_ms,
            "endTimeMs": end_ms,
            # individual signal fields for filtering / faceting in AI Search
            "transcript": transcript,
            "speakers": speakers,
            "ocrText": ocr_text,
            "labels": labels,
            "brands": brands,
            "locations": locations,
            "keywords": keywords,
            "topics": topics,
            "objects": objects,
            # rich text field for vector embedding and BM25 ranking
            "searchText": search_text,
            # url = VI embed player — loads just the player (no portal shell), works in iframe
            "url": player_url,
            # viInsightsUrl = VI embed — use inside an iframe for split-pane HTML demo
            "viInsightsUrl": insights_url,
        }
        documents.append(doc)

    return video_name, documents


def save_local(video_name: str, documents: list[dict]) -> str:
    out_path = Path(f"{video_name}_segments.json")
    out_path.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved → {out_path}  ({len(documents)} scenes)")
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transform_vi_to_segments.py <vi_json_file>")
        sys.exit(1)

    video_name, docs = transform(sys.argv[1])
    save_local(video_name, docs)

    print("\nSample — scene 1:")
    print(json.dumps(docs[0], indent=2))

    print("\nAll scenes summary:")
    for d in docs:
        print(
            f"  scene {d['sceneId']}  {d['startTimeMs']/1000:.1f}s–{d['endTimeMs']/1000:.1f}s"
        )
        print(f"    labels:    {d['labels']}")
        print(f"    brands:    {d['brands']}")
        print(f"    locations: {d['locations']}")
        print(f"    topics:    {d['topics'][:2]}")
        print(f"    transcript: {d['transcript'][:80]}...")
