---
title: Copilot Studio Video Indexer Agent Booth Setup
description: End-to-end guide for a single Video Indexer agent booth experience with fixed topics, fixed flow wiring, and prompt-only instruction tuning.
author: GitHub Copilot
ms.date: 2026-04-13
ms.topic: how-to
keywords:
  - copilot studio
  - video indexer
  - booth demo
  - prompt engineering
  - searchmatches
  - selectedvideoinsights
  - foundvideos
  - adaptive card
  - global variables
estimated_reading_time: 10
---

## Overview

Use this setup when you want the simplest live booth experience:

* one public-facing Video Indexer agent
* one fixed `Search Video Indexer` topic
* one fixed Power Automate flow
* parsed outputs saved to globals by the topic
* booth users edit only the agent instructions

This is a no-code Copilot Studio approach for question answering over Video
Indexer insights. The fixed retrieval path keeps the search grounded in indexed
evidence so the agent can accurately return the scene or moment the user
intended to find.

This guide assumes the existing video-search flow and topic are already working
as described in [Copilot_Studio_Video_Indexer_Flow.md](./Copilot_Studio_Video_Indexer_Flow.md).

> [!NOTE]
> Earlier versions of this guide used a main-agent and subagent pattern. For
> the booth, we now recommend a single-agent design because it is simpler to
> operate live and easier for visitors to understand.

> [!IMPORTANT]
> Do not change the flow schema, parse schemas, topic wiring, or adaptive card
> formula during the booth. Keep retrieval fixed and use instruction changes to
> create visible behavior changes.

## Recommended End State

```text
Visitor
  -> Video Indexer agent
     -> routes to Search Video Indexer topic
     -> calls Power Automate flow
     -> parses outer payload
     -> parses SearchMatches
     -> parses SelectedVideoInsights
     -> parses FoundVideos
     -> saves globals
     -> renders results-only adaptive card
     -> optionally adds summary, evidence, suggestions, or transcript behavior
        from globals when instructions ask for it
```

The booth goal is to keep retrieval stable and let the same agent change how it
explains the result.

## Build Order

Use this order when you set everything up end to end:

1. Confirm the Power Automate flow and current `Search Video Indexer` topic are
   working.
2. Remove the generated text summary step from the topic.
3. Remove summary content from the adaptive card.
4. Keep parsed values available in globals.
5. Set the baseline agent instructions.
6. Prepare instruction recipes for summary, evidence, suggested prompts, and
   transcript.
7. Demonstrate prompt-only changes by rerunning the same query.

## Current Topic Design

### Role of the `Search Video Indexer` topic

The topic should do one deterministic job:

* accept the user's search query without rewriting it
* call the flow
* parse the returned payload
* save parsed values into globals
* render an adaptive card that shows only matched values

The topic should not:

* generate a free-form summary
* add suggested prompts in the topic
* rewrite, expand, or infer extra search terms
* change retrieval behavior based on style words
* require booth users to edit nodes, schemas, or formulas

### Recommended topic path

1. Trigger.
2. `Search_VI_Videos` action.
3. Parse outer payload.
4. Parse `SearchMatches`.
5. Parse `SelectedVideoInsights`.
6. Parse `FoundVideos`.
7. Set globals.
8. Message with results-only adaptive card.

### Globals that should remain available

In the Copilot Studio variable list, the global names appear as
`TopicPayload`, `TopicMatchRows`, `TopicSelectedVideoInsights`, and
`TopicFoundVideos`. In formula expressions, reference the same globals as
`Global.TopicPayload`, `Global.TopicMatchRows`,
`Global.TopicSelectedVideoInsights`, and `Global.TopicFoundVideos`.

| Global variable | Type | Use |
|---|---|---|
| `Global.TopicPayload` | Record | Outer payload record, including the search query and raw payload fields |
| `Global.TopicMatchRows` | Table | Match rows and times for the selected result |
| `Global.TopicSelectedVideoInsights` | Record | Transcript and structured evidence for the selected result |
| `Global.TopicFoundVideos` | Table | Cross-video results and grouped moments |
| `Global.VideoSummaryText` | String | Optional summary text for the current result |
| `Global.VideoEvidenceText` | String | Optional evidence explanation for the current result |
| `Global.SuggestedPromptsText` | String | Optional next-question suggestions |
| `Global.TranscriptAnswerText` | String | Optional transcript answer for the current result |
| `Global.ArchiveMetadataText` | String | Optional archive metadata response |
| `Global.ComparisonText` | String | Optional result comparison response |

> [!IMPORTANT]
> The baseline booth build should not depend on `Global.VideoSummaryText`. Keep
> summary generation out of the topic and let instruction changes add it later
> from the saved globals.

## Operator Changes Before the Booth

### Remove generated summary from the topic

Update the current topic so the baseline response is deterministic:

1. Remove the `Create generative answers` step, or disable it if you want to
   keep a copy for later.
2. Stop populating `Global.VideoSummaryText` in the baseline path.
3. Keep the parse steps for `SearchMatches`, `SelectedVideoInsights`, and
  `FoundVideos`, and save them into `Global.TopicMatchRows`,
  `Global.TopicSelectedVideoInsights`, and `Global.TopicFoundVideos`.
4. Leave the adaptive card node in place.

Do not add an LLM query-cleaning node in the baseline booth build. In this
scenario, generative rewriting can over-expand the query, introduce random
terms, or change the user intent.

### Remove summary from the adaptive card

Update the adaptive card so it shows only matched values:

* remove the summary block or summary text field
* keep grouped moments, timestamps, match types, OCR text, exact text, or other
  matched evidence
* keep the response focused on deterministic retrieved values
* do not add free-form narration inside the card

The first-turn booth response should be a results-only card.

### Alternative baseline when the model still infers too much

If the agent is already able to answer questions such as `find the best matching
result` from saved globals without any prompt change, the cleanest booth design
is often a topic-owned summary card rather than a card-only baseline.

In that version, the topic itself should generate and render a compact best-match
panel that includes:

* best matching video thumbnail
* best matching video title
* strongest evidence time
* short grounded summary text
* `Play` link
* `Insights` link

Then the lower portion of the card can still show matching videos and grouped
moments.

This works better when you want the booth result to feel intentionally designed
instead of letting the model improvise a prose answer from globals.

### Best-match links and thumbnail behavior

For a top summary panel, do not bind the top `Play` and `Insights` buttons to
`First(Global.TopicFoundVideos).WatchUrl` or
`First(Global.TopicFoundVideos).InsightsUrl`. Those fields come from the
video-level row and normally point at that video's first grouped moment, not
the strongest match used in the summary.

Instead, bind the top buttons to the chosen row in
`First(Global.TopicFoundVideos).Moments`, or better, to an explicit best-moment
record computed in the flow or topic. If you want the links to open at the same
timestamp mentioned in the summary text, keep that best moment as structured
data with at least `Time`, `StartSeconds`, `WatchUrl`, and `InsightsUrl`.

`ThumbnailDataUri` is still a video-level preview image. It is not tied to a
specific grouped moment. If you need the top card image to show the frame near
the chosen timestamp, extend the flow to return a moment-level thumbnail such
as `BestMomentThumbnailDataUri` or `Moments[].ThumbnailDataUri`.

If you want the summary step to choose the best moment, do not ask the model to
invent the final `WatchUrl` or `InsightsUrl` from scratch. A safer approach is
keep the model limited to summary text, then let the card choose the real links
from the existing globals.

Recommended baseline with the current variable set:

* summary text: `Global.VideoSummaryText` or a topic variable such as `Topic.TopicSummaryText`
* title and thumbnail: chosen from `Global.TopicFoundVideos`
* top `Play` and `Insights` links: chosen from the matching row in `BestVideo.Moments`

Do not introduce a required `Global.VideoSummaryPayload` record unless you have
explicitly added a parse step that creates it. The baseline guide assumes you
only have `Global.TopicPayload`, `Global.TopicMatchRows`,
`Global.TopicSelectedVideoInsights`, `Global.TopicFoundVideos`, and optional
summary text.

## Base Agent Instructions

### Baseline behavior

The public-facing agent should use one baseline instruction set. That baseline
should:

* route search-style requests to the existing `Search Video Indexer` topic
* reduce only obvious filler words when that preserves the exact search intent
* avoid rewriting, expanding, or semantically changing the user query
* avoid adding style, orchestration, or inferred terms into the search query
* present the adaptive card as the response
* use saved globals for later behavior changes
* treat any topic response as final for that turn
* avoid adding summary text unless the current instruction recipe explicitly
  asks for it

### Recommended baseline instructions

```text
You are a Video Indexer booth agent. When a user asks to find a scene, object, brand, logo, spoken phrase, transcript line, or specific moment in a video, route the request to the existing Search Video Indexer topic.

For search requests, you may remove obvious filler and command words from the topic input only when doing so preserves the user's exact searchable meaning. Reduction by deletion only is allowed. Do not rewrite, expand, enrich, reinterpret, or substitute the user's search terms. Do not add inferred entities, synonyms, categories, or extra context. Keep retrieval stable.

Remove filler words like show, show me, find, scene, clip, video, from existing videos, it, the, a, an, is, and please when they do not change the search meaning. Keep meaningful phrases exactly as the user said them, such as white background, Mars rover, fresh water, and flight simulator. Return only the cleaned search text. Do not add labels, commas, explanations, or full sentences. If the target is unclear, ask one short clarification question.

Examples:
User: Show me an Airbus scene from existing videos
Search query: Airbus
User: Show me an Airbus scene where it is in white background
Search query: Airbus white background
User: Show me a rover driving on Mars
Search query: rover Mars  

The topic may return an adaptive card, text, or both, and it also saves TopicPayload, TopicMatchRows, TopicSelectedVideoInsights, and TopicFoundVideos into globals.

If any topic is triggered and it returns a response, treat that topic response as final for the current turn. Do not restate it. Do not summarize it again. Do not explain it. Do not add any text before it. Do not add any text after it. Do not produce a second answer after the topic response.

If a topic returns a message or adaptive card, that topic response is final for the current turn. Do not print or serialize the adaptive card object as text.

Use the saved globals only when answering a later follow-up turn that does not already have a topic response. Do not invent timestamps, transcript lines, scene descriptions, evidence, or alternate search queries.
```

> [!IMPORTANT]
> The current topic sends `Activity.Text` directly to `SearchQuery`.
> Keep the cleaned value as plain searchable text. Do not format it as CSV such
> as `Rover, Mars`. If you need exact-phrase or AND behavior such as
> `"white background"` or `airbus+white+background`, add that logic in the
> topic or flow instead of relying on the booth prompt.

This baseline keeps the first response clean and makes the later instruction
changes easy to see.

## Booth User Experience

### What users change

Booth users should edit only the agent instructions.

They should not edit:

* topics
* parse schemas
* flow steps
* adaptive card formula
* global variable wiring

### What users see first

The baseline flow should be:

1. The user asks a natural search question.
2. The agent routes that question to `Search Video Indexer`.
3. The topic calls the flow and parses the payload.
4. The topic stores `TopicPayload`, `TopicMatchRows`,
  `TopicSelectedVideoInsights`, and `TopicFoundVideos` in globals.
5. The topic returns either a results-only adaptive card or a topic-owned
  best-match summary card, depending on the baseline you choose.
6. The agent should not add extra free-form analysis outside that card.

### Why this works better for the booth

This version is easier to operate live because:

* retrieval stays fixed
* the topic stays fixed
* the card stays fixed
* users can see instruction changes without touching wiring
* the same query can be rerun to show a visible before-and-after

If the model keeps answering from globals even before any instruction change,
prefer the topic-owned summary card baseline. That makes the baseline behavior
look deliberate rather than accidental.

### Hands-on booth exercise

Use these steps as direct instructions for the booth user.

#### Part 1: Start with the baseline agent

1. Watch the short source video in Video Indexer so you know what kind of
   content is available.
2. Open the agent and paste the baseline booth instructions.
3. Confirm that only the fixed `Search Video Indexer` topic is active for the
   search turn.
4. Ask a natural search question such as `show me Airbus scenes` or
   `show me water dew blur in background`.
5. Review the returned adaptive card.

What to notice:

* the agent routes the request to the fixed search topic
* the search topic returns matched results
* the topic also stores `TopicPayload`, `TopicMatchRows`,
  `TopicSelectedVideoInsights`, and `TopicFoundVideos` in globals

#### Part 2: Ask a follow-up question with the baseline instructions only

1. Keep only the baseline instructions in the agent.
2. Ask a follow-up question such as `summarize the best matching scene`.
3. Review the response.

What to notice:

* the general LLM may still answer from the available globals
* the answer may be useful, but it may also be inconsistent in format or may
  add extra prose

#### Part 3: Add the summary instruction recipe and ask the same question again

1. Open the agent instructions.
2. Add the `Summary` instruction recipe from this guide.
3. Save the agent.
4. Ask the same follow-up question again: `summarize the best matching scene`.
5. Compare the new response with the earlier one.

What to notice:

* the retrieval did not change
* the globals did not change
* the response shape is now controlled by the instruction recipe

#### Part 4: Ask an evidence question with the baseline instructions only

1. Remove the `Summary` instruction recipe or return to the baseline
  instructions.
2. Ask an evidence question such as `why is that the best result?`.
3. Review how the general LLM responds from the stored globals.

What to notice:

* the agent may answer from `Global.TopicMatchRows` and
  `Global.TopicSelectedVideoInsights`
* the answer may not stop cleanly or may not use the layout you want

#### Part 5: Add the evidence instruction recipe and ask the same question again

1. Open the agent instructions.
2. Add the `Evidence` instruction recipe from this guide.
3. Save the agent.
4. Ask the same evidence question again: `why is that the best result?`.
5. Compare the new response with the earlier one.

What to notice:

* the explanation is now grounded in the same saved globals
* the format is now more controlled
* the behavior is now driven by the instruction recipe

#### Part 6: Inspect where the logic happens

After the comparison, inspect both the agent instructions and the fixed search
topic.

For the agent instructions:

1. Open the agent instructions.
2. Locate the `Summary` or `Evidence` instruction recipe.
3. Review how the instruction tells the agent to use the saved globals.
4. Confirm that the summary or evidence behavior is coming from the current
  instructions, not from a separate topic.

For the fixed search topic:

1. Open `Search Video Indexer`.
2. Locate the parse steps for `SearchMatches`, `SelectedVideoInsights`, and
  `FoundVideos`.
3. Confirm that the topic stores those parsed values in globals.
4. If the topic still contains a `Generated text` or `Create generative
  answers` step, review what it is doing.
5. Confirm that the fixed search topic returns the final card and then stops.

#### Part 7: Explain the improvement

Use this conclusion in the booth:

* with only the baseline instructions, the LLM may still answer from the saved
  globals
* with an added instruction recipe, the same data is presented in a more
  controlled way
* the value is not different retrieval
* the value is better formatting, better stopping behavior, and more consistent
  grounding

## Prompt Recipes for Gradual Change

Use short instruction add-ons so the same agent produces visibly different
behavior without changing topics.

### Change 1: Summary

#### What changes

Add this to the agent instructions:

```text
After a successful video result, add a short two-sentence summary grounded only in Global.TopicSelectedVideoInsights and Global.TopicMatchRows. Mention the strongest matching evidence and keep the summary factual. Do not replace the adaptive card. Add the summary after the card.
```

#### What users see

* Before the change: card only.
* After the change: the same card plus a short grounded summary.

This is the cleanest proof that instruction tuning changed the response.

### Change 2: Evidence

#### What changes

Add this to the agent instructions:

```text
If the user asks why, prove it, explain the match, or asks for evidence, answer from Global.TopicMatchRows first and Global.TopicSelectedVideoInsights second. Cite the strongest timestamp, match type, and one or two supporting signals such as OCR, exact text, brand, label, or keyword. Keep the answer short and factual.
```

#### What users see

* The first-turn card stays the same.
* A follow-up such as `why is that the best result?` now produces evidence
  grounded in the saved globals.

### Change 3: Suggested Prompts

#### What changes

Add this to the agent instructions:

```text
After a successful video result, add one short line with three suggested follow-up prompts that can be answered from the saved globals. Prefer prompts about evidence, transcript, comparison, or metadata.
```

#### What users see

* The same card still appears.
* The agent now offers clear next steps after the card.

### Change 4: Transcript

#### What changes

Add this to the agent instructions:

```text
If the user asks what was said, asks for a quote, asks for transcript evidence, or asks for dialogue, answer from the transcript in Global.TopicSelectedVideoInsights. Quote only the relevant line or lines and give the nearest available timestamp. Do not summarize when the user explicitly asks for spoken words.
```

#### What users see

* The same card still appears on the search turn.
* A follow-up such as `what is actually said?` now returns transcript lines
  with times.

## Recommended Booth Script

Use the hands-on booth exercise above as the default live script. It gives the
audience a clean sequence:

1. watch the video
2. paste the baseline instructions into the agent
3. ask a search question
4. ask a follow-up question with the baseline instructions only
5. add an instruction recipe and ask the same question again
6. inspect the agent instructions and the fixed search topic to show where the
  logic happens

This is one of the strongest booth demos because the audience can see that the
same stored data supports both free-form and controlled agent behavior.

### Improvement ideas for the booth

Use these improvements if you want the experience to feel tighter and more
intentional.

1. Use only one instruction add-on at a time during the demo.
2. Keep a fixed sequence of follow-up questions so the audience can compare the
  outputs directly.
3. Use the same search query before and after changing the instructions.
4. Keep the fixed search topic ending immediately after its final card.
5. Prefer regular messages for evidence or transcript answers and adaptive cards
  for summary or hero-style presentation.
6. If the general LLM keeps adding extra text after a topic response, tighten
  the agent instruction that says topic output is final for that turn.
7. If the model already answers well from globals with only the baseline
  instructions, keep that as the baseline and use the added instruction recipe
  to show better layout, clearer grounding, and more consistent stopping
  behavior.

### Recommended demo queries

Use these queries for the first turn:

* `show me Airbus scenes`
* `find the push back radio call`
* `show me the spoken line about cognitive services`
* `find nearby Airbus moments`

Use these follow-up questions after the recipe changes:

* `why is that the best result?`
* `what is actually said?`
* `what else can I ask next?`
* `turn this into archive metadata`
* `compare the top results`

## No Additional Topics

This booth guide assumes that you do not have separate follow-up topics for
summary, evidence, transcript, metadata, comparison, or suggestions.

Use this pattern instead:

* keep one fixed `Search Video Indexer` topic for retrieval and globals
* keep the search topic deterministic
* use agent instruction changes to control summary, evidence, transcript, or
  other follow-up behavior from the saved globals
* do not create or enable extra topics live during the booth

## Validation Checklist

Confirm these points before the booth starts:

* `Search Video Indexer` still returns the correct card
* the topic still parses `SearchMatches`, `SelectedVideoInsights`, and
  `FoundVideos`
* `Global.TopicMatchRows` is populated after search
* the other parsed values are stored in globals
* the generated summary step is removed from the baseline topic
* the adaptive card no longer shows summary text
* the same search query still returns the same matched values after instruction
  changes
* if you use a top summary card, its `Play` and `Insights` links open at the
  chosen best-moment timestamp rather than the first video-level match
* the `Summary` add-on produces a visible change
* the `Evidence`, `Suggested Prompts`, and `Transcript` add-ons work from the
  saved globals

> [!IMPORTANT]
> The goal is not to make retrieval change every time. The goal is to keep
> retrieval stable while instruction changes alter how the agent summarizes,
> explains, suggests next steps, or quotes transcript.

## Recommendation

For the booth, use one stable Video Indexer agent with one stable search topic.
Remove the built-in summary from the topic and card, keep parsed values
available in globals, and let users edit only the agent instructions. That
gives you a controlled baseline and clear, gradual behavior changes that are
easy to demonstrate live.