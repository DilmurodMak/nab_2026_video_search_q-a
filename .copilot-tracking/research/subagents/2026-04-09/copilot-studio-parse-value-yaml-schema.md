---
title: Copilot Studio Parse value YAML schema research
description: Research notes on the YAML schema syntax accepted by the Microsoft Copilot Studio Parse value editor
author: GitHub Copilot
ms.date: 2026-04-09
ms.topic: reference
keywords:
  - copilot studio
  - parse value
  - yaml schema
  - record
  - table
estimated_reading_time: 3
---

## Scope

Research reliable documentation or examples for Microsoft Copilot Studio Parse
value YAML schema syntax when the schema editor expects YAML with `kind:`
entries such as `Record` and `Table`.

Focus questions:

1. What is the exact YAML shape for a `Record` with string fields
   `SearchQuery`, `SearchMatches`, and `SelectedVideoInsights`?
2. What is the exact YAML shape for a `Table` of records with string fields
   `VideoName`, `VideoId`, `AccountId`, `Time`, `StartSeconds`, `MatchText`,
   `MatchType`, `ExactText`, `WatchUrl`, and `InsightsUrl`?
3. What caveats exist around field naming and type keywords?

## Status

Complete.

## Findings

1. Microsoft Learn shows the canonical root `Record` schema form used by the
    Copilot Studio schema editor.

    On the WhatsApp publishing article, Copilot Studio's HTTP Request response
    schema is shown as:

    ```yaml
    kind: Record
    properties:
       exists: Boolean
       phone: String
    ```

    This confirms the editor uses `kind: Record` plus a `properties` mapping,
    with primitive type keywords such as `String` and `Boolean`.

2. Microsoft Learn shows the canonical `Table` grammar for a table of records.

    On the custom knowledge sources article, the generated response schema is
    shown as:

    ```yaml
    responseSchema:
       kind: Record
       properties:
          query: String
          results:
             type:
                kind: Table
                properties:
                   snippet: String
                   title: String
                   url: String
    ```

    This is important because it shows the table row shape is declared with
    `kind: Table` and a `properties` block, not `items:`.

3. For the user's requested root-level schemas, the exact shapes are:

    Record with string fields:

    ```yaml
    kind: Record
    properties:
       SearchQuery: String
       SearchMatches: String
       SelectedVideoInsights: String
    ```

    Table of records with string fields:

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

4. A Microsoft Learn Q&A thread shows a maker attempting JSON-schema-like array
    syntax:

    ```yaml
    employeeTasks:
       kind: Array
       items:
          kind: Record
          properties:
             ...
    ```

    The post states Copilot Studio rejected that shape for an output variable.
    While this is not a product-spec page, it is useful corroboration that the
    schema editor expects `Table` semantics rather than `Array/items` semantics
    for row collections.

## References

* Microsoft Learn: Work with variables
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-variables>
* Microsoft Learn: Publish an agent to WhatsApp
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-add-bot-to-whatsapp>
* Microsoft Learn: Connect to custom knowledge sources
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/custom-knowledge-sources>
* Microsoft Learn Q&A: How to Capture and Return Dynamic Table Data in Adaptive
   Card for Copilot Studio
   <https://learn.microsoft.com/en-us/answers/questions/2155342/how-to-capture-and-return-dynamic-table-data-in-ad>
* Repo context: spike/Copilot_Studio_Video_Indexer_Flow.md
* Repo context: spike/sample_output_flow_return.json

## Caveats

* Primitive type keywords in Microsoft examples are capitalized: `String`,
   `Number`, `Boolean`.
* Complex types use `kind: Record` and `kind: Table`, not JSON Schema keywords
   like `object`, `array`, or lowercase `string`.
* For primitive properties, the concise form is `FieldName: String`.
* For a complex property inside a record, Microsoft examples wrap the type in a
   `type:` block, for example:

   ```yaml
   results:
      type:
         kind: Table
         properties:
            snippet: String
   ```

* Microsoft Learn explicitly publishes nested-table syntax, but I did not find
   a separate Microsoft page that shows a standalone root-level `kind: Table`
   block. The root-level table example above is the direct root-form adaptation
   of the documented table grammar.
* Field names should match the incoming JSON property names exactly, including
   case, because Copilot Studio examples preserve property names verbatim.

## Open questions

* No blocking questions remain.