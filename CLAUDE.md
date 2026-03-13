# CLAUDE.md — Learning Tool

## Overview

A local web-based knowledge exploration tool with a node-graph canvas UI. Users ask questions, get AI responses in visual nodes, then highlight text to spawn follow-up queries (explain, dig deeper, ask a question), building a connected graph of understanding.

**Stack:** Python/FastAPI backend, vanilla JS frontend (no framework, no build step), file-based JSON persistence.

## Quick Start

```bash
python app.py

# Custom options
python app.py --port 9000 --llm-model "my-model.gguf"
```

Opens at `http://localhost:8100`

## Project Structure

```
LearningSystem/
├── app.py                     # FastAPI server, routes, SSE streaming endpoint
├── models.py                  # Pydantic request/response models
├── prompt_engineer.py         # Prompt templates with lineage context
├── llm_bridge.py              # Async LLM bridge (OpenAI-compatible API)
├── session_manager.py         # File-based session CRUD + trash
├── static/
│   ├── index.html             # Single-page HTML shell
│   ├── css/main.css           # All styles, dark/light themes
│   ├── js/
│   │   ├── api.js             # Fetch wrappers + SSE streaming consumer
│   │   ├── app.js             # Main controller, workflows
│   │   ├── canvas.js          # Infinite canvas pan/zoom
│   │   ├── context_menu.js    # Text selection, highlighting, actions
│   │   ├── edge.js            # SVG Bezier edge rendering
│   │   ├── node.js            # Node DOM, drag, resize, streaming, math
│   │   ├── session.js         # Session CRUD, sidebar UI, auto-save
│   │   └── marked.min.js      # Vendored markdown parser
│   └── vendor/katex/          # Vendored KaTeX v0.16.21 (LaTeX math rendering)
├── learning_sessions/         # Active session data (JSON files)
├── learning_sessions_trash/   # Soft-deleted sessions (30-day retention)
└── development-docs/          # Development journey and architecture docs
```

## Architecture

- **Frontend:** Vanilla JS with IIFE module pattern. CSS transform-based infinite canvas. Nodes are absolute-positioned divs, edges are SVG Bezier curves.
- **Backend:** FastAPI + Uvicorn. SSE streaming endpoint for real-time token delivery from LLM to browser.
- **Persistence:** File-based JSON sessions in `learning_sessions/{YYYYMMDD_HHMMSS}/session.json`. Auto-save with 2-second debounce, flush on session switch, `sendBeacon` on page close.
- **LLM Integration:** OpenAI-compatible API via SSE streaming (default: chimera AI server at `192.168.1.221:8080`). Thinking token detection and filtering. Non-streaming fallback.

## Key Patterns

- **Node HTML rebuild:** `rebuildInnerHTML()` regenerates full node HTML on collapse/expand toggle to keep DOM structure in sync with state (scroll wrappers, fade overlays).
- **Edge scroll-aware clamping:** Edges track highlighted text during scroll, clamping to response section bounds when highlights scroll out of view.
- **Response rendering:** Raw AI text → `parseMdWithMath()` (LaTeX placeholder protection → `normalizeMarkdown()` → `marked.parse()` → restore) → `renderMath()` (KaTeX). Supports progressive rendering during SSE streaming.
- **Prompt data separation:** `prompt_text` stores user-facing text only; `engineered_prompt` stores the full LLM prompt separately. Lineage context grows linearly (not exponentially).
- **Viewport persistence:** Three-part save strategy — debounced auto-save on pan/zoom, `flushSave()` before session switch, `navigator.sendBeacon()` on page close.

## CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8100 | Server port |
| `--llm-url` | `http://192.168.1.221:8080/v1/chat/completions` | LLM endpoint (chimera AI server) |
| `--llm-model` | `""` | Model name (empty = use server default) |

## Dependencies

**Python:** `fastapi`, `uvicorn` (install via `apt install python3-fastapi python3-uvicorn` on Linux)

**JavaScript:** `marked.min.js` vendored, `KaTeX v0.16.21` vendored (no CDN, no npm)

**External:** OpenAI-compatible LLM server (default: chimera at `192.168.1.221:8080`)

## Development Notes

- All frontend modules use the IIFE pattern returning a public API object
- No build step — edit JS/CSS directly, refresh browser
- Session data is plain JSON — can be inspected/edited manually
- Development history documented in `development-docs/development-journey.md`
- System architecture documented in `development-docs/system-architecture.md`
