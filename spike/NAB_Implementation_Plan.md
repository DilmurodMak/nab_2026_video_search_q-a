Here is the content formatted in Markdown:

# NAB BYOA Experience Plan

Everyone, sharing an update on **Feasibility and Recommended Experiences**. Based on our recent validation work (thanks to Uffaz Nathaniel, Laura Lund, and Dilmurod Makhamadaliev (Mak) for awesome work), and considering the 10–15 minute walk-up NAB booth format, we plan moving forward with two BYOA experiences that are technically robust and suitable for the show floor.

## Selected Experiences

### 1. Visual Scene & Talent Analysis (Option B)
* **Description:** Pre-configured vision analysis for scenes, objects, and talent detection.
* **Interaction:** Visitors can build, publish, use, and tune a live agent on broadcast images.
* **Impact:** Clear cause-and-effect from adjusting instructions, with strong visual impact and fast feedback.

### 2. Video Content Q&A & Search (Option C)
* **Description:** Pre-indexed short videos with semantic video understanding.
* **Interaction:** Visitors assemble and publish an agent, ask questions, and refine how results are explained or ranked.
* **Impact:** Demonstrates advanced reasoning over video, not just keyword search, and scales well for booth traffic.

---

## Rationale
Our feasibility review highlighted that experiences must be **walk-up, reset-able, and booth-safe**. Visitors should actively build something, not just watch a demo. 

A simple **Build → Use → Iterate** loop with visible results is essential, using low-code, pre-configured elements for reliability. The 15-minute structure (5 min build, 5 min use, 5–10 min iterate) meets these needs and adapts to varying booth traffic.

---

## Next Steps
* Finalize visitor flows and booth enablement details.
* Align messaging for sales/marketing and training sessions.
* Complete building the agents with necessary building blocks to hook up by users.

**Action Items:**
* Please review the document and share any feedback or ideas, especially on areas that we can simplify or enhance without adding complexity. 
* Please reach out if you have bandwidth to help the building efforts in the next week or so.

---
**Attachment:** `NAB BYOA Experience Plan.docx`

---
**Attachment:** `NAB BYOA Experience Plan.docx`

---
# NAB BYOA Experience Plan: 15-Minute Build → Use → Iterate

## Purpose of this Document
This document assists the continuous development of the **NAB Build Your Own Agent (BYOA)** experience. We are targeting a **15-minute, walk-up experience** that preserves the BYOA spirit while remaining low-risk, repeatable, and booth-friendly.

### The 15-Minute Structure
* **Build:** 5 minutes
* **Use:** 5 minutes
* **Iterate:** 5–10 minutes (extendable if no queue)

This structure applies to the two technically-validated experiences:
1.  **Experience 1:** Visual Scene & Talent Analysis (Option B)
2.  **Experience 2:** Video Content Q&A & Search (Option C)

---

## Feedback Requested
Please focus feedback on:
* **Clarity** of the Build → Use → Iterate flow.
* Whether **visitor actions** feel meaningful but safe.
* Any parts that feel **too complex or too shallow** for NAB audiences.
* **Messaging** or framing improvements for sales/marketing alignment.

---

## Why We Are Adjusting the Plan
Recent feasibility discussions highlighted specific show-floor constraints:
* **Safety:** Must be short, walk-up, and easily resettable.
* **Agency:** Visitors should feel they *built* something, not just watched a demo.
* **Demonstration:** We must show a clear **cause → effect** when tuning an agent.
* **Scalability:** This flow is a speed-optimized version of the broader media AI agent patterns shown at IBC (e.g., rights verification, archive search, and metadata alignment).

---

## Experience Design Principles
* **No Blank Slates:** Visitors do not start from scratch.
* **Pre-Configured Stability:** All complex building blocks (models, indexing, pipelines) are pre-configured.
* **Meaningful Tuning:** The visitor completes, publishes, and tunes **one specific instruction** to observe a direct behavior change.
* **Clear Outcomes:** Each phase has a tangible result (Published Agent → Live Output → Behavior Change).

### High-Level Flow (Shared)

| Phase | Time | Goal | Visitor Outcome |
| :--- | :--- | :--- | :--- |
| **Build** | 0–5 min | Assemble agent using predefined blocks | Agent published |
| **Use** | 5–10 min | Interact with the live agent | Immediate, meaningful output |
| **Iterate** | 10–15+ min | Change one thing and re-publish | Behavior change observed |

---

## Experience 1: Visual Scene & Talent Analysis
**Narrative:** *"I can quickly assemble a media-aware agent, use it on broadcast images, then adjust its focus and see the difference."*

### Phase 1: BUILD (5 min)
* **Pre-configured:** Vision tools (scene, object, face detection), curated images, safe templates.
* **Visitor Actions:**
    * Select enabled capabilities (e.g., Faces vs. Scenes).
    * Choose a focus preset (e.g., Broadcast Metadata vs. Talent & Compliance).
    * Edit **one high-level instruction** (tone, priority, or verbosity).

### Phase 2: USE (5 min)
* Run the agent on a selected image.
* View bounding boxes, scene summaries, and talent insights.
* **Key Message:** *"This is your agent and its live output."*

### Phase 3: ITERATE (5–10 min)
* Change one setting (e.g., summarization style).
* Re-publish and run the same image to observe the difference.

---

## Experience 2: Video Content Q&A & Search
**Narrative:** *"I can assemble a video-aware agent, ask natural questions, and tune how it searches or explains results."*

### Phase 1: BUILD (5 min)
* **Pre-configured:** Pre-indexed short videos, vector search/grounding layer, baseline templates.
* **Visitor Actions:**
    * Select a search intent profile (Editorial, Compliance, or Archive).
    * Choose signals to emphasize (transcript, visuals, or brands).
    * Edit **one high-level instruction** (e.g., "timestamps required").

### Phase 2: USE (5 min)
* Ask natural-language questions about the video content.
* Receive timestamped answers and click to exact playback moments.
* **Key Message:** *"This is reasoning over video, not keyword search."*

### Phase 3: ITERATE (5–10 min)
* Change one instruction (ranking logic or signal priority).
* Re-publish and re-ask the same question to see changes in result ordering or explanation style.

---

## Summary of Benefits
* **Preserves BYOA value** while fitting booth constraints.
* **Demonstrates control** and adaptability rather than just static output.
* **Minimizes risk** of debugging or operational failure on the floor.
* **Scales beyond the booth** by showing the core "Build-Use-Iterate" loop used in production environments.