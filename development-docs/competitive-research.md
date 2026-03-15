# Learning Tool — Competitive Research

Research conducted March 2026 via 25+ web queries across Product Hunt, Hacker News, GitHub, Reddit, and general web. Products are organized by how closely they match our five key features:

1. **Node-graph canvas** — infinite canvas with visual nodes
2. **Text selection within AI responses to branch into new queries**
3. **Visual edges** — lines connecting highlights to child nodes
4. **Lineage-aware context** — ancestor prompt/response pairs sent to LLM
5. **Learning/knowledge exploration focus**

---

## TIER 1: Very Close Match (4–5 of 5 key features)

### 1. Canvas Chat (by Eric Ma)

- **URL:** https://github.com/ericmjl/canvas-chat | Blog: https://ericmjl.github.io/blog/2025/12/31/canvas-chat-a-visual-interface-for-thinking-with-llms/
- **Status:** Open source (GitHub)
- **Similarity:** Very high — this is the closest match found
- **Matching features:** Infinite canvas with nodes, highlight-and-branch (select text in a response to spawn a follow-up), visual edges between nodes, full ancestry context sent to LLM, multi-select merge for synthesis
- **Differences:** Built over a Christmas break as a personal tool; less polished; also includes matrix evaluation and LLM committee features; not specifically focused on learning

### 2. CanvasChatAI

- **URL:** https://canvaschatai.com/
- **Status:** Open source (runs on Modal)
- **Similarity:** Very high — appears to be the deployed/evolved version of Canvas Chat
- **Matching features:** Branching conversations, highlight-and-branch, context visualization, auto-layout, LaTeX/math rendering, multiple LLM providers including local Ollama
- **Differences:** Adds web research, image analysis, /matrix commands; more feature-rich but same core concept

### 3. TrAIn of Thought (bix.computer)

- **URL:** https://bix.computer/graphMode | HN discussion: https://news.ycombinator.com/item?id=47238814
- **Status:** Web app (free to use, unclear licensing)
- **Similarity:** Very high
- **Matching features:** Node-graph canvas for AI chat, text selection to branch/spin-off, quick definitions from highlighted text, visual connections between nodes
- **Differences:** Less information available about full feature set; appears to be a newer/smaller project

### 4. Project Nodal

- **URL:** https://github.com/yibie/project-nodal
- **Status:** Open source (GitHub)
- **Similarity:** High
- **Matching features:** Local-first infinite canvas, conversations as persistent spatial objects, branching from specific messages, multiple simultaneous AI conversations, context is spatial
- **Differences:** Uses IndexedDB for storage; describes itself as a "Thinking OS" rather than learning tool; supports OpenAI key or local Ollama; no explicit text-highlight-to-branch feature mentioned

### 5. MindCanvas

- **URL:** https://mindcanvas.app/ | Devpost: https://devpost.com/software/mindcanvas-m81znf
- **Status:** Web app (hackathon project)
- **Similarity:** High
- **Matching features:** AI conversations turn into connected draggable cards on infinite canvas, clarification branching (highlight text you do not understand to branch into a new linked chat), visual knowledge map
- **Differences:** Built with React Flow + FastAPI + Gemini API; hackathon-quality; specifically designed for learning/understanding

### 6. Conduit

- **URL:** https://conduitchat.app/
- **Status:** Open source, free forever
- **Similarity:** High
- **Matching features:** Highlight any text in any message to create a new conversation branch, each branch maintains clean context, 50+ models via OpenRouter
- **Differences:** Appears to be more of a branching chat UI than a full canvas/graph layout; self-hostable

---

## TIER 2: Strong Match (3–4 of 5 key features)

### 7. Heuristica

- **URL:** https://www.heuristi.ca/
- **Status:** Paid SaaS (with free tier)
- **Similarity:** High — specifically focused on learning/knowledge exploration
- **Matching features:** Node-based concept maps, AI-generated related concepts, infinite canvas, non-linear exploration, button-based exploration (ELI5, summarize, elaborate, analogize)
- **Differences:** Predefined exploration buttons rather than free-text highlight-to-query; integrates Wikipedia/arXiv/PubMed; generates flashcards and essays; more structured than free-form

### 8. Flowith

- **URL:** https://flowith.io/ | Review: https://dupple.com/tools/flowith
- **Status:** Paid SaaS ($15–40/month, free tier with 1,000 credits)
- **Similarity:** High
- **Matching features:** Infinite 2D canvas, AI responses as visual nodes, branching/merging/rearranging, 40+ AI models, Knowledge Garden for context
- **Differences:** More focused on productivity/creation than learning; includes Agent Neo (autonomous agent); 1M+ users; broader feature set (slides, video, websites)

### 9. Rabbitholes AI

- **URL:** https://www.rabbitholes.ai/
- **Status:** Paid (desktop app, $89 lifetime or $249 lifetime updates)
- **Similarity:** High
- **Matching features:** Infinite canvas, every chat is a node with branches, multi-model support (OpenAI/Anthropic/Google), visual connections, local storage
- **Differences:** Desktop app (not web-based); can attach files/PDFs/images to nodes; no explicit text-selection-to-branch mentioned; more general-purpose

### 10. ProjectLoom

- **URL:** https://projectloom.space/
- **Status:** Web app (demo available without signup)
- **Similarity:** High
- **Matching features:** Split conversations into different directions, explore side-by-side, combine insights from multiple threads, AI sees full context from all connected threads
- **Differences:** Less emphasis on text selection within responses; more about conversation-level branching

### 11. Thinkvas

- **URL:** https://www.thinkvasai.com/
- **Status:** Web app / SaaS
- **Similarity:** High
- **Matching features:** Infinite canvas, multiple parallel AI chats, branching at any turn, knowledge graphs, full context inheritance across threads
- **Differences:** Emphasizes knowledge graph construction; transforms documents/notes into living knowledge graphs; broader than just Q&A

### 12. FunBlocks AIFlow

- **URL:** https://www.funblocks.net/aiflow
- **Status:** Paid SaaS (browser extension available)
- **Similarity:** Moderate-High
- **Matching features:** AI-driven whiteboard/mind mapping, non-linear exploration, branching ideas on canvas, GPT-4/Claude integration, mental models framework
- **Differences:** More of a whiteboard/mind-mapping tool than a conversation graph; emphasizes mental models and structured thinking frameworks

### 13. Nodini.ai

- **URL:** https://nodini.ai/ | HN discussion: https://news.ycombinator.com/item?id=43407668
- **Status:** Web app (early stage, requires own ChatGPT API key)
- **Similarity:** Moderate-High
- **Matching features:** Live interactive flowchart of conversations, every message becomes a node, branching visible paths, zoom in/out of exploration
- **Differences:** Focused on brainstorming rather than learning; requires ChatGPT API key; early stage

---

## TIER 3: Moderate Match (2–3 of 5 key features)

### 14. Chatvas (Chat Nodes Canvas)

- **URL:** https://github.com/Kaleab-Ayenew/chatvas | Website: https://kaleab-ayenew.github.io/chatvas/
- **Status:** Open source (desktop app for Windows/macOS/Linux)
- **Matching features:** Infinite canvas, each ChatGPT branch = node, animated edges, pan/zoom
- **Differences:** Wraps ChatGPT web interface (each node embeds a full ChatGPT session); not a standalone LLM client; no text-selection branching

### 15. LLM Canvas (by LittleLittleCloud)

- **URL:** https://github.com/LittleLittleCloud/llm-canvas | PyPI: https://pypi.org/project/llm-canvas/
- **Status:** Open source (Python/PyPI)
- **Matching features:** Infinite canvas visualization, branching conversations, Git-like branch management API
- **Differences:** Developer-focused tool for visualizing agent/tool-call flows; not end-user learning tool; API-driven (checkout/commit metaphor)

### 16. tldraw Branching Chat Template

- **URL:** https://github.com/tldraw/branching-chat-template | Docs: https://tldraw.dev/starter-kits/branching-chat
- **Status:** Open source (starter kit / SDK)
- **Matching features:** Visual branching conversation trees on infinite canvas, AI integration with streaming, context-aware (considers full branch history), drag-to-connect nodes
- **Differences:** A developer SDK/template, not a finished product; requires building on top of it

### 17. GitChat (by DrustZ)

- **URL:** https://github.com/DrustZ/GitChat
- **Status:** Open source (GitHub)
- **Matching features:** Branch, merge, and rewire LLM conversation histories; visual interface
- **Differences:** Git-inspired metaphor; more about conversation management than visual canvas exploration

### 18. Forky

- **URL:** https://github.com/ishandhanani/forky | Blog: https://ishan.rs/posts/forky-git-style-llm-history
- **Status:** Open source (GitHub)
- **Matching features:** DAG-based conversation management, forking/branching, web UI with interactive graph, three-way semantic merge
- **Differences:** Git-style metaphor; focuses on merge/summarize operations; more developer-oriented

### 19. BranchGPT

- **URL:** https://www.branchgpt.org/
- **Status:** Paid SaaS
- **Matching features:** Multiple conversation paths from any point, multi-model support, context preservation per branch
- **Differences:** More of a branching chat interface than a spatial canvas; focused on comparing model responses

### 20. Graphine

- **URL:** HN discussion: https://news.ycombinator.com/item?id=43249085
- **Status:** Beta (as of early 2025)
- **Matching features:** Multi-model AI chat with branching conversations
- **Differences:** Limited public information; was in beta

### 21. Obsidian Plugins (RabbitMap, Canvas LLM, Chat Stream)

- **URLs:** RabbitMap: https://github.com/bayradion/rabbitmap | Canvas LLM: https://www.obsidianstats.com/plugins/canvas-llm | Chat Stream: https://www.obsidianstats.com/plugins/chat-stream
- **Status:** Open source (Obsidian plugins)
- **Matching features:** Canvas-based AI chat nodes within Obsidian, branching conversations, drag & drop context from vault, visual node-based interface
- **Differences:** Requires Obsidian; leverages Obsidian's canvas feature; tightly coupled to the Obsidian ecosystem

### 22. Cognis AI (by Scalifi)

- **URL:** https://www.scalifiai.com/cognis-ai
- **Status:** Paid SaaS (free community tier, paid Essential/Professional)
- **Matching features:** Full visible conversation tree, infinite branches, model switching within threads, context control
- **Differences:** Enterprise/team-focused; more about workflow automation than learning; agentic orchestration platform

---

## TIER 4: Partial Match (1–2 key features, related concept)

| # | Product | Type | Notes |
|---|---------|------|-------|
| 23 | **Eureka** | SaaS | Knowledge into explorable visual maps with connected nodes. More about document/PDF analysis than interactive Q&A. |
| 24 | **Think Machine** | Paid SaaS | 3D mind maps, knowledge graphs, AI research workspace. Focus on note-taking, not conversational AI. |
| 25 | **Ponder** | Paid SaaS | Infinite canvas with nodes/relationships, AI-powered analysis. Oriented toward academic research/literature review. |
| 26 | **InfraNodus** | Paid SaaS | Text network visualization, click graph clusters to send to AI for elaboration. Primarily a text analysis tool. |
| 27 | **Jeda.ai** | Paid SaaS | AI mind maps on canvas, multi-LLM support, in-place AI discussions per object. Enterprise whiteboard/workspace. |
| 28 | **MyMap.ai** | Freemium SaaS | AI canvas for visual thinking, chat creates mind maps/diagrams, 10+ models. Focus on diagram/presentation generation. |
| 29 | **Whimsical AI Mind Maps** | Paid SaaS | AI-generated mind map branches (powered by Claude), click to expand. Mind map generator, not conversational. |
| 30 | **CanvasGPT** | SaaS | Infinite canvas, AI understands spatial topology. More about prototyping than conversational knowledge exploration. |
| 31 | **Mapify** | Paid SaaS | AI mind map generation. Summarization tool, not conversational. |
| 32 | **ChatGraPhT** | Academic paper | arxiv.org/abs/2512.22790 — node-link visual conversation interface, branching/merging, two agentic LLM assistants. Research prototype, not a shipping product. |
| 33 | **Prompt Tree** | Open source | DAG-based conversation structure, branching, local-first. Simpler tree interface, not a full canvas. |
| 34 | **aiTree** | Web app | Visualize AI conversations as tree structures. Organizes existing ChatGPT/Claude/Gemini conversations into trees; not standalone. |
| 35 | **TalkTree** | Web app | Visual conversation tree, branch off at any point. Simpler tree structure rather than spatial canvas. |

---

## Landscape Summary

The closest competitors are **Canvas Chat/CanvasChatAI** and **TrAIn of Thought**, which implement nearly identical workflows. Erik Fadiman's Medium article declares 2026 as "The Year of the Node-Based Editor."

### Feature Comparison: Our Differentiators

| Feature | Us | Canvas Chat | TrAIn of Thought | Heuristica | Flowith |
|---------|:--:|:-----------:|:-----------------:|:----------:|:-------:|
| Text-selection-to-branch | Yes | Yes | Yes | No (buttons) | No |
| Learning-first focus | Yes | No | No | Yes | No |
| Local-first / self-hosted | Yes | Partial | No | No | No |
| No build step (vanilla JS) | Yes | No | No | No | No |
| Linear context growth | Yes | Unknown | Unknown | N/A | Unknown |
| Multi-LLM provider support | Yes | Yes | Unknown | No | Yes (40+) |
| SSE streaming into nodes | Yes | Unknown | Unknown | N/A | Yes |
| Local LLM support | Yes | Yes (Ollama) | No | No | No |
| Claude CLI integration | Yes | No | No | No | No |
| No account required | Yes | Yes | No | No | No |

---

## Strategic Recommendations

### Recommended Differentiators to Build

**High-impact — nobody else is doing these:**

1. **Spaced repetition from your graph** — The killer feature gap. No competitor integrates actual learning science. Let the user click a node or highlight and generate flashcards (Anki-compatible export). Track what you've explored, surface it for review. This turns a casual exploration tool into something that produces *durable knowledge*.

2. **Shareable exploration paths** — Export a graph as a static HTML page others can walk through. "Here's how I learned quantum mechanics in 45 minutes." This is viral by nature and no one does it. Think of it as a learning artifact, not just a session.

3. **Cross-session knowledge graph** — Right now sessions are isolated. Let concepts link across sessions so you build a personal knowledge base over time. "You explored derivatives in Session A — connect that here."

4. **Learning progress signals** — Depth indicators, coverage maps, "you've explored 3 of 7 subtopics" type feedback. Turns passive exploration into guided learning.

**Medium-impact — sharpens the edge:**

5. **Guided exploration templates** — Pre-built starting graphs for common topics ("Learn linear algebra", "Understand how TCP works"). Lowers the cold-start problem.

6. **Code execution in nodes** — For STEM learning, being able to run Python/JS snippets inline within a response node would be powerful. None of the canvas tools do this.

7. **Source citations with verification** — Have the LLM cite sources, then let users click to verify. Addresses the trust problem in AI-assisted learning.

### Open Source vs Paid

**Open source is the clear play.** The paid space is too crowded for an unknown entrant (Flowith has 1M+ users at $15–40/mo, Rabbitholes charges $89 lifetime). But the open source landscape is weak — Canvas Chat was a Christmas break project, MindCanvas is a hackathon, Project Nodal is a side project. There's a vacuum for *the* well-maintained open source tool in this category.

Our vanilla JS / Python / FastAPI / file-based stack is extraordinarily contributor-friendly and deployment-friendly. People can clone and run in 30 seconds.

**Revenue path if desired:**
```
Open source with learning focus
  → GitHub stars / community
    → "The open-source AI learning canvas"
      → Consulting / custom deployments for education
      → Optional hosted version (freemium) for non-technical users
      → Integrations with education platforms (LMS, Anki, etc.)
```

**Bottom line:** Our strongest strategic position is the **open-source, local-first, learning-focused AI canvas** — with spaced repetition and shareable exploration paths as the features that make us categorically different from the "AI brainstorming whiteboard" crowd. The learning science angle is the moat nobody else is building toward.
