---
title: Copilot Studio Native Video Indexer Flow
description: Build-from-scratch reference for the current Power Automate and Copilot Studio implementation, plus the grouped-moments upgrade that collapses duplicate timestamps per video.
author: GitHub Copilot
ms.date: 2026-04-10
ms.topic: how-to
keywords:
  - copilot studio
  - azure ai video indexer
  - power automate
  - adaptive card
  - enrichedpayloadjson
  - searchmatches
  - selectedvideoinsights
  - foundvideos
  - thumbnails
    - moments
    - dedupe
    - booth demo
    - prompt tuning
estimated_reading_time: 12
---

## Overview

This document captures the current NAB 2026 implementation and is written as a
first-time setup guide for rebuilding the flow and topic from scratch.

The flow still returns one top-level output, `enrichedpayloadjson`, and the
payload has four top-level fields:

| Field                   | Type        | Purpose |
|-------------------------|-------------|---------|
| `SearchQuery`           | String      | Original user query |
| `SearchMatches`         | JSON string | Flat match rows for the first returned video |
| `SelectedVideoInsights` | JSON string | Slim evidence object for the first returned video |
| `FoundVideos`           | JSON string | Top returned videos with one video-level thumbnail and grouped nested moments per video |

This split is intentional:

* `SearchMatches` and `SelectedVideoInsights` continue to power the AI summary
  and the detailed findings list
* `FoundVideos` powers thumbnail previews, matching-video rows, and grouped
    per-video moment data
* The summary node must ignore thumbnails and base64 image data
* `Moments` keeps duplicate timestamps collapsed without changing AI grounding

The current implementation already returns a native nested `Moments` array
inside each `FoundVideos` row. That lets you keep the AI summary path stable
while also supporting cleaner grouped rendering later.

> [!IMPORTANT]
> `ThumbnailDataUri` is a video-level preview image. It is not an exact
> timestamp-aligned thumbnail for the matching moment shown in the card.

> [!IMPORTANT]
> For booth demos, keep the flow, payload contract, and card structure fixed.
> Let presenters experiment with instruction text instead of rewiring the flow.

## First-Time Setup

Use this sequence when you are creating the solution for the first time.

### Before You Start

* Confirm Azure AI Video Indexer is available in the same Power Automate
    environment as your Copilot Studio agent.
* Confirm `Get Account Access Token` works before you build the rest of the
    flow.
* Decide whether you are using `trial` or another Video Indexer location and
    reuse that same location in every connector action and URL template.
* Create the Power Automate cloud flow from a blank flow by choosing
    `When an agent calls the flow`.
* Keep the output contract stable once the topic is wired:
    `SearchQuery`, `SearchMatches`, `SelectedVideoInsights`, and `FoundVideos`.
* Turn concurrency off on loops that reuse shared variables:
    `Apply_to_each_FoundVideo`, `Apply_to_each_CurrentVideoMoment`, and
    `Apply_to_each_CurrentMomentMatch`.

### Build Strategy

Build the flow once, validate the payload, and then treat the flow as stable.
For demos and booth exploration, change instructions before you change schema,
array shape, or adaptive card structure.

## Power Automate Build

### Top-Level Node Order

Build the top-level flow in this order:

| Order | Node name | Type | Purpose |
|-------|-----------|------|---------|
| 1 | `When an agent calls the flow` | Trigger | Accept `SearchQuery` |
| 2 | `Get Account Access Token` | Video Indexer connector | Get a read token |
| 3 | `Search Videos` | Video Indexer connector | Search the account |
| 4 | `Select` | Select | Optional lightweight debug shape |
| 5 | `Initialize_FoundVideos` | Initialize variable | Store per-video thumbnail rows |
| 6 | `Apply_to_each_FoundVideo` | Apply to each | Build `FoundVideos` |
| 7 | `Compose_SelectedVideo` | Compose | Capture the first returned video |
| 8 | `Compose_SelectedVideoMatchesRaw` | Compose | Keep all matches from the selected video |
| 9 | `Initialize_MatchRows` | Initialize variable | Store detailed finding rows |
| 10 | `Apply_to_each_SelectedVideoMatch` | Apply to each | Build `SearchMatches` |
| 11 | `Get_Video_Index_For_SelectedVideo` | Video Indexer connector | Get one full index payload |
| 12 | `Compose_SelectedVideoInsightsSlim` | Compose | Keep only evidence needed by the topic |
| 13 | `Compose_EnrichedPayload` | Compose | Package the final payload |
| 14 | `Return value(s) to Power Virtual Agents)` | Return | Return `enrichedpayloadjson` |

### Optional Select Step

Keep this step if you still want a lightweight debug shape in run history.
It is not required by the topic.

`From`:

```text
body('Search_Videos')?['results']
```

Map these fields:

```text
Name = item()?['name']
ID = item()?['id']
AccountId = item()?['accountId']
SearchMatches = item()?['searchMatches']
```

### First Validation Check

After you save the flow and run one test query, confirm these points in run
history before you move to Copilot Studio:

* `SearchQuery` is not blank in `Compose_EnrichedPayload`
* `SearchMatches` contains flat rows from the selected first video
* `FoundVideos` contains at least one row with a `ThumbnailDataUri`
* Each `FoundVideos` row contains a populated native `Moments` array
* At least one `Moments` row has non-empty `TypesText`, `TextsText`, and
    `DisplayText`

> [!NOTE]
> If `SearchQuery` comes back blank, cache the trigger input in a compose such
> as `Compose_SearchQueryInput` right after the trigger and reuse that output in
> both `Search Videos` and `Compose_EnrichedPayload`.

### FoundVideos Thumbnail Loop

This branch adds the per-video thumbnail preview data.

#### Initialize_FoundVideos

Type: Variables > Initialize variable

Use these values:

* Variable name: `FoundVideos`
* Variable type: `Array`
* Initial value:

```json
[]
```

#### Apply_to_each_FoundVideo

Type: Control > Apply to each

Loop input:

```text
take(body('Search_Videos')?['results'], 3)
```

Keep the limit at `3` unless you have already validated card size in Copilot
Studio.

#### Compose_CurrentVideoMatchesRaw

Type: Compose

Inputs:

```text
coalesce(
  items('Apply_to_each_FoundVideo')?['searchMatches'],
  json('[]')
)
```

#### Compose_CurrentVideoFirstMatch

Type: Compose

Inputs:

```text
if(
  equals(length(outputs('Compose_CurrentVideoMatchesRaw')), 0),
  json('{}'),
  first(outputs('Compose_CurrentVideoMatchesRaw'))
)
```

#### Compose_CurrentVideoFirstMatchSeconds

Type: Compose

Inputs:

```text
if(
  empty(outputs('Compose_CurrentVideoFirstMatch')?['startTime']),
  0,
  add(
    mul(int(split(outputs('Compose_CurrentVideoFirstMatch')?['startTime'], ':')[0]), 3600),
    add(
      mul(int(split(outputs('Compose_CurrentVideoFirstMatch')?['startTime'], ':')[1]), 60),
      float(split(outputs('Compose_CurrentVideoFirstMatch')?['startTime'], ':')[2])
    )
  )
)
```

#### Get_Video_Thumbnail_For_FoundVideo

Type: Azure Video Indexer connector

Use these values:

* Location: `trial`
* Account ID:

```text
items('Apply_to_each_FoundVideo')?['accountId']
```

* Video ID:

```text
items('Apply_to_each_FoundVideo')?['id']
```

* Thumbnail ID:

```text
coalesce(
  items('Apply_to_each_FoundVideo')?['thumbnailId'],
  items('Apply_to_each_FoundVideo')?['summarizedInsights']?['thumbnailId']
)
```

* Access Token: `Access Token` from `Get Account Access Token`

#### Compose_CurrentVideoThumbnailDataUri

Type: Compose

Inputs:

```text
if(
  empty(body('Get_Video_Thumbnail_For_FoundVideo')?['$content']),
  '',
  concat(
    'data:',
    body('Get_Video_Thumbnail_For_FoundVideo')?['$content-type'],
    ';base64,',
    body('Get_Video_Thumbnail_For_FoundVideo')?['$content']
  )
)
```

#### Append_to_FoundVideos

Type: Variables > Append to array variable

Variable name: `FoundVideos`

Value:

```json
{
  "VideoName": "@{items('Apply_to_each_FoundVideo')?['name']}",
  "VideoId": "@{items('Apply_to_each_FoundVideo')?['id']}",
  "AccountId": "@{items('Apply_to_each_FoundVideo')?['accountId']}",
  "ThumbnailId": "@{coalesce(items('Apply_to_each_FoundVideo')?['thumbnailId'], items('Apply_to_each_FoundVideo')?['summarizedInsights']?['thumbnailId'])}",
  "ThumbnailDataUri": "@{outputs('Compose_CurrentVideoThumbnailDataUri')}",
  "MatchCount": "@{length(outputs('Compose_CurrentVideoMatchesRaw'))}",
  "FirstMatchTime": "@{coalesce(outputs('Compose_CurrentVideoFirstMatch')?['startTime'], '')}",
  "FirstMatchText": "@{coalesce(outputs('Compose_CurrentVideoFirstMatch')?['text'], '')}",
  "FirstMatchType": "@{coalesce(outputs('Compose_CurrentVideoFirstMatch')?['type'], '')}",
  "FirstExactText": "@{coalesce(outputs('Compose_CurrentVideoFirstMatch')?['exactText'], '')}",
  "WatchUrl": "@{concat('https://www.videoindexer.ai/embed/player/', items('Apply_to_each_FoundVideo')?['accountId'], '/', items('Apply_to_each_FoundVideo')?['id'], '?t=', string(outputs('Compose_CurrentVideoFirstMatchSeconds')), '&location=trial')}",
  "InsightsUrl": "@{concat('https://www.videoindexer.ai/embed/insights/', items('Apply_to_each_FoundVideo')?['accountId'], '/', items('Apply_to_each_FoundVideo')?['id'], '/?t=', string(outputs('Compose_CurrentVideoFirstMatchSeconds')))}",
  "SearchMatchesJson": "@{string(outputs('Compose_CurrentVideoMatchesRaw'))}"
}
```

### Selected-Video Summary Branch

This branch stays close to the original build. It still uses the first returned
video as the selected video for the summary and the detailed findings list.

#### Compose_SelectedVideo

Type: Compose

Inputs:

```text
first(body('Search_Videos')?['results'])
```

#### Compose_SelectedVideoMatchesRaw

Type: Compose

Inputs:

```text
coalesce(
  outputs('Compose_SelectedVideo')?['searchMatches'],
  json('[]')
)
```

#### Initialize_MatchRows

Type: Variables > Initialize variable

Use these values:

* Variable name: `MatchRows`
* Variable type: `Array`
* Initial value:

```json
[]
```

#### Apply_to_each_SelectedVideoMatch

Type: Control > Apply to each

Loop input:

```text
outputs('Compose_SelectedVideoMatchesRaw')
```

Inside this loop, add the next two nodes.

#### Compose_MatchSeconds

Type: Compose

Inputs:

```text
add(
  mul(int(split(items('Apply_to_each_SelectedVideoMatch')?['startTime'], ':')[0]), 3600),
  add(
    mul(int(split(items('Apply_to_each_SelectedVideoMatch')?['startTime'], ':')[1]), 60),
    float(split(items('Apply_to_each_SelectedVideoMatch')?['startTime'], ':')[2])
  )
)
```

#### Append_to_MatchRows

Type: Variables > Append to array variable

Variable name: `MatchRows`

Value:

```json
{
  "VideoName": "@{outputs('Compose_SelectedVideo')?['name']}",
  "VideoId": "@{outputs('Compose_SelectedVideo')?['id']}",
  "AccountId": "@{outputs('Compose_SelectedVideo')?['accountId']}",
  "Time": "@{items('Apply_to_each_SelectedVideoMatch')?['startTime']}",
  "StartSeconds": "@{outputs('Compose_MatchSeconds')}",
  "MatchText": "@{items('Apply_to_each_SelectedVideoMatch')?['text']}",
  "MatchType": "@{items('Apply_to_each_SelectedVideoMatch')?['type']}",
  "ExactText": "@{items('Apply_to_each_SelectedVideoMatch')?['exactText']}",
  "WatchUrl": "@{concat('https://www.videoindexer.ai/embed/player/', outputs('Compose_SelectedVideo')?['accountId'], '/', outputs('Compose_SelectedVideo')?['id'], '?t=', string(outputs('Compose_MatchSeconds')), '&location=trial')}",
  "InsightsUrl": "@{concat('https://www.videoindexer.ai/embed/insights/', outputs('Compose_SelectedVideo')?['accountId'], '/', outputs('Compose_SelectedVideo')?['id'], '/?t=', string(outputs('Compose_MatchSeconds')))}"
}
```

#### Get_Video_Index_For_SelectedVideo

Type: Azure Video Indexer connector

Use these values:

* Location: `trial`
* Account ID:

```text
outputs('Compose_SelectedVideo')?['accountId']
```

* Video ID:

```text
outputs('Compose_SelectedVideo')?['id']
```

* Access Token: `Access Token` from `Get Account Access Token`
* Captions Language: `English`

#### Compose_SelectedVideoInsightsSlim

Type: Compose

Build this object in the Compose object designer:

| Property | Value |
|----------|-------|
| `VideoName` | `outputs('Compose_SelectedVideo')?['name']` |
| `VideoId` | `outputs('Compose_SelectedVideo')?['id']` |
| `Duration` | `body('Get_Video_Index_For_SelectedVideo')?['duration']` |
| `Transcript` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['transcript']` |
| `OCR` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['ocr']` |
| `Brands` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['brands']` |
| `Labels` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['labels']` |
| `Keywords` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['keywords']` |
| `DetectedObjects` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['detectedObjects']` |
| `Scenes` | `first(body('Get_Video_Index_For_SelectedVideo')?['videos'])?['insights']?['scenes']` |

### Compose_EnrichedPayload

Type: Compose

Build this object in the Compose object designer:

| Property | Value |
|----------|-------|
| `SearchQuery` | `SearchQuery` from the trigger |
| `SearchMatches` | `string(variables('MatchRows'))` |
| `SelectedVideoInsights` | `string(outputs('Compose_SelectedVideoInsightsSlim'))` |
| `FoundVideos` | `string(variables('FoundVideos'))` |

### Return Node

Type: Return

Output `enrichedpayloadjson`:

```text
string(outputs('Compose_EnrichedPayload'))
```

## Output Contract

The flow returns one string output:

```text
enrichedpayloadjson
```

Current shape:

```json
{
  "SearchQuery": "Airbus A330",
  "SearchMatches": "[...]",
  "SelectedVideoInsights": "{...}",
  "FoundVideos": "[...]"
}
```

Each row in `FoundVideos` now also contains a native `Moments` array when the
grouped flow branch is enabled. A typical row looks like this:

```json
{
    "VideoName": "A family that flies together_ Airbus' commercial aircraft",
    "MatchCount": "9",
    "Moments": [
        {
            "Time": "0:00:56",
            "StartSeconds": "56",
            "TypesText": "Ocr, Brand",
            "TextsText": "A330 | Airbus A380 | Airbus A330",
            "ExactTextsText": "A330 | Airbus",
            "DisplayText": "A330 | Airbus",
            "WatchUrl": "...",
            "InsightsUrl": "..."
        }
    ]
}
```

`MatchCount` inside `FoundVideos` currently arrives as a string. Keep the topic
parse schema aligned with that actual output.

## Copilot Studio Build

### Topic Node Order

Build the topic in this order:

| Order | Node | Purpose |
|-------|------|---------|
| 1 | Trigger | Route the user request to the topic |
| 2 | `Search_VI_Videos` action | Call the flow |
| 3 | Parse value for `TopicEnrichedPayloadJson` | Parse the outer payload |
| 4 | Parse value for `TopicPayload.SearchMatches` | Build `TopicMatchRows` |
| 5 | Parse value for `TopicPayload.SelectedVideoInsights` | Build `TopicSelectedVideoInsights` |
| 6 | Parse value for `TopicPayload.FoundVideos` | Build `TopicFoundVideos` |
| 7 | Create generative answers | Produce `Global.VideoSummaryText` |
| 8 | Message | Render the adaptive card |

### Topic Variables

Use these variables:

* `TopicEnrichedPayloadJson` as `String`
* `TopicPayload` as `Record`
* `TopicMatchRows` as `Table`
* `TopicSelectedVideoInsights` as `Record`
* `TopicFoundVideos` as `Table`
* `Global.VideoSummaryText` as `String`

### Trigger

Type: Trigger

Use these values:

* Trigger type: `The agent chooses`
* Topic description:

```text
This topic searches Azure Video Indexer for a requested scene or moment and returns a best-match summary plus rich result cards with thumbnails and links.
```

### Action

Type: Action

Use these values:

* Flow: `Search_VI_Videos`
* Input `SearchQuery`: `Activity.Text`
* Output mapping: `enrichedpayloadjson` -> `TopicEnrichedPayloadJson`

### Parse Outer Payload

Type: Variable management > Parse value

Use these values:

* Parse value: `Topic.TopicEnrichedPayloadJson`
* Data type: `Record`
* Save as: `TopicPayload`

Schema:

```yaml
kind: Record
properties:
  SearchQuery: String
  SearchMatches: String
  SelectedVideoInsights: String
  FoundVideos: String
```

### Parse SearchMatches

Type: Variable management > Parse value

Use these values:

* Parse value: `Topic.TopicPayload.SearchMatches`
* Data type: `Table`
* Save as: `TopicMatchRows`

Schema:

```yaml
kind: Table
properties:
  VideoName: String
  VideoId: String
  AccountId: String
  Time: String
  StartSeconds: String
  MatchText: String
  MatchType: String
  ExactText: String
  WatchUrl: String
  InsightsUrl: String
```

### Parse SelectedVideoInsights

Type: Variable management > Parse value

Use these values:

* Parse value: `Topic.TopicPayload.SelectedVideoInsights`
* Data type: `Record`
* Save as: `TopicSelectedVideoInsights`

Schema:

```yaml
kind: Record
properties:
  VideoName: String
  VideoId: String
  Duration: String
  Transcript: String
  OCR: String
  Brands: String
  Labels: String
  Keywords: String
  DetectedObjects: String
  Scenes: String
```

### Parse FoundVideos

Type: Variable management > Parse value

Use these values:

* Parse value: `Topic.TopicPayload.FoundVideos`
* Data type: `Table`
* Save as: `TopicFoundVideos`

Schema:

```yaml
kind: Table
properties:
  VideoName: String
  VideoId: String
  AccountId: String
  ThumbnailId: String
  ThumbnailDataUri: String
  MatchCount: String
  FirstMatchTime: String
  FirstMatchText: String
  FirstMatchType: String
  FirstExactText: String
  WatchUrl: String
  InsightsUrl: String
  SearchMatchesJson: String
    Moments:
        type:
            kind: Table
            properties:
                Time: String
                StartSeconds: String
                TypesText: String
                TextsText: String
                ExactTextsText: String
                DisplayText: String
                WatchUrl: String
                InsightsUrl: String
```

> [!IMPORTANT]
> The current flow already returns a nested `Moments` array inside each
> `FoundVideos` row. Updating the topic to use grouped moments requires only a
> topic change. You do not need to change the flow again.

### Create Generative Answers

Type: Advanced > Create generative answers

Use these settings:

* Input: `Activity.Text`
* `Search only selected sources`: On
* `Add knowledge`: leave empty
* `Web search`: Off
* `Allow the AI to use its own general knowledge`: Off

Open `Classic data`, switch `Custom data` to `Formula`, and paste this:

```powerfx
Table(
    {
        Title: "Instructions",
        Content: "Use only the provided search matches and selected video insights. Ignore any thumbnail, image, or data URI content. If there is only one matching result, summarize that result. If there are multiple matching results, identify the best matching result and summarize that one first. You may briefly mention that other relevant matches were also found. Mention the most relevant time, match type, and short supporting evidence. Do not invent facts."
    },
    {
        Title: "Search matches",
        Content: Topic.TopicPayload.SearchMatches
    },
    {
        Title: "Selected video insights",
        Content: Topic.TopicPayload.SelectedVideoInsights
    }
)
```

In `Advanced`, use these values:

* Save generated answer to global variable: `VideoSummaryText`
* `Send a message`: Off

#### Booth Demo Recommendation

For a booth or presentation setup, keep the flow, parse schema, and adaptive
card unchanged. Change only one instruction layer at a time so attendees can
see the effect clearly:

* Safest option: keep the flow and topic fixed and adjust only the Copilot
    Studio agent base instructions
* Topic-scoped option: keep the flow fixed and replace only the `Instructions`
    content string above

Do not change both layers in the same demo pass unless you want a combined
effect rather than a clean before-and-after comparison.

#### Higher-Precision Prompt For Comparison

If you want a stronger second pass without changing the flow, replace only the
`Instructions` content string with this version:

```text
Use only the provided search matches and selected video insights. Ignore any thumbnail, image, or data URI content. Prefer the most specific evidence over broad title or transcript hits. If the user asks for a named aircraft, model, logo, brand, object, or scene, prioritize exact OCR, brand, keyword, or label matches that contain the requested term. Treat generic title matches as secondary evidence unless no better evidence exists. If there are multiple matches, summarize the single best matching moment first and cite the exact time, match type, and short supporting evidence. Mention other relevant matches only if they reinforce the answer. Do not invent facts.
```

This is the recommended comparison prompt for demo queries such as `show me
airbus A330 scene`.

### Message Node With Adaptive Card

Type: Message

Use these values:

* Message format: `Adaptive card`
* Editor mode: `Formula`

Paste this current formula:

```powerfx
{
    '$schema': "http://adaptivecards.io/schemas/adaptive-card.json",
    type: "AdaptiveCard",
    version: "1.5",
    body: Table(
        {
            type: "ColumnSet",
            columns: Table(
                {
                    type: "Column",
                    width: "auto",
                    items: If(
                        CountRows(Filter(Topic.TopicFoundVideos, Not(IsBlank(ThumbnailDataUri)))) > 0,
                        Table(
                            {
                                type: "Image",
                                url: First(Filter(Topic.TopicFoundVideos, Not(IsBlank(ThumbnailDataUri)))).ThumbnailDataUri,
                                altText: First(Filter(Topic.TopicFoundVideos, Not(IsBlank(ThumbnailDataUri)))).VideoName,
                                size: "Medium"
                            }
                        ),
                        Table(
                            {
                                type: "Container",
                                style: "emphasis",
                                items: Table(
                                    {
                                        type: "TextBlock",
                                        text: "Thumbnail",
                                        weight: "Bolder",
                                        horizontalAlignment: "Center",
                                        wrap: true
                                    },
                                    {
                                        type: "TextBlock",
                                        text: "Placeholder",
                                        isSubtle: true,
                                        horizontalAlignment: "Center",
                                        spacing: "Small",
                                        wrap: true
                                    }
                                )
                            }
                        )
                    )
                },
                {
                    type: "Column",
                    width: "stretch",
                    items: Table(
                        {
                            type: "TextBlock",
                            text: "All Findings",
                            weight: "Bolder",
                            size: "Large",
                            color: "Accent",
                            wrap: true
                        },
                        {
                            type: "TextBlock",
                            text: Text(CountRows(Topic.TopicMatchRows)) & " raw evidence rows in the selected summary video",
                            isSubtle: true,
                            wrap: true,
                            spacing: "Small"
                        },
                        {
                            type: "TextBlock",
                            text: Coalesce(Global.VideoSummaryText, "Best matching summary will appear here."),
                            wrap: true,
                            spacing: "Medium"
                        }
                    )
                }
            )
        },
        {
            type: "TextBlock",
            text: "Available insights",
            weight: "Bolder",
            spacing: "Medium",
            wrap: true
        },
        {
            type: "FactSet",
            facts: Table(
                {
                    title: "Evidence pool:",
                    value: "Transcript, OCR, Brands, Labels, Keywords, Objects, Scenes"
                }
            ),
            spacing: "Small"
        },
        {
            type: "TextBlock",
            text: "Matching videos",
            weight: "Bolder",
            spacing: "Medium",
            wrap: true
        },
        {
            type: "Container",
            items: ForAll(
                Topic.TopicFoundVideos,
                {
                    type: "Container",
                    style: "emphasis",
                    separator: true,
                    spacing: "Medium",
                    items: Table(
                        {
                            type: "ColumnSet",
                            columns: Table(
                                {
                                    type: "Column",
                                    width: "auto",
                                    items: If(
                                        Not(IsBlank(ThumbnailDataUri)),
                                        Table(
                                            {
                                                type: "Image",
                                                url: ThumbnailDataUri,
                                                altText: VideoName,
                                                size: "Medium"
                                            }
                                        ),
                                        Table(
                                            {
                                                type: "TextBlock",
                                                text: "No thumbnail",
                                                isSubtle: true,
                                                wrap: true
                                            }
                                        )
                                    )
                                },
                                {
                                    type: "Column",
                                    width: "stretch",
                                    items: Table(
                                        {
                                            type: "TextBlock",
                                            text: VideoName,
                                            weight: "Bolder",
                                            size: "Medium",
                                            color: "Accent",
                                            wrap: true
                                        },
                                        {
                                            type: "TextBlock",
                                            text: Text(CountRows(Moments)) & " grouped moments from " & MatchCount & " raw matches",
                                            isSubtle: true,
                                            wrap: true,
                                            spacing: "Small"
                                        },
                                        {
                                            type: "TextBlock",
                                            text: Coalesce(FirstMatchType, "Match") & " | " & Coalesce(FirstMatchTime, ""),
                                            wrap: true,
                                            spacing: "Small"
                                        },
                                        {
                                            type: "TextBlock",
                                            text: Coalesce(FirstMatchText, ""),
                                            wrap: true,
                                            spacing: "Small"
                                        }
                                    )
                                }
                            )
                        },
                        {
                            type: "TextBlock",
                            text: "Grouped moments",
                            weight: "Bolder",
                            spacing: "Medium",
                            wrap: true
                        },
                        {
                            type: "Container",
                            spacing: "Small",
                            items: If(
                                CountRows(Moments) > 0,
                                ForAll(
                                    Moments,
                                    {
                                        type: "Container",
                                        separator: true,
                                        spacing: "Small",
                                        items: Table(
                                            {
                                                type: "TextBlock",
                                                text: "Moment | " & Time & If(Not(IsBlank(TypesText)), " | " & TypesText, ""),
                                                weight: "Bolder",
                                                wrap: true
                                            },
                                            {
                                                type: "TextBlock",
                                                text: Coalesce(DisplayText, TextsText, ExactTextsText, "No detail available."),
                                                wrap: true,
                                                spacing: "Small"
                                            },
                                            {
                                                type: "FactSet",
                                                facts: Table(
                                                    {
                                                        title: "Types:",
                                                        value: Coalesce(TypesText, "")
                                                    },
                                                    {
                                                        title: "Matched text:",
                                                        value: Coalesce(TextsText, "")
                                                    },
                                                    {
                                                        title: "Exact text:",
                                                        value: Coalesce(ExactTextsText, "")
                                                    }
                                                ),
                                                spacing: "Small"
                                            },
                                            {
                                                type: "ActionSet",
                                                spacing: "Small",
                                                actions: Table(
                                                    {
                                                        type: "Action.OpenUrl",
                                                        title: "Play moment",
                                                        url: WatchUrl
                                                    },
                                                    {
                                                        type: "Action.OpenUrl",
                                                        title: "Moment insights",
                                                        url: InsightsUrl
                                                    }
                                                )
                                            }
                                        )
                                    }
                                ),
                                Table(
                                    {
                                        type: "TextBlock",
                                        text: "No grouped moments available for this video.",
                                        isSubtle: true,
                                        wrap: true
                                    }
                                )
                            )
                        }
                    )
                }
            )
        }
    )
}
```

> [!NOTE]
> The summary still grounds on `TopicMatchRows` and `TopicSelectedVideoInsights`.
> The card details now render from `TopicFoundVideos[].Moments`.

## Grouped Moments Build

This grouped moments branch is part of the current working flow. Use this
section to rebuild it from scratch or verify that an existing build still
matches the intended shape. It keeps the summary path stable because
`SearchMatches` and `SelectedVideoInsights` do not change.

### Design Rules

* Keep `SearchMatches` flat for `Create generative answers`
* Keep `SelectedVideoInsights` unchanged
* Enrich only `FoundVideos`
* Deduplicate moments inside each video by `startTime`
* Merge repeated `type`, `text`, and `exactText` values before returning the
    card payload
* Run every loop in this section sequentially because the design reuses array
    variables

> [!IMPORTANT]
> Turn concurrency off on `Apply_to_each_FoundVideo`,
> `Apply_to_each_CurrentVideoMoment`, and `Apply_to_each_CurrentMomentMatch`.
> Shared variables make concurrent execution unsafe here.

### Add Top-Level Variables

Add these variables after `Initialize_FoundVideos`:

#### Initialize_CurrentVideoMoments

Type: Variables > Initialize variable

Use these values:

* Variable name: `CurrentVideoMoments`
* Variable type: `Array`
* Initial value:

```json
[]
```

#### Initialize_CurrentMomentTypes

Type: Variables > Initialize variable

Use these values:

* Variable name: `CurrentMomentTypes`
* Variable type: `Array`
* Initial value:

```json
[]
```

#### Initialize_CurrentMomentTexts

Type: Variables > Initialize variable

Use these values:

* Variable name: `CurrentMomentTexts`
* Variable type: `Array`
* Initial value:

```json
[]
```

#### Initialize_CurrentMomentExactTexts

Type: Variables > Initialize variable

Use these values:

* Variable name: `CurrentMomentExactTexts`
* Variable type: `Array`
* Initial value:

```json
[]
```

### Build The Inner FoundVideos Logic

Keep the existing thumbnail steps and first-match preview fields. Add the
moment-grouping steps below inside `Apply_to_each_FoundVideo`.

#### Set_CurrentVideoMoments

Type: Variables > Set variable

Use these values:

* Variable name: `CurrentVideoMoments`
* Value:

```json
[]
```

#### Filter_CurrentVideoMatchesTimed

Type: Data Operations > Filter array

From:

```text
outputs('Compose_CurrentVideoMatchesRaw')
```

Condition in advanced mode:

```text
@not(empty(item()?['startTime']))
```

#### Select_CurrentVideoMomentKeys

Type: Data Operations > Select

From:

```text
body('Filter_CurrentVideoMatchesTimed')
```

Map these two fields:

* `StartTime`

```text
item()?['startTime']
```

* `StartSeconds`

```text
add(
    mul(int(split(item()?['startTime'], ':')[0]), 3600),
    add(
        mul(int(split(item()?['startTime'], ':')[1]), 60),
        float(split(item()?['startTime'], ':')[2])
    )
)
```

#### Compose_CurrentVideoUniqueMoments

Type: Compose

Inputs:

```text
sort(
    union(
        body('Select_CurrentVideoMomentKeys'),
        body('Select_CurrentVideoMomentKeys')
    ),
    'StartSeconds'
)
```

#### Apply_to_each_CurrentVideoMoment

Type: Control > Apply to each

Loop input:

```text
outputs('Compose_CurrentVideoUniqueMoments')
```

Inside this loop, add the following actions.

#### Set_CurrentMomentTypes

Type: Variables > Set variable

Use these values:

* Variable name: `CurrentMomentTypes`
* Value:

```json
[]
```

#### Set_CurrentMomentTexts

Type: Variables > Set variable

Use these values:

* Variable name: `CurrentMomentTexts`
* Value:

```json
[]
```

#### Set_CurrentMomentExactTexts

Type: Variables > Set variable

Use these values:

* Variable name: `CurrentMomentExactTexts`
* Value:

```json
[]
```

#### Filter_CurrentMomentMatches

Type: Data Operations > Filter array

From:

```text
outputs('Compose_CurrentVideoMatchesRaw')
```

Condition in advanced mode:

```text
@equals(item()?['startTime'], items('Apply_to_each_CurrentVideoMoment')?['StartTime'])
```

#### Apply_to_each_CurrentMomentMatch

Type: Control > Apply to each

Loop input:

```text
body('Filter_CurrentMomentMatches')
```

Inside this loop, use three small conditions so each array variable stores only
distinct non-empty values.

Condition for `CurrentMomentTypes` in advanced mode:

```text
@and(not(empty(item()?['type'])), not(contains(variables('CurrentMomentTypes'), item()?['type'])))
```

If true, append this value:

```text
item()?['type']
```

Condition for `CurrentMomentTexts` in advanced mode:

```text
@and(not(empty(item()?['text'])), not(contains(variables('CurrentMomentTexts'), item()?['text'])))
```

If true, append this value:

```text
item()?['text']
```

Condition for `CurrentMomentExactTexts` in advanced mode:

```text
@and(not(empty(item()?['exactText'])), not(contains(variables('CurrentMomentExactTexts'), item()?['exactText'])))
```

If true, append this value:

```text
item()?['exactText']
```

#### Compose_CurrentMomentTypesText

Type: Compose

Inputs:

```text
join(variables('CurrentMomentTypes'), ', ')
```

#### Compose_CurrentMomentTextsText

Type: Compose

Inputs:

```text
join(variables('CurrentMomentTexts'), ' | ')
```

#### Compose_CurrentMomentExactTextsText

Type: Compose

Inputs:

```text
join(variables('CurrentMomentExactTexts'), ' | ')
```

#### Compose_CurrentMomentDisplayText

Type: Compose

Inputs:

```text
if(
    empty(outputs('Compose_CurrentMomentExactTextsText')),
    outputs('Compose_CurrentMomentTextsText'),
    outputs('Compose_CurrentMomentExactTextsText')
)
```

#### Append_to_CurrentVideoMoments

Type: Variables > Append to array variable

Variable name: `CurrentVideoMoments`

Value:

```text
{
    "Time": "@{items('Apply_to_each_CurrentVideoMoment')?['StartTime']}",
    "StartSeconds": "@{string(items('Apply_to_each_CurrentVideoMoment')?['StartSeconds'])}",
    "TypesText": "@{outputs('Compose_CurrentMomentTypesText')}",
    "TextsText": "@{outputs('Compose_CurrentMomentTextsText')}",
    "ExactTextsText": "@{outputs('Compose_CurrentMomentExactTextsText')}",
    "DisplayText": "@{outputs('Compose_CurrentMomentDisplayText')}",
    "WatchUrl": "@{concat('https://www.videoindexer.ai/embed/player/', items('Apply_to_each_FoundVideo')?['accountId'], '/', items('Apply_to_each_FoundVideo')?['id'], '?t=', string(items('Apply_to_each_CurrentVideoMoment')?['StartSeconds']), '&location=trial')}",
    "InsightsUrl": "@{concat('https://www.videoindexer.ai/embed/insights/', items('Apply_to_each_FoundVideo')?['accountId'], '/', items('Apply_to_each_FoundVideo')?['id'], '/?t=', string(items('Apply_to_each_CurrentVideoMoment')?['StartSeconds']))}"
}
```

#### Append_to_FoundVideos Delta

Keep the existing `Append_to_FoundVideos` object and add one more property:

```text
"Moments": variables('CurrentVideoMoments')
```

Insert `variables('CurrentVideoMoments')` from the Expression tab so it remains
a native array. If you wrap it in quotes, Copilot Studio will receive a string
instead of a nested table.

### Topic Parse Schema Reference

This is the same nested schema used in the main topic build above. Reuse it if
you rebuild the topic or need to repair the parse node:

```yaml
kind: Table
properties:
    VideoName: String
    VideoId: String
    AccountId: String
    ThumbnailId: String
    ThumbnailDataUri: String
    MatchCount: String
    FirstMatchTime: String
    FirstMatchText: String
    FirstMatchType: String
    FirstExactText: String
    WatchUrl: String
    InsightsUrl: String
    SearchMatchesJson: String
    Moments:
        type:
            kind: Table
            properties:
                Time: String
                StartSeconds: String
                TypesText: String
                TextsText: String
                ExactTextsText: String
                DisplayText: String
                WatchUrl: String
                InsightsUrl: String
```

### Current Card Rendering Pattern

The current topic card no longer loops through `TopicMatchRows` for the lower
detail section. It keeps `TopicMatchRows` for AI grounding, but renders the UI
details from `TopicFoundVideos` and each video's nested `Moments` table.

This gives you:

* One video card per found video
* One deduplicated moment row per timestamp
* Merged OCR, brand, and annotation text for the same moment
* Timestamp-specific `Play video` and `Insights` links for every grouped row

## Thumbnail Changes From The Original Build

These are the changes made to add thumbnails without breaking the existing
summary and findings path:

* Added `FoundVideos` to `enrichedpayloadjson`
* Added a new `FoundVideos` loop in Power Automate to fetch one thumbnail per
  found video
* Added `TopicFoundVideos` in Copilot Studio with its own parse schema
* Changed `Create generative answers` grounding to use `SearchMatches` and
  `SelectedVideoInsights` only
* Replaced the original header placeholder with the first available
  `ThumbnailDataUri`
* Added a `Matching videos` section that renders rows from `TopicFoundVideos`
* Kept the detailed finding cards grounded on `TopicMatchRows`
* Added native grouped `Moments` inside each `FoundVideos` row for later card
    upgrades

## Known Limitations

* `SearchMatches` and `SelectedVideoInsights` still come from the first video
  returned by `Search Videos`
* `FoundVideos` follows flow order, not AI-selected best-match order
* `FirstMatchType`, `FirstMatchTime`, and `FirstMatchText` are preview fields
  from the flow, not guaranteed best-match fields
* `ThumbnailDataUri` is a video-level preview, not an exact timestamp
  thumbnail
* Copilot Studio may render only the first or first few inline base64 images
  if the card payload becomes too large

> [!TIP]
> If later thumbnails stop rendering, reduce the flow loop from
> `take(body('Search_Videos')?['results'], 3)` to `2`, or switch to externally
> hosted image URLs.

## Multi-Agent Booth Pattern

Use this pattern when the video search agent is exposed as a subagent or skill
inside a larger booth agent.

### What You Want To Achieve

The best booth experience keeps the video retrieval path deterministic and lets
the parent agent control only the user experience.

The intended split is:

* The parent agent owns the conversation and user-facing behavior
* The video search subagent behaves like a retrieval tool, not a second host
* The flow stays fixed and predictable
* The topic stays fixed unless you explicitly decide to add a small input
  parser for control metadata
* A successful video search returns the adaptive card as the complete answer
* Additional agent prose appears only for clarification, empty results, or
  failures

### What Works Today With No Topic Or Flow Changes

With the current setup, the parent agent can safely do only two things:

* Decide whether to call the video search subagent
* Pass a clean search query to the subagent

This means the parent agent can improve user experience, but it must not append
control words directly to the searchable query.

These work today:

* `show me all airbus A330 scenes`
* `find the Airbus A330 close shot`
* `show the spoken line about cognitive services`

These do not work safely today if passed as one raw message to the subagent:

* `show me all airbus A330 scenes mode=focus`
* `show me all airbus A330 scenes card_only`
* `find Airbus A330 and be concise`

The reason is simple: the current topic forwards `Activity.Text` into the video
search flow, so `mode=focus` becomes part of the search query instead of a
control value.

> [!IMPORTANT]
> If you test the current subagent directly, use only the clean search phrase.
> Do not embed orchestration flags inside the same message unless you first add
> a parser that strips them before the flow call.

### Smallest Useful Change For Dynamic Parent Control

If you want the parent agent to influence subagent behavior without changing
the flow logic, the smallest safe change is in the topic, not the flow.

Add a lightweight preprocessing step so the topic can separate:

* the clean search query sent to the flow
* the display or behavior mode used only by the topic or agent instructions

For example, the parent agent could send a structured envelope, but the topic
must strip the control fields before it calls the flow.

Until that parser exists, keep the parent-to-subagent contract simple: pass only
the cleaned search query.

### Recommended Subagent Role

The video search subagent should have one stable responsibility:

* take a clean search query
* run the existing search topic
* return the adaptive card as the full success response
* avoid extra narrative on successful search results

Suggested subagent base instruction:

```text
You are a deterministic video-search subagent. Your job is to retrieve the best available video moments through the existing video search topic and return the topic result. When the video search topic returns a successful adaptive card, treat that card as the complete response. Do not add extra narrative, headings, suggestions, or follow-up text after the card. Ask a short clarification question only when the user request does not contain enough searchable detail. If no useful result is found, return one short fallback sentence without invented details.
```

This instruction is static. It does not depend on parent control values, so it
works today.

### Recommended Main Agent Role

The parent agent is where the booth experience should live. That is the layer
users can modify and compare without risking the deterministic retrieval path.

The parent agent should:

1. Detect whether the request is a video-search request
2. Extract the searchable part of the request
3. Remove meta-phrases such as `focus mode`, `card only`, `be concise`,
    `explore mode`, or other orchestration language
4. Call the video-search subagent with only the cleaned search query
5. Present the subagent result directly when the subagent returns a successful
    adaptive card
6. Add text only for clarification, failure, or no-result cases

Suggested main-agent instruction:

```text
You are the booth host agent. When a user asks to find a scene, object, brand, logo, aircraft, spoken phrase, or moment in video, extract only the clean searchable query and send that query to the video-search subagent. Remove any meta-instructions such as focus mode, card only, explore mode, or tone guidance before invoking the subagent. If the video-search subagent returns a successful adaptive card, present that card as the full answer and do not add any extra summary or suggestions. Ask a clarification question only if the request lacks the searchable target. If no useful result is found, return one short sentence and one suggested reformulation. Do not invent timestamps, dialogue, or scene descriptions.
```

### Recommended Booth Progression

This is the safest way to let users experience prompt changes without touching
the subagent topic or flow.

1. Start with the stable subagent instruction that always returns only the card
    on success
2. Create a parent agent with the booth-host instruction above
3. Let users modify only the parent agent instructions
4. Compare how the parent agent rewrites or routes requests while the subagent
    remains fixed
5. Use the same query in repeated runs to show visible behavior changes without
    changing retrieval logic

Good booth comparison prompts are:

* `show me all airbus A330 scenes`
* `find the Airbus A330 close shot`
* `show the spoken line about cognitive services`
* `find nearby Airbus moments`

### Recommended First Validation Test

To test whether the design is possible with the current setup, validate in this
order:

1. Test the video-search subagent directly with a clean query only
2. Confirm it returns the adaptive card without extra text
3. Create the parent agent
4. Give the parent agent a mixed request that includes both a search request and
    meta-guidance
5. Confirm the parent agent strips the meta-guidance and still calls the
    subagent with a clean query

Example of a parent-level test request:

```text
Show me all Airbus A330 scenes. Use a focused booth style and do not add extra explanation.
```

Desired behavior:

* The parent agent interprets `focused booth style` as orchestration guidance
* The parent agent sends only `show me all Airbus A330 scenes` to the subagent
* The subagent returns only the adaptive card
* The parent agent does not add another narrative answer after the card

## Reference

* Video Indexer connector documentation:
  <https://learn.microsoft.com/en-us/connectors/videoindexer-v2/>
