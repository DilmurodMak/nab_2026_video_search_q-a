---
title: NAB 2026 Video Index Pipeline
description: Execution instructions for generating final video segment output files and optionally uploading them to Azure AI Search
author: GitHub Copilot
ms.date: 2026-04-03
ms.topic: how-to
keywords:
  - video indexer
  - content understanding
  - azure ai search
  - python
  - nab 2026
estimated_reading_time: 4
---

## Overview

This workspace builds final video segment JSON files by combining:

* Video Indexer output in `video_index/<video_name>_vi_output.json`
* Content Understanding output in `video_index/<video_name>_cu_output.json`

The generated result is written to:

* `video_index/<video_name>_final_output.json`

The root entrypoint is `main.py`.

## Folder Layout

The pipeline expects this structure:

```text
video/
video_index/
src/
main.py
```

Important files:

* `main.py`: Runs the batch final-output generation flow
* `src/build_all_final_outputs.py`: Batch builder for all videos
* `src/build_final_output.py`: Single-video final-output builder
* `src/index_builder.py`: Uploads final output JSON into Azure AI Search

## Prerequisites

You need:

* Python 3
* Input files in `video_index/`
* Matching file names for each video

Expected input naming:

```text
video_index/flight_simulator_vi_output.json
video_index/flight_simulator_cu_output.json
```

Optional video files can exist in `video/`, but final output generation only
requires the JSON inputs in `video_index/`.

## Generate Final Output

Run the pipeline from the repository root:

```bash
python3 main.py
```

This uses the default folders:

* `video`
* `video_index`

If you want to pass them explicitly, run:

```bash
python3 main.py --video-dir video --video-index-dir video_index
```

If you want to build a single video only, run:

```bash
python3 main.py --video-name flight_simulator
```

Successful output looks like this:

```text
Saved → video_index/flight_simulator_final_output.json  (6 scenes)
Built flight_simulator_final_output.json: 6 segments, 6 with CU descriptions
```

## Build One Video Directly

If you want to run the single-video builder without the batch wrapper, use:

```bash
python3 src/build_final_output.py \
  video_index/flight_simulator_vi_output.json \
  --cu-json video_index/flight_simulator_cu_output.json
```

## Upload to Azure AI Search

Final output generation and Azure AI Search upload are separate steps.

After `main.py` creates the final JSON, upload it with:

```bash
python3 src/index_builder.py \
  --input video_index/flight_simulator_final_output.json
```

If you want to recreate the index first, run:

```bash
python3 src/index_builder.py \
  --input video_index/flight_simulator_final_output.json \
  --recreate-index
```

## Environment Variables

`main.py` does not require Azure environment variables for final JSON
generation.

Azure settings are only required when running `src/index_builder.py`.

You can use `src/.env.example` as the template for `src/.env`.

## Current Flow

Use this sequence when running the pipeline:

1. Place `*_vi_output.json` and optional `*_cu_output.json` files in
   `video_index/`
2. Run `python3 main.py`
3. Confirm that `*_final_output.json` was created in `video_index/`
4. Run `python3 src/index_builder.py --input <final_output_file>` if you want
   to upload the results to Azure AI Search
