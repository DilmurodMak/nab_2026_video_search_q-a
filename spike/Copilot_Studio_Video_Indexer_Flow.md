---
title: Copilot Studio Native Video Indexer Flow
description: Build-from-scratch reference for the current Power Automate and Copilot Studio implementation that returns selected-video evidence plus found-video thumbnail previews.
author: GitHub Copilot
ms.date: 2026-04-09
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
estimated_reading_time: 10
---

## Overview

This document captures the current NAB 2026 implementation.

The flow still returns one top-level output, `enrichedpayloadjson`, but the
payload now has four fields instead of three:

| Field                   | Type        | Purpose |
|-------------------------|-------------|---------|
| `SearchQuery`           | String      | Original user query |
| `SearchMatches`         | JSON string | Flat match rows for the first returned video |
| `SelectedVideoInsights` | JSON string | Slim evidence object for the first returned video |
| `FoundVideos`           | JSON string | Top returned videos with one video-level thumbnail per video |

This split is intentional:

* `SearchMatches` and `SelectedVideoInsights` continue to power the AI summary
  and the detailed findings list
* `FoundVideos` powers thumbnail previews and the matching-videos section
* The summary node must ignore thumbnails and base64 image data

> [!IMPORTANT]
> `ThumbnailDataUri` is a video-level preview image. It is not an exact
> timestamp-aligned thumbnail for the matching moment shown in the card.

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
```

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
                            },
                            {
                                type: "TextBlock",
                                text: "Top result thumbnail",
                                isSubtle: true,
                                horizontalAlignment: "Center",
                                spacing: "Small",
                                wrap: true
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
                            text: Text(CountRows(Topic.TopicMatchRows)) & " matching moments",
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
                Filter(Topic.TopicFoundVideos, Not(IsBlank(ThumbnailDataUri))),
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
                                    items: Table(
                                        {
                                            type: "Image",
                                            url: ThumbnailDataUri,
                                            altText: VideoName,
                                            size: "Medium"
                                        }
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
                                            text: MatchCount & " matching moments",
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
                            type: "ActionSet",
                            spacing: "Medium",
                            actions: Table(
                                {
                                    type: "Action.OpenUrl",
                                    title: "Play video",
                                    url: WatchUrl
                                },
                                {
                                    type: "Action.OpenUrl",
                                    title: "Insights",
                                    url: InsightsUrl
                                }
                            )
                        }
                    )
                }
            )
        },
        {
            type: "Container",
            items: ForAll(
                Topic.TopicMatchRows,
                {
                    type: "Container",
                    style: "emphasis",
                    separator: true,
                    spacing: "Medium",
                    items: Table(
                        {
                            type: "TextBlock",
                            text: "Finding | " & Time & " | " & MatchType,
                            weight: "Bolder",
                            size: "Medium",
                            color: "Accent",
                            wrap: true
                        },
                        {
                            type: "TextBlock",
                            text: Switch(
                                Lower(MatchType),
                                "ocr", "OCR match for: " & MatchText & " at " & Time & ".",
                                "brand", "Brand match for: " & MatchText & " at " & Time & ".",
                                "annotations", "Visual annotation match for: " & MatchText & " at " & Time & ".",
                                MatchType & " match for: " & MatchText & " at " & Time & "."
                            ),
                            wrap: true,
                            spacing: "Small"
                        },
                        {
                            type: "FactSet",
                            facts: Table(
                                {
                                    title: "Matched text:",
                                    value: MatchText
                                },
                                {
                                    title: "Exact text:",
                                    value: ExactText
                                },
                                {
                                    title: "Video:",
                                    value: VideoName
                                }
                            ),
                            spacing: "Medium"
                        },
                        {
                            type: "ActionSet",
                            spacing: "Medium",
                            actions: Table(
                                {
                                    type: "Action.OpenUrl",
                                    title: "Play video",
                                    url: WatchUrl
                                },
                                {
                                    type: "Action.OpenUrl",
                                    title: "Insights",
                                    url: InsightsUrl
                                }
                            )
                        }
                    )
                }
            )
        }
    )
}
```

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

## Reference

* Video Indexer connector documentation:
  <https://learn.microsoft.com/en-us/connectors/videoindexer-v2/>
