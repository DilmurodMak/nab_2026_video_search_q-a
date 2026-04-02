# Option C: Video Q&A and Search — Progress Log

**Approach:** Azure Content Understanding → Azure AI Search → Foundry IQ Agent

---

## What We Are Building

A walk-up conference demo where visitors type natural-language questions (e.g. *"Find scenes with crowd noise"*) and receive timestamped video segments they can click and immediately play — powered by Azure Content Understanding, Azure AI Search vector index, and a Foundry IQ agent with GPT-4.1.

---

## Steps Completed

### ✅ Step 1 — Analysed Option C requirements and evaluated approaches

- Reviewed NAB_Requirements.md Option C (Video Content Q&A and Search)
- Reviewed spike sketch (Video Indexer path vs Content Understanding path)
- **Decision:** Drop Video Indexer as primary path — Power Automate and Logic Apps connectors are blocked by organisational policy. Content Understanding + AI Search is the viable path.
- **Further decision:** Drop "Bypass AI Search" approach — without vector/semantic search, free-text Q&A does not work reliably.
- Produced `Architecture_Option_C.md` with full Mermaid diagram, tech stack, and Foundry IQ rationale.
- Populated `resources.md` with latest official documentation links for all services.

---

### ✅ Step 2 — Confirmed Content Understanding output structure

- Ran `prebuilt-videoAnalyzer` against `flight_simulator.mp4`
- Output saved to `indexed-video` container: `flight_simulator_content_understanding_output.json`
- Output contains per-segment: `SegmentId`, `StartTimeMs`, `EndTimeMs`, `Description`, WEBVTT transcript, keyframe timestamps
- **Gap identified:** Content Understanding does **not** store the source video URL in its output — `videoUrl` and `seekUrl` must be injected during the index build step

**Fix pattern (to implement in index builder):**
```python
VIDEO_BASE_URL = "https://nabmaksg.blob.core.windows.net/raw-video"
CONTAINER_SAS  = "<token from .env>"

video_url = f"{VIDEO_BASE_URL}/flight_simulator.mp4?{CONTAINER_SAS}"
seek_url  = f"{video_url}#t={start_time_ms / 1000:.1f}"
```

---

### ✅ Step 3 — Diagnosed Azure Storage access restrictions

Two organisation-level policies are active on storage account `nabmaksg`:

| Policy | Status | Impact |
|---|---|---|
| Allow Blob Public Access | ❌ Disabled (locked by policy) | Cannot make container publicly readable |
| Allow Shared Key Access | ❌ Disabled | Blocks account-key SAS and Storage Explorer key auth |
| User Delegation SAS | ✅ Works | Signed by Entra identity — not affected by either policy |

---

### ✅ Step 4 — Generated User Delegation SAS for `raw-video` container

Generated a container-level SAS token valid for 7 days (maximum allowed for User Delegation SAS):

```bash
az storage container generate-sas \
  --account-name nabmaksg \
  --name raw-video \
  --permissions rl \
  --expiry 2026-04-08T15:53Z \
  --auth-mode login \
  --as-user \
  --https-only \
  --output tsv
```

- **One token works for all `.mp4` files in the container** — just swap the filename
- Token stored in `.env` as `CONTAINER_SAS`
- `seekUrl` pattern: `{VIDEO_BASE_URL}/{file}.mp4?{CONTAINER_SAS}#t={seconds}`
- `#t=` fragment is handled entirely by the browser — Azure never sees it

---

### ✅ Step 5 — Validated video streaming from blob storage

```
HTTP/1.1 200 OK
Content-Type: video/mp4
Accept-Ranges: bytes          ← range requests work → browser can seek to #t=
Content-Length: 38598427
```

Video confirmed playing in browser via SAS URL. **Note: slow initial load** — see open item below.

---

### ✅ Step 6 — Set up Python environment and .env

- Activated `.venv` with `uv`
- Installed packages: `azure-ai-contentunderstanding`, `azure-search-documents`, `azure-identity`, `openai`, `python-dotenv`, `requests`
- `.env` file configured with all required variables

---

### ✅ Step 7 — Switched to Video Indexer (VI) for NAB pipeline

- Pivoted from Content Understanding to VI-only approach
- VI provides broadcast-relevant signals: brands (OCR), labels (aircraft/aviation), named locations, topics, keywords, detected objects
- `transform_vi_to_segments.py` written: converts raw VI JSON → flat scene array with all signals merged per scene window
- `flight_simulator_vi_segments.json` produced: 6 scenes, key demo moment in scene 6 (`brands: ["Airbus"]`, `locations: ["Orlando Ground"]`, `labels: [aircraft, jet engine...]`)
- `index_builder.py` written with VI schema: Collection(Edm.String) fields for labels/brands/locations, HNSW vector search, semantic ranker on `searchText` + `transcript`

---

### ✅ Step 8 — Fixed Azure AI Search indexing permissions

The portal "Import and vectorize data" wizard failed with API key error because **API key authentication is disabled** on the Azure OpenAI resource (`makfoundrywestus`).

**Fix — two changes required:**

**1. Enable system-assigned managed identity on AI Search**
- AI Search resource → **Settings** → **Identity** → System assigned → **On** → Save

**2. Assign role on the Foundry/OpenAI resource**
- Azure Portal → OpenAI resource **makfoundrywestus** → **Access control (IAM)**
- **+ Add role assignment** → **Cognitive Services OpenAI User**
- Assign to: **Managed identity** → select the AI Search resource

This allows AI Search to call the embedding model using its managed identity (no API key needed).

**3. `index_builder.py` updated to use `DefaultAzureCredential`**
- Removed `api_key` from `AzureOpenAI` client
- Added `get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")`
- Set `AZURE_OPENAI_ENDPOINT=https://makfoundrywestus.openai.azure.com/` in `.env`
- `AZURE_OPENAI_API_KEY` left empty — not needed

---

## Open Items — Next Steps

| # | Task | Notes |
|---|---|---|
| 1 | **Fix slow video load — faststart** | Re-upload videos with `+faststart` flag: `ffmpeg -i input.mp4 -c copy -movflags +faststart output.mp4`. Moves MP4 metadata to front so browser can play before full download. |
| 1b | **Fix slow video load — CDN** *(later)* | Add Azure CDN endpoint in front of `nabmaksg.blob.core.windows.net` for conference floor edge caching. SAS URL pattern works through CDN unchanged. Do after index is built and validated. |
| 2 | **Build AI Search index** | Write index builder script: read CU JSON from `indexed-video`, inject `videoUrl` + `seekUrl`, embed `description` + transcript, push to `nab-video-segments` index |
| 3 | **Fill `.env` values** | Still need: `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `AZURE_CU_ENDPOINT`, `AZURE_CU_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| 4 | **Register AI Search in Foundry IQ** | New Foundry portal → Build → Knowledge → add `nab-video-segments` as knowledge source → create `nab-video-kb` knowledge base |
| 5 | **Create Foundry Agent** | GPT-4.1, connect `nab-video-kb`, apply system prompt that cites `seekUrl` as clickable Markdown link |
| 6 | **Process remaining demo videos** | Run CU analyzer on all NAB demo videos, save output to `indexed-video`, add to index |
| 7 | **Refresh SAS token before NAB** | Expires 2026-04-08. Regenerate with same `az storage container generate-sas` command, update `.env`, re-run index builder |

---

## Key Files

| File | Purpose |
|---|---|
| `.env` | All credentials and config |
| `spike/Architecture_Option_C.md` | Full architecture, Mermaid diagram, Foundry IQ rationale |
| `spike/resources.md` | Official documentation links for all services |
| `flight_simulator_content_understanding_output.json` | Working CU output — reference for index builder schema |
| `flight_simulator_vi_output.json` | Video Indexer output — kept for reference only, not used in pipeline |
