---
title: Copilot Studio Create generative answers research
description: Research notes on the Microsoft Copilot Studio Create generative answers node behavior and constraints
author: GitHub Copilot
ms.date: 2026-04-09
ms.topic: reference
keywords:
  - copilot studio
  - create generative answers
  - variables
  - json
  - parsing
estimated_reading_time: 4
---

## Scope

Research Microsoft Copilot Studio documentation and other reliable sources about
the Create generative answers node.

Focus questions:

1. Whether the node accepts input variables.
2. Whether it can use a single string input as context.
3. Whether knowledge sources, web search, and general knowledge can be disabled
   so it only uses provided input.
4. What outputs it exposes to later nodes, especially text output that can be
   parsed.
5. Whether it can be used to generate strict JSON for a Parse value node.

## Status

Complete.

## Findings

1. The Create generative answers node accepts an input variable for the query.

    * Microsoft documents the node setup as: on the node, for Input, select the
       `Activity.Text` system variable.
    * This confirms the node accepts a variable value as its input question.
    * The documented pattern is query input, not arbitrary prompt templating.

2. A raw single string is not documented as a direct context payload.

    * The documented custom data path expects a JSON array or a variable for that
       array.
    * The custom data field takes a `Table` with `Content` as the required field,
       plus optional `ContentLocation` and `Title`.
    * A single string can plausibly be used only if it is wrapped as one table
       record, not as a bare string.

3. You can limit the node to provided sources, but not with a hard guarantee of
    zero model knowledge.

    * Node-level knowledge sources override agent-level knowledge for that node,
       with agent-level sources acting as fallback.
    * The node supports optional sources including AI general knowledge and Bing
       Web Search. If you only configure custom data, the node is documented to use
       that data source path.
    * At the agent level, Web Search and Allow ungrounded responses can be turned
       off when generative orchestration is on.
    * Important caveat: Microsoft explicitly says that turning off Allow
       ungrounded responses does not guarantee the agent never uses general
       knowledge. The model can still incorporate general knowledge when combining
       it with retrieved knowledge or tool output.

4. The documented reusable output is generated answer text, not a documented
    structured object.

    * Microsoft documents storing the generated answer in a maker-created global
       variable by expanding Advanced on the node, creating a variable, and clearing
       Send a message.
    * This is the documented way to reuse the answer in later nodes, for example
       in an Adaptive Card.
    * Microsoft also documents that citations returned from a knowledge source
       cannot be used as inputs to other tools or actions.
    * No Microsoft Learn page found in this research documents a separate
       structured citation variable or JSON output contract for this node.

5. Strict JSON generation is documented for Prompt tools, not for Create
    generative answers.

    * The Parse value node is designed to parse JSON strings into typed records.
    * Prompt tools have explicit JSON output support, including saved output
       schema behavior and guidance for keeping JSON valid.
    * The generative answers node documentation does not describe JSON mode,
       output schema control, or response format constraints.
    * Conclusion: using Create generative answers to emit strict JSON for Parse
       value is not a documented or reliable pattern. A Prompt tool is the
       supported fit when strict JSON is required.

## References

* Microsoft Learn: Use generative answers in a topic
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/nlu-boost-node>
* Microsoft Learn: Knowledge sources summary
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-copilot-studio>
* Microsoft Learn: Orchestrate agent behavior with generative AI
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-generative-actions>
* Microsoft Learn: Use a custom data source for generative answers nodes
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/nlu-generative-answers-custom-data>
* Microsoft Learn: Connect your data to Azure OpenAI for generative answers
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/nlu-generative-answers-azure-openai>
* Microsoft Learn: Work with variables
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-variables>
* Microsoft Learn: Use prompts to make your agent or agent flow perform specific
   tasks
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/nlu-prompt-node>
* Microsoft Learn: Create a prompt
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/create-custom-prompt>
* Microsoft Learn: JSON output
   <https://learn.microsoft.com/en-us/microsoft-copilot-studio/process-responses-json-output>
* Repo context: spike/Copilot_Studio_Video_Indexer_Flow.md

## Caveats

* The documentation is clear about query input and knowledge-source grounding,
   but not about any rich structured output contract for the node.
* The best evidence for "no structured output" is the absence of any documented
   JSON mode plus the explicit limitation that citations cannot be passed to other
   tools or actions.
* If generative orchestration is turned on, the agent does not use edits to the
   Conversational boosting system topic when it searches knowledge sources.
   Therefore, topic-level node behavior is not the whole story for agent-wide
   knowledge behavior.
* Custom data uses only the first three records of the table to generate an
   answer.

## Open questions

* No unresolved blocking questions from the documentation research.
* If needed, the next step would be a product behavior check inside Copilot
   Studio to confirm the exact UI labels and currently exposed variable names in
   the latest tenant experience.