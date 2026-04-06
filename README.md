---
title: NAB 2026 Video Index Pipeline
description: Execution instructions for the CLI and UI workflows that build video segment output files and upload results to Azure AI Search
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
estimated_reading_time: 6
---

## Overview

This workspace supports two ways to run the NAB 2026 video indexing flow:

* Batch CLI flow: builds final output from Video Indexer JSON and optional
  Content Understanding JSON
* Step-by-step UI flow: runs Video Indexer end to end and builds the final
  output without Content Understanding

The generated artifacts are written to:

* `video_index/<video_name>_vi_output.json`
* `video_index/<video_name>_final_output.json`

The main CLI entrypoint is `main.py`. The interactive workflow UI entrypoint is
`video_index_workflow_ui.py`.

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
* `requirements.txt`: Python dependencies for the CLI and Streamlit UI
* `video_index_workflow_ui.py`: Step-by-step UI for the full Video Indexer flow
* `src/build_all_final_outputs.py`: Batch builder for all videos
* `src/build_final_output.py`: Single-video final-output builder
* `src/index_builder.py`: Uploads final output JSON into Azure AI Search
* `src/video_indexer_api.py`: Reusable Azure Video Indexer REST wrapper
* `src/video_index_workflow.py`: Reusable workflow layer used by the UI

## Prerequisites

You need:

* Python 3
* The project virtual environment in `.venv`
* Python packages installed from `requirements.txt`
* Input files in `video_index/`
* Matching file names for each video

Install the required packages from the repository root:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Expected input naming:

```text
video_index/flight_simulator_vi_output.json
video_index/flight_simulator_cu_output.json
```

Optional video files can exist in `video/`, but final output generation only
requires the JSON inputs in `video_index/`.

> [!IMPORTANT]
> The step-by-step UI uses Video Indexer environment variables for token,
> upload, and index retrieval. The Azure AI Search step also requires Search
> and Azure OpenAI settings in `src/.env`.

## Generate Final Output

Run the pipeline from the repository root:

```bash
.venv/bin/python main.py
```

This uses the default folders:

* `video`
* `video_index`

If you want to pass them explicitly, run:

```bash
.venv/bin/python main.py --video-dir video --video-index-dir video_index
```

If you want to build a single video only, run:

```bash
.venv/bin/python main.py --video-name flight_simulator
```

Successful output looks like this:

```text
Saved → video_index/flight_simulator_final_output.json  (6 scenes)
Built flight_simulator_final_output.json: 6 segments, 6 with CU descriptions
```

## Build One Video Directly

If you want to run the single-video builder without the batch wrapper, use:

```bash
.venv/bin/python src/build_final_output.py \
  video_index/flight_simulator_vi_output.json
```

That command builds a VI-only final output file.

If you also want to merge a Content Understanding scene description, use:

```bash
.venv/bin/python src/build_final_output.py \
  video_index/flight_simulator_vi_output.json \
  --cu-json video_index/flight_simulator_cu_output.json
```

## Run The Step-By-Step UI

Start the interactive workflow UI from the repository root:

```bash
source .venv/bin/activate
streamlit run video_index_workflow_ui.py
```

The UI supports these steps:

1. Get a Video Indexer account token
2. Upload a local video file
3. Poll indexing status and save the raw VI JSON
4. Build the final output without CU descriptions
5. Upload the final output to Azure AI Search

The UI processes one video file at a time. Each step can run independently,
and you can retry any failed step without restarting the full workflow.

The selected video filename drives the canonical artifact names used by the
pipeline. The UI shows those expected artifact names, and it derives them
automatically:

* `video_index/<normalized_video_name>_vi_output.json`
* `video_index/<normalized_video_name>_final_output.json`

The UI keeps the interaction minimal. It does not expose the optional upload
settings from the Video Indexer REST API.

## Upload to Azure AI Search

Final output generation and Azure AI Search upload are separate steps.

After `main.py` creates the final JSON, upload it with:

```bash
.venv/bin/python src/index_builder.py \
  --input video_index/flight_simulator_final_output.json
```

If you want to recreate the index first, run:

```bash
.venv/bin/python src/index_builder.py \
  --input video_index/flight_simulator_final_output.json \
  --recreate-index
```

## Environment Variables

`main.py` does not require Azure environment variables for final JSON
generation.

Azure settings are only required when running `src/index_builder.py`.

You can use `src/.env.example` as the template for `src/.env`.

For the current Azure OpenAI resource in this workspace, use:

* `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small`
* `AZURE_OPENAI_EMBEDDING_DIMENSIONS=1536`

For Azure Video Indexer API calls, configure:

* `AZURE_VIDEO_INDEXER_API_BASE_URL`
* `AZURE_VIDEO_INDEXER_LOCATION`
* `AZURE_VIDEO_INDEXER_ACCOUNT_ID`
* `AZURE_VIDEO_INDEXER_SUBSCRIPTION_KEY`
* `AZURE_VIDEO_INDEXER_TIMEOUT_SECONDS`

Set `AZURE_VIDEO_INDEXER_TIMEOUT_SECONDS=300` for this workspace. Larger local
uploads such as `flight_simulator.mp4` can hit write timeouts when the client
uses a shorter request timeout.

## Azure Video Indexer REST Wrapper

The workspace includes a reusable Video Indexer REST client for future upload,
polling, and index download operations.

To validate the first step, get an account access token with:

```bash
.venv/bin/python src/video_indexer_api.py get-account-access-token
```

That command returns a safe JSON summary with the token length.

If you need a contributor-scoped token for write operations such as upload, run:

```bash
.venv/bin/python src/video_indexer_api.py get-account-access-token \
  --allow-edit
```

If you need the raw token for manual chaining, run:

```bash
.venv/bin/python src/video_indexer_api.py get-account-access-token \
  --print-token
```

To upload a local video file and let the client request a contributor-scoped
token automatically, run:

```bash
.venv/bin/python src/video_indexer_api.py upload-video \
  --file video/flight_simulator.mp4 \
  --name flight-simulator-upload
```

Uploads default to `Public` privacy unless you explicitly override `--privacy`.

In the step-by-step UI and the end-to-end CLI flow, the Video Indexer display
name defaults to the normalized file name. For example,
`flight_simulator.mp4` uses the display name `flight_simulator`. The pipeline
output files still use the canonical local names:
`flight_simulator_vi_output.json` and `flight_simulator_final_output.json`.

To process one local video end to end, upload it, wait for indexing to finish,
and save the raw Video Indexer JSON into `video_index/`, run:

```bash
.venv/bin/python src/process_video_indexer_end_to_end.py \
  --video-file video/flight_simulator.mp4 \
  --output-video-name flight_simulator \
  --video-indexer-name flight-simulator-upload \
  --overwrite
```

That command writes `video_index/flight_simulator_vi_output.json`.

Use `--output-video-name` to control the saved pipeline filename. Use
`--video-indexer-name` when you want the uploaded Video Indexer display name to
be different from the saved local filename.

The upload response includes `id`, which is the Video Indexer video id used for
status polling and index download.

To check the current indexing state and percentage completion, run:

```bash
.venv/bin/python src/video_indexer_api.py get-video-status \
  --video-id swo33fsr52
```

To wait until indexing completes and save the full Video Indexer JSON into
`video_index/` using the pipeline naming convention, run:

```bash
.venv/bin/python src/video_indexer_api.py wait-for-video-index \
  --video-id swo33fsr52 \
  --output-video-name flight_simulator
```

That command writes `video_index/flight_simulator_vi_output.json`.

If indexing is already complete and you only want to download the full JSON,
run:

```bash
.venv/bin/python src/video_indexer_api.py download-video-index \
  --video-id swo33fsr52 \
  --output-video-name flight_simulator
```

You can also provide `--description`, `--language`, `--privacy`,
`--indexing-preset`, `--streaming-preset`, and the other supported upload query
parameters from the Video Indexer REST API.

If you pass `--access-token` to `upload-video`, it must be a contributor-scoped
token. Reader tokens can fetch data, but they cannot upload media.

For `wait-for-video-index` and `download-video-index`, use
`--output-video-name` when the uploaded Video Indexer display name differs from
the local video file stem that the downstream pipeline expects.

## Current Flow

Use one of these sequences when running the pipeline:

### Batch CLI Flow

1. Place `*_vi_output.json` and optional `*_cu_output.json` files in
   `video_index/`
2. Run `.venv/bin/python main.py`
3. Confirm that `*_final_output.json` was created in `video_index/`
4. Run `.venv/bin/python src/index_builder.py --input <final_output_file>` if
  you want to upload the results to Azure AI Search

### Step-By-Step UI Flow

1. Run `streamlit run video_index_workflow_ui.py`
2. Trigger the token and upload steps from the UI
3. Run the index retrieval step to save `*_vi_output.json`
4. Run the final-output step to save `*_final_output.json` without CU
5. Run the Azure AI Search step if you want to upload the generated output
