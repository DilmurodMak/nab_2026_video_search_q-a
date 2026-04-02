# NAB Conference – AI Agent Experiences

This document outlines a small set of lightweight AI agent experience options being considered for the NAB conference. The goal is to gather feedback, surface concerns or blockers, and understand what will resonate most with different NAB audiences.

---

## What we are trying to achieve
* **Create two short, walk-up experiences** that work well on a busy conference floor.
* **Show something visually compelling** that draws attention without explanation.
* **Demonstrate clear, practical relevance** to media and broadcast workflows.
* **Guide visitors through a quick, hands-on flow** to make simple building steps or changes to immediately see the agent’s result, demonstrating ease of use and immediate value.
* **Keep scope realistic:** everything must be pre-built, tested, and stabilized within **~3 weeks**.

---

## How to read the options below
Each option describes a single, pre-built agent experience. Visitors are not building agents from scratch; instead, they **complete** an almost-working agent, interact with it, and influence its behavior through simple inputs or changes. 

Different options naturally appeal to different visitor profiles (e.g., content creators, broadcast ops, media execs, AI-curious technologists), so we aim to pick **two options** for visitors to choose from.

---

## Experience Options

### A. Agent Controlling a Live Application (Computer Use)
A **computer agent** visibly controls a live application using a virtual mouse and keyboard. Once put together and enabled, visitors give a natural-language instruction (e.g., find a clip, edit in Clipchamp, update a schedule, etc.) and watch the agent perform the task on-screen in real time.

* **Why it’s interesting:** Very easy to understand, highly visual, and clearly shows agent autonomy.
* **Good fit for:** AI-curious visitors, operations leaders, and technologists.

### B. Visual Scene & Talent Analysis (Azure Computer Vision + Face API)
An agent analyzes a broadcast image or video frame and summarizes what it sees: labels and captions (e.g., "three people at a desk, camera, microphone"), bounding boxes around detected items, and when faces appear, identified on-screen talent with estimated attributes like age range and emotion. 

* **Why it stands out:** Immediate visual feedback, zero learning curve, and relevant to newsroom/archive metadata workflows and talent/compliance use cases.
* **Who it resonates with:** Broad walk-up audiences, broadcast operations, and compliance/talent management teams.

### C. Video Content Q&A and Search Flow
Using pre-indexed video (or a media website), the agent answers natural-language requests (e.g., “Find scenes with crowd noise”) and returns timestamps, brief summaries, and detected signals such as brands/logos, scene types, and content-safety flags. 

* **Why it’s interesting:** Shows how AI can understand, search, and navigate video content.
* **Good fit for:** Content managers, archivists, producers, and media operations.

### D. Multilingual Video Dubbing
A short broadcast clip is shown in its original language and then replayed in another language (e.g., Spanish, Arabic, French) using AI-generated dubbing and subtitles. 

* **Why it’s interesting:** Clear before/after effect and strong media relevance.
* **Good fit for:** Global broadcasters, content distributors, and streaming platforms.
* **Consider:** Implement Azure Local on a Surface Laptop.

### E. Promo Creative Brief Generator
A Copilot Studio agent turns a simple campaign idea into a structured promo brief, including hooks, CTAs, channels, and optional translations. 

* **Why it’s interesting:** Practical and familiar workflow for media marketing teams.
* **Good fit for:** Marketing, creative, and content strategy roles.
* **Consider:** Turn this into a Clipchamp story with their latest extension.

---

## High-level Comparison

| Option | Visual Impact | Media Workflow Fit | Visitor Interaction | Prep Complexity (3 wks) | Operational Risk | Best Visitor Profile |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Computer Use** | High | Medium-High | Change instructions | Medium-High | Medium | Tech / AI-curious / Ops |
| **B. Scene & Talent** | Medium-High | High | Swap image/frame | Low | Low | Broad / Ops / Compliance |
| **C. Video Q&A** | Medium | High | Ask free-text questions | Medium | Low–Medium | Archive / Media Ops |
| **D. Video Dubbing** | High | High | Select language | Low–Medium | Low | Distribution / Execs |
| **E. Promo Brief** | Low-Medium | High | Modify inputs | Low | Low | Marketing / Creative |

---

## Feedback we are looking for
1.  Which options feel most **compelling vs. confusing**?
2.  Which **visitor types** do you think each option best serves?
3.  Are there **risks or dependencies** we may be underestimating?
4.  Are there **combinations of two experiences** that together tell a strong story?
5.  What would you **simplify or remove** given the 3-week delivery window?