"""
transform_vi_to_segments.py

Transforms a Video Indexer JSON output into a flat array of scene-level documents
ready for Azure AI Search ingestion (parsingMode: jsonArray).

Each document = one VI scene with all signals merged in:
  - transcript phrases overlapping the scene window
  - visual labels (aircraft, sky, cloud ...)
  - brands detected via OCR (Airbus ...)
  - named locations (Orlando Ground ...)
  - keywords extracted from speech
  - topics (NLP, AI, Machine Learning ...)
  - detected objects

The "url" field is a Video Indexer insights embed URL seeked to the scene start.
It is used by Copilot Studio / Foundry IQ as the citation link — clicking it opens
the VI player with transcript, faces, labels, and brands sidebar at the exact moment.

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


def overlaps(
    inst_start_ms: int, inst_end_ms: int, win_start_ms: int, win_end_ms: int
) -> bool:
    """True if [inst_start, inst_end) overlaps [win_start, win_end)."""
    return inst_start_ms < win_end_ms and inst_end_ms > win_start_ms


def collect_insights(
    insight_list: list,
    win_start_ms: int,
    win_end_ms: int,
    name_key: str = "name",
    min_confidence: float = 0.0,
) -> list[str]:
    """
    For any VI insight array (labels, brands, locations, keywords, topics),
    return the names/text of items whose instances overlap the time window.
    Deduplicates and filters by confidence.
    """
    results = []
    for item in insight_list:
        confidence = item.get("confidence", 1.0)
        if confidence < min_confidence:
            continue
        name = item.get(name_key) or item.get("text", "")
        if not name:
            continue
        for inst in item.get("instances", []):
            s = ts_to_ms(inst["adjustedStart"])
            e = ts_to_ms(inst["adjustedEnd"])
            if overlaps(s, e, win_start_ms, win_end_ms):
                results.append(name)
                break  # found one overlap — don't duplicate the same item
    return list(dict.fromkeys(results))  # preserve order, deduplicate


def collect_transcript(
    transcript_list: list, win_start_ms: int, win_end_ms: int
) -> str:
    """Collect transcript phrases that overlap this window, joined as a sentence."""
    phrases = []
    for item in transcript_list:
        for inst in item.get("instances", []):
            s = ts_to_ms(inst["adjustedStart"])
            e = ts_to_ms(inst["adjustedEnd"])
            if overlaps(s, e, win_start_ms, win_end_ms):
                phrases.append(item["text"])
                break
    return " ".join(phrases)


# ---------------------------------------------------------------------------
# Main transform
# ---------------------------------------------------------------------------


def transform(vi_json_path: str) -> tuple[str, list[dict]]:
    with open(vi_json_path, "r") as f:
        data = json.load(f)

    # Video name from the VI metadata (or from filename as fallback)
    video_name = data.get("name") or Path(vi_json_path).stem.replace("_vi_output", "")

    # VI account and video IDs for insights embed URLs
    vi_account_id = data.get("accountId", "")
    vi_video_id = data.get("id", "")
    vi_base = "https://www.videoindexer.ai/embed"

    insights = data["videos"][0]["insights"]

    scenes = insights.get("scenes", [])
    transcript_list = insights.get("transcript", [])
    labels_list = insights.get("labels", [])
    brands_list = insights.get("brands", [])
    locations_list = insights.get("namedLocations", [])
    keywords_list = insights.get("keywords", [])
    topics_list = insights.get("topics", [])
    objects_list = insights.get("detectedObjects", [])

    documents = []

    for scene in scenes:
        scene_id = scene["id"]
        inst = scene["instances"][0]
        start_ms = ts_to_ms(inst["adjustedStart"])
        end_ms = ts_to_ms(inst["adjustedEnd"])
        seek_time = start_ms / 1000.0

        # --- collect all signals for this window ---
        transcript = collect_transcript(transcript_list, start_ms, end_ms)
        labels = collect_insights(
            labels_list, start_ms, end_ms, name_key="name", min_confidence=0.7
        )
        brands = collect_insights(
            brands_list, start_ms, end_ms, name_key="name", min_confidence=0.0
        )
        locations = collect_insights(
            locations_list, start_ms, end_ms, name_key="name", min_confidence=0.0
        )
        keywords = collect_insights(
            keywords_list, start_ms, end_ms, name_key="text", min_confidence=0.5
        )
        topics = collect_insights(
            topics_list, start_ms, end_ms, name_key="name", min_confidence=0.6
        )
        objects = collect_insights(
            objects_list, start_ms, end_ms, name_key="object", min_confidence=0.7
        )

        # --- build rich searchText: the field that gets embedded and ranked ---
        # Ordering: transcript first (highest signal), then visual labels/brands,
        # then topics, then locations — drives semantic search quality.
        search_parts = []
        if transcript:
            search_parts.append(f"Transcript: {transcript}")
        if labels:
            search_parts.append(f"Visual: {', '.join(labels)}")
        if brands:
            search_parts.append(f"Brands: {', '.join(brands)}")
        if locations:
            search_parts.append(f"Locations: {', '.join(locations)}")
        if topics:
            search_parts.append(f"Topics: {', '.join(topics)}")
        if keywords:
            search_parts.append(f"Keywords: {', '.join(keywords)}")
        if objects:
            search_parts.append(f"Objects: {', '.join(objects)}")

        search_text = ". ".join(search_parts)

        doc = {
            "id": f"{video_name}_scene_{scene_id}",
            "videoName": video_name,
            "sceneId": str(scene_id),
            "startTimeMs": start_ms,
            "endTimeMs": end_ms,
            # individual signal fields for filtering / faceting in AI Search
            "transcript": transcript,
            "labels": labels,
            "brands": brands,
            "locations": locations,
            "keywords": keywords,
            "topics": topics,
            # rich text field for vector embedding and BM25 ranking
            "searchText": search_text,
            # url = VI embed player — loads just the player (no portal shell), works in iframe
            "url": f"https://www.videoindexer.ai/embed/player/{vi_account_id}/{vi_video_id}?t={seek_time:.0f}&location=trial",
            # viInsightsUrl = VI embed — use inside an iframe for split-pane HTML demo
            "viInsightsUrl": f"https://www.videoindexer.ai/embed/insights/{vi_account_id}/{vi_video_id}/?t={seek_time:.0f}",
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
