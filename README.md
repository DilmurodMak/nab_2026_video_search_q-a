---
title: NAB 2026 Video Index Pipeline
description: Simple run guide for the NAB 2026 video indexing app and optional CLI tools
author: GitHub Copilot
ms.date: 2026-04-06
ms.topic: how-to
keywords:
  - video indexer
  - content understanding
  - azure ai search
  - python
  - nab 2026
  - streamlit
estimated_reading_time: 4
---

## Overview

The primary entrypoint for this repo is `video_index_workflow_ui.py`.

It runs the full flow for one local video file at a time:

1. Upload to Video Indexer
2. Wait for indexing to finish
3. Save the raw VI JSON
4. Build the final output without CU
5. Upload the final output to Azure AI Search

The app writes these files to `video_index/`:

* `video_index/<normalized_video_name>_vi_output.json`
* `video_index/<normalized_video_name>_final_output.json`



## Run The App

Use this checklist:

* [ ] Activate the virtual environment in `.venv`
* [ ] Install dependencies with `python -m pip install -r requirements.txt`
* [ ] Put at least one supported video file in `video/`

Required in `src/.env` for the Video Indexer steps:

```text
AZURE_VIDEO_INDEXER_LOCATION
AZURE_VIDEO_INDEXER_ACCOUNT_ID
AZURE_VIDEO_INDEXER_SUBSCRIPTION_KEY
AZURE_VIDEO_INDEXER_TIMEOUT_SECONDS=300
```

Required in `src/.env` only if you want to run the final Azure AI Search step:

```text
AZURE_SEARCH_ENDPOINT
AZURE_SEARCH_API_KEY
AZURE_SEARCH_INDEX_NAME
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
AZURE_OPENAI_EMBEDDING_DIMENSIONS
```

Sign in to Azure locally before using the final Azure AI Search step so
`DefaultAzureCredential` can request embeddings.

Start the app from the repository root:

```bash
source .venv/bin/activate
streamlit run video_index_workflow_ui.py
```

## What The App Shows

The app is intentionally minimal:

* One selected video file at a time
* Expected output names before you run
* Step-by-step buttons with retry support
* A full workflow button
* The Azure AI Search index name currently configured in `src/.env`

## Notes

* Uploads default to `Public` privacy
* The Video Indexer display name defaults to the normalized file name
* `flight_simulator.mp4` becomes `flight_simulator` in Video Indexer
* The saved pipeline files still use the canonical local names:
  `flight_simulator_vi_output.json` and
  `flight_simulator_final_output.json`

## Optional CLI Commands

Use these only if you want lower-level control outside the app.

Build final output from an existing VI JSON file:

```bash
.venv/bin/python src/build_final_output.py \
  video_index/flight_simulator_vi_output.json
```

Upload a final output file to Azure AI Search:

```bash
.venv/bin/python src/index_builder.py \
  --input video_index/flight_simulator_final_output.json
```

Upload a local video directly to Video Indexer:

```bash
.venv/bin/python src/video_indexer_api.py upload-video \
  --file video/flight_simulator.mp4 \
  --name flight_simulator
```

Wait for indexing to finish and save the raw VI JSON:

```bash
.venv/bin/python src/video_indexer_api.py wait-for-video-index \
  --video-id swo33fsr52 \
  --output-video-name flight_simulator
```

