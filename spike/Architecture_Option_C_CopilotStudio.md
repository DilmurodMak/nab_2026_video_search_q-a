# Option C: Video Content Q&A and Search — Copilot Studio Variant

## Overview

Alternative delivery path for the NAB 2026 demo using **Microsoft Copilot Studio** as the agent layer instead of Foundry IQ. Shares the same AI Search index and CU pipeline with the primary Foundry IQ architecture. The pivot is at the agent/UI layer only — no pipeline changes required.

Two paths are documented:

- **Path A — Copilot Studio Webchat (Recommended for NAB)**: Natural-language chat agent backed by AI Search, published as a webchat URL. Timestamp citations open video in browser at exact seek position.
- **Path B — Power Apps Canvas App with Custom Connector**: Search box + results gallery + embedded Video control for a fully in-app experience.

---

## Why Copilot Studio Instead of Foundry IQ

| Factor | Foundry IQ | Copilot Studio |
|---|---|---|
| Status | Public Preview | GA |
| AI Search knowledge source | ✅ Native | ✅ Native (key or Entra auth) |
| Publish to webchat/Teams | ✅ | ✅ |
| Power Apps embed | ❌ Not supported | ⚠️ Canvas Copilot control deprecated Feb 2026 |
| No Power Automate needed | ✅ | ✅ |
| LLM for grounding | GPT-4.1 via Foundry | GPT-4o (platform-managed) |
| Citation field mapping | `seekUrl` field in index | Field named `url` or `metadata_storage_path` in index |
| Topic authoring / guardrails | Via system prompt | Via Topics + Generative Answers node |

**Both paths read from the same `nab-video-segments` AI Search index.** No pipeline changes needed to support either option.

> **Important**: The Power Apps Canvas Copilot control (embedded chat bubble in canvas apps) was deprecated as of **February 2, 2026**. New canvas apps cannot use it. Path B uses a custom connector approach instead, which is fully supported.

---

## Shared Prerequisites (Same as Primary Architecture)

These must be completed before either Copilot Studio path works:

1. CU JSON files stored in `indexed-video` blob container (one JSON per video)
2. Python index builder run → `nab-video-segments` AI Search index populated with:
   - `id`, `videoName`, `segmentId`
   - `description` (CU segment description)
   - `startTimeMs`, `endTimeMs`
   - `seekUrl` / `url` (playback URL + `#t={seconds}` fragment, **must be named `url` for Copilot Studio citations**)
   - `content_vector` (embedding of description + transcript)
3. `.env` values filled: `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`

---

## Path A — Copilot Studio Webchat

### Architecture

```
Azure Blob Storage (indexed-video)
        │ CU JSON per video
        ▼
Python Index Builder (local)
   - builds url field from playback URL + `#t=` fragment
  - embeds description + transcript
        │
        ▼
Azure AI Search  ──────────────────────────────────────────┐
  Index: nab-video-segments                                 │
  Fields: id, videoName, description,                       │ Knowledge Source
          startTimeMs, endTimeMs,                           │ (key auth)
          url (seekUrl), content_vector                     │
                                                            ▼
                                              Copilot Studio Agent
                                              - Generative Answers node
                                              - Grounded on nab-video-segments
                                              - Citations = url field value
                                                            │
                                                            ▼
                                              Published Webchat (iframe / URL)
                                                            │
                                              User asks: "Show me takeoff scenes"
                                              Agent replies: description + clickable seekUrl
                                                            │
                                              User clicks → browser opens
                                              video.mp4?SAS#t=7.4 → plays at 7.4s
```

### Step-by-Step Build Guide

#### Step 1 — Ensure `url` field is in AI Search index

Copilot Studio uses the field named **`url`** (or `metadata_storage_path`) as the citation link. Rename `seekUrl` → `url` in the index schema and index builder script.

```python
doc = {
    "id": f"{video_name}_seg_{segment_id}",
    "videoName": video_name,
    "segmentId": segment_id,
    "description": segment["description"],
    "startTimeMs": segment["startTimeMs"],
    "endTimeMs": segment["endTimeMs"],
    "url": seek_url,          # ← must be "url" for Copilot Studio citations
    "content_vector": embed(text)
}
```

#### Step 2 — Create the Copilot Studio Agent

1. Go to [https://copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Select **Create** → **New agent**
3. Name: `NAB Video Search`
4. Description: `Answers questions about conference demo videos and returns timestamped clips`
5. Select **Skip to configure** (do not use the AI setup wizard for the knowledge source — add it manually)

#### Step 3 — Add Azure AI Search as Knowledge Source

1. Open the agent → **Knowledge** tab → **Add knowledge**
2. Select **Featured** → **Azure AI Search**
3. Select **Create new connection**
4. Authentication type: **Access Key**
5. Enter:
   - **Azure AI Search Endpoint URL**: `https://<your-search-service>.search.windows.net`
   - **Azure AI Search Admin Key**: from `.env` `AZURE_SEARCH_API_KEY`
6. Select **Create** → green check confirms connection
7. Select **Next**
8. Enter index name: `nab-video-segments`
9. Select **Add to agent**

Knowledge source status shows **In progress** then **Ready** (takes a few minutes for metadata indexing).

#### Step 4 — Configure Generative Answers

1. Go to **Topics** → **System** → **Conversational boosting**
2. Open the **Generative Answers** node
3. Confirm the `nab-video-segments` knowledge source is selected
4. Set **Content moderation**: Medium
5. In agent **Settings** → **Generative AI** → turn on **Generative orchestration**

#### Step 5 — Apply System Prompt

In agent **Settings** → **Generative AI** → **Instructions**, enter:

```
You are a video search assistant for NAB 2026 conference demos.
When a user asks about video content, search the knowledge base and return relevant video segments.
For each result, include:
- A one-sentence description of what happens in the segment
- The timestamp range (startTimeMs to endTimeMs in seconds)
- A clickable link using the url field so the user can watch the clip

Always cite your sources. If no relevant segment is found, say so clearly.
Do not answer questions outside the scope of the demo video library.
```

#### Step 6 — Test the Agent

1. In Copilot Studio **Test** panel, ask:
   - `"Show me scenes with aircraft takeoff"`
   - `"Find segments mentioning Airbus"`
   - `"What happens at the beginning of flight simulator?"`
2. Confirm each response includes a citation with a URL (the `seekUrl` / `#t=` link)

#### Step 7 — Publish

1. **Publish** tab → **Publish** → confirm
2. **Channels** → **Demo Website** (or **Custom website** for iframe embed)
3. Copy the webchat URL or `<iframe>` snippet
4. Open in browser — demo is live

---

## Path B — Power Apps Canvas App with Custom Connector

### Architecture

```
Azure AI Search (nab-video-segments)
        ▲
        │ REST API (api-key header)
        │
Power Platform Custom Connector
  - Base URL: https://<search>.search.windows.net
  - Action: POST /indexes/nab-video-segments/docs/search
  - Header: api-key: {AZURE_SEARCH_API_KEY}
        │
        ▼
Power Apps Canvas App
  ┌─────────────────────────────────────────┐
  │  [TextInput]  [Search Button]           │
  │                                         │
  │  Gallery (results):                     │
  │    ● videoName                          │
  │    ● description                        │
  │    ● startTime / endTime                │
  │    ● [Watch Clip] button                │
  │                                         │
  │  Video Control:                         │
  │    Media = Gallery.Selected.url         │
  │    (opens video at seekUrl#t=)          │
  └─────────────────────────────────────────┘
```

### Step-by-Step Build Guide

#### Step 1 — Create the Custom Connector

1. Go to [https://make.powerapps.com](https://make.powerapps.com) → your environment
2. Left nav → **... More** → **Custom connectors** → **New custom connector** → **Create from blank**
3. Name: `AzureAISearch-NAB`
4. **General** tab:
   - Host: `<your-search-service>.search.windows.net`
   - Base URL: `/`
5. **Security** tab:
   - Authentication type: **API Key**
   - Parameter label: `api-key`
   - Parameter name: `api-key`
   - Parameter location: **Header**
6. **Definition** tab → **New action**:
   - Summary: `Search video segments`
   - Operation ID: `SearchVideoSegments`
   - Verb: **POST**
   - URL: `/indexes/nab-video-segments/docs/search?api-version=2024-07-01`
   - Request body (sample JSON):
     ```json
     {
       "search": "aircraft takeoff",
       "queryType": "semantic",
       "semanticConfiguration": "default",
       "top": 5,
       "select": "id,videoName,description,startTimeMs,endTimeMs,url"
     }
     ```
7. **Test** tab → Create connection → enter admin API key → run test query
8. **Create connector** → green check

#### Step 2 — Build the Canvas App

1. [https://make.powerapps.com](https://make.powerapps.com) → **Create** → **Blank canvas app** → Phone layout
2. Add the custom connector as a data source:
   - **Data** panel → **Add data** → search `AzureAISearch-NAB` → connect

#### Step 3 — Add Controls

**Search bar:**
```
Insert → Text input → Name: txtQuery
Insert → Button → Text: "Search" → Name: btnSearch
```

**Button `OnSelect` formula:**
```
ClearCollect(
    colResults,
    AzureAISearch_NAB.SearchVideoSegments({
        search: txtQuery.Text,
        queryType: "semantic",
        semanticConfiguration: "default",
        top: 5,
        select: "id,videoName,description,startTimeMs,endTimeMs,url"
    }).value
)
```

**Results Gallery:**
```
Insert → Gallery → Vertical → Name: galResults
Items: colResults

In gallery template:
  - Label1.Text: ThisItem.videoName
  - Label2.Text: ThisItem.description
  - Label3.Text: "▶ " & Text(ThisItem.startTimeMs/1000, "[$-en-US]0.0") & "s"
   - Button "Watch" → OnSelect: Set(varClipUrl, ThisItem.url)
```

**Video control:**
```
Insert → Media → Video → Name: videoPlayer
Media: varClipUrl
```

> **Note on video playback**: The Power Apps Video control docs state external videos must be accessible anonymously. SAS URLs embed the token in the query string (no browser auth challenge) and work in most cases, but are not officially supported. For guaranteed compatibility, use Azure CDN with a custom domain or a public container for demo purposes.

#### Step 4 — Style and Publish

1. Adjust layouts, colours, and fonts as needed for NAB branding
2. **File** → **Save** → **Publish**
3. Share with demo team: **File** → **Share** → add users or "Everyone in organization"

---

## Comparison: Path A vs Path B

| Criteria | Path A — Copilot Studio Webchat | Path B — Power Apps |
|---|---|---|
| Power Automate dependency | None | None |
| Video player embedded | ❌ Opens in separate browser tab | ✅ In-app video control |
| Search experience | ✅ Natural language chat | ❌ Keyword/semantic search box |
| Build time | ~2 hours | ~1 day |
| Deprecated components | None | None |
| Video streaming risk | Low — browser handles SAS natively | Medium — Power Apps anonymous video requirement |
| Requires custom connector | No | Yes |
| Best for | Conference Q&A demo — AI chat feel | Product showcase — visual gallery + player |
| URL for demo | Single webchat URL (shareable) | Published app link (requires PP license) |

---

## Comparison: Copilot Studio vs Foundry IQ (Current Primary Plan)

| Criteria | Copilot Studio (this doc) | Foundry IQ (primary plan) |
|---|---|---|
| Status | GA | Public Preview |
| AI Search as knowledge source | ✅ GA feature | ✅ Preview feature |
| Citation field | Must be named `url` in index | `seekUrl` — any field name configurable |
| LLM model choice | Platform-managed (GPT-4o) | GPT-4.1 (your Foundry deployment) |
| Publish channels | Webchat, Teams, custom website | Foundry Playground, custom API |
| Topic / flow authoring | ✅ Full topic designer | ❌ Agent prompt only |
| Build time to live demo | ~2 hours | ~2 hours |
| Org policy blockers | None | None |
| Same AI Search index | ✅ Yes | ✅ Yes |

**Both options use the exact same index** — you can build both and demo either, or let the team decide at the event.

---

## Key Constraint: Citation Field Naming

Copilot Studio returns citations based on a specific field name convention:

1. If the index has a field named **`metadata_storage_path`** → used as citation URL (blob indexer pattern)
2. Otherwise, the first field that contains a **complete URL** → used as citation

To be explicit and reliable, name the field **`url`** in your index schema and ensure the value is the full `seekUrl` (including `#t=` fragment and SAS token). This is the only change needed to the index builder script if switching from Foundry IQ to Copilot Studio.

---

## References

- [Add Azure AI Search as a knowledge source in Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-azure-ai-search) *(Updated Jan 2026)*
- [Copilot Studio knowledge sources overview](https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-copilot-studio) *(Updated Jan 2026)*
- [Power Apps Audio and Video controls](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/controls/control-audio-video)
- [Power Apps custom connectors overview](https://learn.microsoft.com/en-us/connectors/custom-connectors/)
- [Create a custom connector from an OpenAPI definition](https://learn.microsoft.com/en-us/connectors/custom-connectors/define-openapi-definition)
- [Copilot Studio — Publish to demo website](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-connect-bot-to-web-channels)
- [Azure AI Search REST API reference](https://learn.microsoft.com/en-us/rest/api/searchservice/)
