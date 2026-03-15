# Learning Tool — System Architecture

A local web-based knowledge exploration tool. You ask a question, get an AI response in a visual node, highlight text in that response to spawn follow-up queries (explain, dig deeper, ask a question), and build a connected graph of understanding.

---

## Quick Start

```bash
python app.py

# Custom options
python app.py --port 9000 --llm-url "http://my-server:8080/v1/chat/completions"
```

Opens at `http://localhost:8100`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (localhost:8100)               │
│                                                          │
│  ┌──────────┐  ┌────────────────────────────────────┐   │
│  │ Sidebar   │  │        Canvas Viewport             │   │
│  │           │  │  ┌──────────┐    ┌──────────┐      │   │
│  │ Sessions  │  │  │  Node A  │───→│  Node B  │      │   │
│  │ Trash     │  │  │ prompt   │    │ prompt   │      │   │
│  │           │  │  │ response │    │ response │      │   │
│  │           │  │  └──────────┘    └──────────┘      │   │
│  └──────────┘  └────────────────────────────────────┘   │
│                                                          │
│  JS Modules: app.js, canvas.js, node.js, edge.js,       │
│              session.js, context_menu.js, api.js         │
└──────────────────────┬───────────────────────────────────┘
                       │ REST API (fetch)
┌──────────────────────▼───────────────────────────────────┐
│                  FastAPI Server (app.py)                   │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Query API    │  │ Session API   │  │ Settings API   │  │
│  │ POST stream  │  │ CRUD sessions │  │ Provider CRUD  │  │
│  │ SSE response │  │ save/load     │  │ test/default   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │            │
│  ┌──────▼──────┐  ┌──────▼───────┐  ┌───────▼────────┐  │
│  │ Prompt      │  │ Session      │  │ Settings       │  │
│  │ Engineer    │  │ Manager      │  │ Manager        │  │
│  └──────┬──────┘  └──────────────┘  └───────┬────────┘  │
│         │                                    │            │
│  ┌──────▼────────────────────────────────────▼─────────┐ │
│  │ ProviderRegistry (llm_bridge.py)                    │ │
│  │ Factory → OpenAICompatibleProvider | ClaudeCLIProvider│ │
│  │ Default + Fallback provider routing                 │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## Backend

### `app.py` — FastAPI Entry Point

The main server file. Parses CLI args, initializes shared state, defines all API routes.

**CLI Arguments:**
| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8100 | Server port |
| `--llm-url` | `http://192.168.1.221:8080/v1/chat/completions` | LLM endpoint (used for first-run seeding only) |
| `--llm-model` | `""` | Model name (used for first-run seeding only) |

**Note:** CLI args `--llm-url` and `--llm-model` are only used to seed the initial `settings/providers.json` on first run. After that, provider configuration is managed through the settings UI and persisted in the settings file.

**API Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/query/stream` | Stream a prompt via SSE (primary query path) |
| `POST` | `/api/query` | Submit a prompt, returns `job_id` (legacy fallback) |
| `GET` | `/api/query/{job_id}/status` | Poll job status (legacy fallback) |
| `POST` | `/api/query/{job_id}/retry` | Re-run same prompt |
| `POST` | `/api/generate-title` | Generate session title from prompt |
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/sessions` | Create new session |
| `GET` | `/api/sessions/{id}` | Load session data |
| `PUT/POST` | `/api/sessions/{id}` | Save session data (POST for sendBeacon) |
| `PUT` | `/api/sessions/{id}/rename` | Rename session |
| `DELETE` | `/api/sessions/{id}` | Soft-delete to trash |
| `GET` | `/api/trash` | List trashed sessions |
| `POST` | `/api/trash/{id}/restore` | Restore from trash |
| `DELETE` | `/api/trash/{id}` | Permanently delete |
| `GET` | `/api/settings/providers` | List all providers (keys masked) |
| `POST` | `/api/settings/providers` | Add a new provider |
| `PUT` | `/api/settings/providers/{id}` | Update provider config |
| `DELETE` | `/api/settings/providers/{id}` | Delete provider |
| `POST` | `/api/settings/providers/{id}/test` | Test provider connectivity |
| `PUT` | `/api/settings/default-provider` | Set default provider |
| `PUT` | `/api/settings/fallback-provider` | Set fallback provider |
| `GET` | `/api/settings/provider-list` | Lightweight provider list for dropdown |

**Streaming query lifecycle (SSE):**
1. `POST /api/query/stream` builds the engineered prompt, returns `StreamingResponse` (SSE)
2. Provider resolved from `provider_id` in request body, or default provider
3. SSE events flow: `prompt` (engineered prompt) → `thinking` (model reasoning) → `token` (content chunks) → `done` (full text) or `error`
4. On failure with fallback configured: emits `event: fallback` SSE event, retries with fallback provider
5. Frontend consumes via `fetch` + `ReadableStream` reader, progressively rendering tokens into the node
6. Thinking tokens are detected and filtered (supports `<think>`, `<|channel|>analysis`, bare "analysis" prefix)

### `models.py` — Pydantic Models

Data models for API request/response validation:

- `QueryRequest` — prompt text, mode (initial/explain/deeper/question), parent references, `provider_id` (optional)
- `QueryResponse` — job_id, status, engineered prompt
- `JobStatusResponse` — status, elapsed time, response content
- `SessionFull` — complete session state: viewport, nodes dict, edges list, highlights dict
- `NodeData` — id, position, dimensions (width/height), prompt, response, status, collapsed states (prompt/response), parent/highlight references
- `EdgeData` — source node + highlight -> target node
- `HighlightData` — id, node, text, color
- `ProviderCreate` — alias, type, url, model, api_key, max_tokens, temperature, timeout, enabled
- `ProviderUpdate` — all fields optional (partial update)
- `DefaultProviderSet` — provider_id (str or None for fallback clear)

### `prompt_engineer.py` — Prompt Templates

Builds context-aware prompts for the three follow-up modes:

- **Explain**: "The user highlighted this text, explain it in context" — includes conversation lineage
- **Deeper**: "Explain this concept from first principles" — standalone, covers definition/importance/mechanisms/examples/misconceptions
- **Question**: "The user highlighted text and asks this question" — includes lineage + user's custom question

**Lineage context**: Walks the parent chain from the current node to root, collecting prompt+response pairs. Truncates responses to 1500 chars to avoid prompt bloat.

**Linear context growth**: Each node stores only a short user-facing `prompt_text` (the user's typed question, or a summary like `'Explain: "highlighted text"'`). The full engineered prompt (which includes lineage context) is stored separately as `engineered_prompt` and is **not** included when building lineage for child nodes. This prevents exponential context growth where each layer would otherwise embed all previous layers' context.

### `llm_bridge.py` — LLM Integration

Contains the OpenAI-compatible provider and the provider registry that manages all LLM providers.

**`OpenAICompatibleProvider`** (renamed from `LocalLLMQueue`):
- Two modes: `submit()` (non-streaming) and `stream()` (SSE streaming async generator)
- Uses `urllib.request` (no external dependencies)
- Runs blocking HTTP call in thread executor, bridges to async via `asyncio.Queue` + `loop.call_soon_threadsafe()`
- Streaming yields events: `("thinking", "")`, `("token", chunk)`, `("done", full_text)`, `("error", msg)`
- `api_key` parameter → `Authorization: Bearer {key}` header when non-empty
- URL auto-normalization: `_normalize_url()` appends `/v1/chat/completions` to bare host URLs
- `test()` method for connectivity validation
- Configurable `max_tokens`, `temperature`, `timeout`, `provider_id`

**`ProviderRegistry`**:
- Manages instantiated LLM provider instances from settings
- `_create(config)` factory method: `openai-compatible` → `OpenAICompatibleProvider`, `claude-cli` → `ClaudeCLIProvider`
- `get(id)` — specific provider, `get_default()` — default provider, `get_fallback()` — fallback or None
- `refresh()` — rebuilds from current settings (called after settings mutations)

**Thinking token detection and filtering:**
- `_strip_thinking(text)` — removes `<think>...</think>`, `<|channel|>final<|message|>` sequences, remaining `<|...|>` tokens, and bare "analysis" prefix
- `_has_thinking(text)` — detects thinking content onset for streaming phase transitions
- Streaming uses a phase state machine: `detecting` → `thinking` → `content`
- Non-streaming fallback when server returns `application/json` instead of `text/event-stream`

### `claude_cli_provider.py` — Claude Code CLI Integration

Calls Claude via the `claude` CLI binary, enabling use of an existing Claude Code subscription without an API key.

- Uses `asyncio.create_subprocess_exec` (not shell) — args as list, prompt via stdin pipe (no shell injection)
- CLI command: `['claude', '-p', '--output-format', 'json', '--tools', '', '--model', <model>]`
- Model name normalization: `MODEL_ALIASES` dict maps variations ("Opus 4.6", "claude opus", "claude-opus-4-6") to CLI short names ("opus", "sonnet", "haiku")
- `stream()` wraps the non-streaming subprocess for SSE compatibility: emits `("thinking", "")` → `("token", full_text)` → `("done", full_text)`
- Error handling includes stdout fallback when stderr is empty
- `test()` validates CLI binary exists and responds

### `settings_manager.py` — Provider Settings Persistence

File-based JSON persistence for LLM provider configuration.

**Storage:** `settings/providers.json` (gitignored to protect API keys)

**Provider config structure:**
```json
{
  "default_provider_id": "local-llm",
  "fallback_provider_id": "claudecode",
  "providers": {
    "local-llm": {
      "id": "local-llm", "alias": "OSS120", "type": "openai-compatible",
      "url": "http://192.168.1.221:8081/v1/chat/completions",
      "model": "gpt-oss-120b", "api_key": "", "enabled": true,
      "max_tokens": 30000, "temperature": 0.7, "timeout": 300
    }
  }
}
```

**Key behaviors:**
- API key masking: `_mask_key()` returns `"sk-...xxxx"` format; keys never sent unmasked to frontend
- Update handling: detects masked key values and preserves existing key
- First-run seeding: if no settings file exists, creates one from `--llm-url`/`--llm-model` CLI args
- Slug ID generation from provider alias (e.g., "My Provider" → "my-provider")
- Default/fallback provider selection and clearing on delete

### `session_manager.py` — Session Persistence

File-based CRUD with soft-delete trash system.

**Directory structure:**
```
learning_tool/
├── learning_sessions/
│   └── {YYYYMMDD_HHMMSS}/
│       └── session.json
└── learning_sessions_trash/
    └── {YYYYMMDD_HHMMSS}/
        └── session.json          # has extra "deleted_at" field
```

**Session JSON schema:**
```json
{
  "id": "20260310_110549",
  "name": "Understanding Transformers",
  "created_at": "2026-03-10T11:05:49",
  "updated_at": "2026-03-10T11:30:22",
  "viewport": { "panX": -120, "panY": -50, "zoom": 0.8 },
  "nodes": {
    "node_abc123_1": {
      "id": "node_abc123_1",
      "parent_id": null,
      "highlight_id": null,
      "x": 80, "y": 80,
      "width": 500, "height": null,
      "prompt_text": "What are transformers?",
      "engineered_prompt": "What are transformers?",
      "user_question": null,
      "prompt_mode": "initial",
      "prompt_collapsed": true,
      "response_collapsed": true,
      "response_html": "<h2>Transformers</h2>...",
      "response_text": "## Transformers\n...",
      "highlighted_text": null,
      "status": "complete",
      "created_at": "2026-03-10T11:05:55"
    }
  },
  "edges": [
    {
      "id": "edge_abc456",
      "source_node_id": "node_abc123_1",
      "source_highlight_id": "hl_def789",
      "target_node_id": "node_ghi012_2"
    }
  ],
  "highlights": {
    "hl_def789": {
      "id": "hl_def789",
      "node_id": "node_abc123_1",
      "text": "attention mechanism",
      "color": "rgba(59,130,246,0.3)"
    }
  }
}
```

**Trash lifecycle:**
1. Delete: `shutil.move()` to trash dir, add `deleted_at` timestamp
2. Restore: `shutil.move()` back, remove `deleted_at`, update `updated_at`
3. Permanent delete: `shutil.rmtree()`
4. Auto-cleanup: on startup, remove sessions where `deleted_at` > 30 days ago

---

## Frontend

All frontend code is vanilla JavaScript using the module pattern (IIFE returning public API). No build step, no framework.

### `index.html` — Page Structure

```
┌────────────────────────────────────────────────────┐
│ <aside#sidebar>                                     │
│   ├── sidebar-header (title + New button)           │
│   ├── session-list (populated by JS)                │
│   ├── sidebar-trash-section                         │
│   │   ├── trash toggle button                       │
│   │   └── trash-list (hidden by default)            │
│   └── sidebar-toggle (collapse button)              │
│                                                     │
│ <main#main-area>                                    │
│   ├── top-bar                                       │
│   │   ├── prompt input + send button                │
│   │   ├── provider dropdown (select AI provider)    │
│   │   ├── session name display                      │
│   │   └── settings gear + zoom + theme toggle       │
│   ├── canvas-viewport                               │
│   │   └── canvas-world (CSS transform for pan/zoom) │
│   │       ├── svg#edge-layer (Bezier edges)         │
│   │       └── .lt-node elements (appended by JS)    │
│   ├── context-menu (hidden, shown on right-click)   │
│   │   ├── Explain in Context                        │
│   │   ├── Dig Deeper                                │
│   │   └── Ask a Question                            │
│   └── settings-overlay (hidden, full-page modal)    │
│       ├── settings-backdrop                         │
│       └── settings-panel (provider list/forms)      │
└────────────────────────────────────────────────────┘
```

### `app.js` — Application Controller

Wires everything together on `DOMContentLoaded`:
- Initializes all modules: `Canvas.init()`, `EdgeRenderer.init()`, `Session.init()`, `ContextMenu.init()`, `Settings.init()`
- Theme toggle (persisted to `localStorage`)
- Prompt input handling (Enter to submit)
- Keyboard shortcuts (Escape to hide context menu + settings overlay, Ctrl+S to save)
- Provider dropdown population with localStorage persistence
- Settings button wiring

**Core workflows:**

1. **Initial prompt**: Creates session if needed → creates node data → renders DOM node → streams query via SSE → progressive token display → final render
2. **Spawn child**: Computes child position → creates node + edge data → renders DOM → draws edge → streams query via SSE (or shows editable textarea for "question" mode)
3. **Auto-title**: On first prompt, calls `/api/generate-title` to name the session

**SSE streaming (`streamQueryToNode`):**
- Injects `provider_id` from dropdown selection into query
- Receives events from `API.streamQuery()`: `onPrompt`, `onThinking`, `onToken`, `onDone`, `onError`, `onFallback`
- `onFallback` shows a toast notification when fallback provider is activated
- `onPrompt` stores the engineered prompt in `engineered_prompt` field (separate from `prompt_text`)
- `onToken` calls `NodeRenderer.streamToken()` for progressive markdown rendering
- `onDone` calls `NodeRenderer.finishStreaming()` for final render with full features

**Prompt data separation:**
- `prompt_text` stores user-facing text only (typed question or action summary like `'Explain: "highlighted text"'`)
- `engineered_prompt` stores the full prompt sent to LLM (with lineage context)
- `user_question` stores the original typed question for question-mode nodes (displayed in badge header)

**Node positioning (tree layout):**
- Initial nodes: stacked vertically at x=80, each below the previous (using actual DOM height + 60px gap)
- Child nodes: offset 500px to the right of parent
- First child aligns to parent's **top Y** (horizontal tree layout)
- Subsequent siblings stack below the last sibling using actual DOM height + 40px gap
- Collision avoidance: iterative algorithm checks all existing nodes for bounding-box overlap, pushes down only on actual conflicts (max 50 iterations)

### `canvas.js` — Infinite Canvas

CSS transform-based pan and zoom on `#canvas-world` inside `#canvas-viewport`.

**State:** `panX`, `panY`, `zoom` (applied as `translate(panX, panY) scale(zoom)`)
**Zoom:** `ZOOM_STEP = 0.04` per scroll tick (range 0.15–3.0)

**Interactions:**
- **Pan**: mousedown on empty canvas -> mousemove updates panX/panY -> mouseup ends
- **Zoom**: mouse wheel on empty canvas -> zoom at cursor position (maintains point under cursor)
- **Over collapsed nodes**: wheel events pass through for native scroll inside `.node-section-scroll`; when scroll hits bounds, event is absorbed (never falls through to canvas pan)
- **Over expanded nodes**: if no scrollable content exists (expanded, `overflow: visible`), wheel event pans the canvas so user can scroll past large nodes

**Cursor feedback:**
- Rest: `grab` (open hand)
- Panning: `grabbing` (closed hand) via `.panning` class
- Zooming: `zoom-in` or `zoom-out` via transient class with 150ms debounce

**Coordinate conversion:**
- `screenToWorld(clientX, clientY)` — for positioning new nodes
- `worldToScreen(wx, wy)` — for context menu positioning

### `node.js` — Node Rendering

Each node is a `div.lt-node` with absolute positioning on the canvas world.

**Node HTML structure (collapsed response):**
```html
<div class="lt-node" id="node_xxx" style="left:80px; top:80px; width:420px">
  <div class="node-header">
    <span class="node-mode-badge">Initial</span>
    <div class="node-actions">
      <button class="btn-toggle-section" data-section="prompt">▸</button>
      <button class="btn-toggle-section" data-section="response">▸</button>
      <button class="btn-retry">↻</button>
    </div>
  </div>
  <div class="node-prompt collapsed">
    <div class="node-section-scroll">
      <div class="node-prompt-text">What are transformers?</div>
    </div>
    <div class="section-fade"></div>
  </div>
  <div class="node-response collapsed">
    <div class="node-section-scroll">
      <div class="node-response-content"><!-- HTML response --></div>
    </div>
    <div class="section-fade"></div>
  </div>
  <div class="resize-handle resize-e" data-resize="e"></div>
  <div class="resize-handle resize-w" data-resize="w"></div>
  <div class="resize-handle resize-s" data-resize="s"></div>
  <div class="resize-handle resize-se" data-resize="se"></div>
  <div class="resize-handle resize-sw" data-resize="sw"></div>
</div>
```

**Key patterns:**

- **Event delegation**: Drag and resize handlers are on the outer `el`, so they survive `innerHTML` replacements when node status changes
- **Inner interactions**: Toggle buttons, expand/collapse clicks, scroll listeners — re-bound on every `updateNode()` call via `wireInnerInteractions()`
- **HTML rebuild on toggle**: `rebuildInnerHTML()` regenerates the full node HTML when toggling collapse/expand, ensuring the DOM structure (scroll wrappers, fade overlays) always matches the collapsed state. This replaced the earlier approach of just toggling CSS classes, which left HTML structure mismatched and caused edge rendering bugs.
- **Scroll wrapper**: Collapsed sections use `.node-section-scroll` for native scrolling; expanded sections have flat structure (no wrapper)
- **Fade overlay**: `.section-fade` is a sibling div (not `::after` pseudo-element) to stay pinned during scroll
- **Custom height**: `.has-custom-height` class enables flex-based response sizing; cleared when expanding via toggle
- **ResizeObserver**: Each node is observed for size changes (content reflow, images loading); triggers throttled edge redraw via `requestAnimationFrame`

**Response rendering pipeline:**
1. Raw text → `parseMdWithMath()` → HTML (always preferred when `response_text` is available)
2. Saved HTML fallback — only when no raw text exists (legacy sessions)
3. Plain text (HTML-escaped) — final fallback

**`parseMdWithMath(text)`**: Two-pass rendering that protects LaTeX from markdown:
1. Regex-extract all math blocks (`$$`, `\[...\]`, `\(...\)`, `$...$`), replace with `%%MATH_N%%` placeholders
2. Run `normalizeMarkdown()` + `marked.parse()` on placeholder-safe text
3. Restore placeholders with original LaTeX strings

**`renderMath(el)`**: Calls KaTeX `renderMathInElement()` on DOM elements after HTML insertion. Called at all four insertion points: `createNode`, `updateNode`, `rebuildInnerHTML`, streaming render. Uses `strict: false` to handle Unicode in LLM output.

**`normalizeMarkdown(text)`**: Deterministic text cleanup that runs before `marked.js`:
- Converts numbered section lines (`1. Title`) to `## 1. Title` headers
- Converts em-dash/en-dash bullets (`– item`) to standard `- item` markdown
- Detects short title-like lines (< 60 chars, ≤ 8 words, no ending punctuation, no commas or colons) and promotes them to `### ` sub-headers with surrounding blank lines
- Excludes table rows (lines with `|` characters) from sub-header detection
- Ensures proper spacing between sections for `marked.js` to parse correctly

**Progressive streaming:**
- `streamToken(nodeId, text)`: On first token, replaces thinking indicator with streaming response container (collapsed with scroll wrapper). Appends to buffer, debounced markdown render every 150ms via `parseMdWithMath()` + `renderMath()`.
- `finishStreaming(nodeId, fullText)`: Clears streaming state, forces both sections collapsed, calls `updateNode()` for final render with full features (highlights, edge anchors).
- Streaming container starts with `collapsed` class to prevent auto-save from capturing expanded state.

### `edge.js` — SVG Edge Drawing

Draws cubic Bezier curves from source highlights to target nodes.

**Coordinate system:** Uses world-space coordinates directly from node `style.left`/`style.top` to avoid screen-to-world conversion bugs.

**Source anchor (x1, y1):**
- If source is a `<mark>` element:
  - In a scroll container (collapsed section): clamp to **response section** visible bounds (not the scroll container, which can extend beyond the `overflow: hidden` clip area)
  - In expanded section: use direct `getBoundingClientRect()` position
  - Not rendered (zero dimensions): fall back to node center
- If no mark: right-center of source node

**Target anchor (x2, y2):**
- Left edge of target node, 50px from top (header area)

**Scroll-aware clamping logic:**
```
responseSection = mark.closest('.node-response')
respRect = responseSection.getBoundingClientRect()
markCenterY = markRect.top + markRect.height / 2
if markCenterY within respRect bounds → use actual position
if markCenterY < respRect.top → clamp to response section top
if markCenterY > respRect.bottom → clamp to response section bottom
Convert: offsetY = (screenY - nodeRect.top) / zoom
```

**Bezier curve:** Horizontal S-curve with control point offset = `max(dx * 0.4, 80)`

### `context_menu.js` — Text Selection and Highlighting

Handles the workflow: select text -> right-click -> choose action -> create highlight -> spawn child node.

**Selection tracking:**
- `mouseup` listener with 10ms delay to let selection finalize
- Validates selection is inside a `.node-response-content`
- Stores `{text, range, nodeId}` as `currentSelection`

**Context menu:**
- Shown on right-click inside response areas (suppresses default context menu)
- Three actions: Explain in Context, Dig Deeper, Ask a Question
- Each creates a persistent `<mark>` highlight, then calls `App.spawnChild()`

**Highlight creation (`createHighlight`):**
- Simple case: single text node — `range.surroundContents(mark)`
- Complex case: cross-element selection — uses `TreeWalker` to find all text nodes in range, wraps each in a `<mark>` element
- Handles partial start/end nodes via `splitText()`
- Skips whitespace-only text nodes that are direct children of `UL`, `OL`, `TABLE`, `TBODY` — prevents empty highlighted lines between list items

**Highlight reapply (`findAndWrapText` in `node.js`):**
- When nodes re-render (collapse/expand, session reload), `<mark>` elements are lost because `renderResponse()` prefers raw text → markdown
- `reapplyHighlights()` restores them by searching for the highlight text in the DOM and re-wrapping
- Exact `indexOf` match for single-element highlights (fast path)
- Whitespace-normalized fallback for cross-element highlights: collapses whitespace runs to single spaces in both search text and DOM text, builds a position map to translate normalized match positions back to exact DOM offsets

### `session.js` — Session Management

Manages the session lifecycle and sidebar UI.

**Session operations:**
- Create, load, rename, delete (to trash)
- Sidebar list with active indicator
- Trash list with restore and permanent delete

**Auto-save:**
- 2-second debounce via `scheduleSave()`
- Also triggered by: pan end, zoom, wheel-pan over expanded nodes (Phase 18)
- Captures current state from DOM before saving:
  - Viewport: panX, panY, zoom
  - Node positions: `style.left`, `style.top`
  - Node dimensions: `style.width`, `style.height`
  - Collapsed states: `.collapsed` class presence on prompt/response elements
  - Response HTML: `innerHTML` of `.node-response-content` (preserves highlights)

**Flush save on session switch:**
- `flushSave()` — cancels debounce timer and saves immediately
- Called before loading a different session to prevent data loss

**Save on page close:**
- `beforeunload` handler synchronously captures viewport + node state
- Uses `navigator.sendBeacon()` for reliable delivery during page teardown
- Server accepts both PUT and POST on the save endpoint (sendBeacon sends POST)

**Session restore:**
- Clears canvas
- Restores viewport state (panX, panY, zoom)
- Recreates all nodes with saved dimensions and collapsed states
- Multi-pass edge redraw: immediate `requestAnimationFrame`, then staggered redraws at 100ms and 500ms to handle layout settling (images loading, content reflowing)

### `api.js` — API Client

Simple fetch wrappers for all backend endpoints. All requests use JSON content type. Errors throw with status code and message.

**`streamQuery(data, callbacks)`**: SSE streaming consumer for the primary query path. Uses `fetch` + `response.body.getReader()` + `TextDecoder` to parse SSE events line-by-line. Dispatches to callbacks: `onPrompt`, `onThinking`, `onToken`, `onDone`, `onError`, `onFallback`. Handles remaining buffer data after stream ends.

**Settings API wrappers:** `getProviderList`, `getProviders`, `addProvider`, `updateProvider`, `deleteProvider`, `testProvider`, `setDefaultProvider`, `setFallbackProvider` — all JSON fetch wrappers for the `/api/settings/*` endpoints.

### `settings.js` — Settings Overlay

IIFE module managing the full-page settings overlay for LLM provider configuration.

**Provider list view:**
- Cards per provider: alias, type badge (CLI/API), URL/model details, DEFAULT/FALLBACK badges
- Action buttons: Test, Edit, Set Default (shows "Is Default" disabled for current), Delete
- "+ Add Provider" button at top
- Fallback provider dropdown at bottom

**Add/Edit form:**
- Fields: Alias, Type (openai-compatible / claude-cli), URL, Model, API Key, Max Tokens, Temperature, Timeout, Enabled
- Type-dependent visibility: claude-cli hides URL and API Key fields
- Password field placeholder shows "(unchanged)" for existing providers

**Test connectivity:**
- POSTs to `/api/settings/providers/{id}/test`
- Inline result display: green for success (with response preview), red for error

---

## Styling (`main.css`)

### Theme System

CSS custom properties with two themes:
- **Dark** (default): Slate/navy palette (`#0a0f1a` body, `#1e293b` nodes)
- **Light**: Clean white/gray (`#f1f5f9` body, `#ffffff` nodes)

Toggled via `data-theme` attribute on `<html>`, persisted to `localStorage`.

### Node Transparency

Nodes use `color-mix(in srgb, var(--bg-node) 80%, transparent)` with `backdrop-filter: blur(6px)` for a frosted glass effect. The fade gradients on collapsed sections match this same transparency.

### Canvas Grid

Dot grid background via `radial-gradient`:
```css
background-image: radial-gradient(circle, var(--border-color) 1px, transparent 1px);
background-size: 30px 30px;
```

### Key CSS Classes

| Class | Purpose |
|-------|---------|
| `.lt-node` | Node container, absolute positioned |
| `.lt-node.dragging` | During drag — higher z-index, accent border |
| `.lt-node.resizing` | During resize — higher z-index |
| `.has-custom-height` | Node has user-set height — response fills space |
| `.node-prompt.collapsed` | Prompt section collapsed (64px max-height) |
| `.node-response.collapsed` | Response section collapsed (320px max-height) |
| `.node-section-scroll` | Scroll container inside collapsed sections |
| `.section-fade` | Gradient overlay at bottom of collapsed sections |
| `.canvas-viewport.panning` | Grabbing cursor during pan |
| `.canvas-viewport.zooming` | Zoom-in cursor during wheel zoom |
| `.provider-select` | Provider dropdown in top bar |
| `.settings-overlay` | Full-page settings modal container |
| `.settings-panel` | Settings content panel (centered) |
| `.provider-card` | Individual provider card in settings |
| `.provider-badge-default` | Green "DEFAULT" badge |
| `.provider-badge-fallback` | Blue "FALLBACK" badge |
| `.provider-test-result` | Inline test result display |
| `.toast` | Auto-dismissing notification bar |

---

## Data Flow

### Query Lifecycle (SSE Streaming)

```
User types question in top bar
        │
        ▼
App.submitInitialPrompt()
  ├── Creates nodeData (status: "queued", prompt_text: user's question)
  ├── NodeRenderer.createNode() → DOM node appears
  ├── streamQueryToNode() → API.streamQuery() → POST /api/query/stream
  │       │
  │       ▼
  │   app.py: build_prompt() → ProviderRegistry.get(provider_id).stream()
  │       │
  │       ▼  SSE events flow back to frontend:
  │   event: prompt  → stores engineered_prompt (separate from prompt_text)
  │   event: thinking → NodeRenderer.updateNode(status: 'running')
  │   event: token   → NodeRenderer.streamToken() (progressive render)
  │   event: done    → NodeRenderer.finishStreaming() (final render, collapse)
  │   event: error   → NodeRenderer.updateNode(status: 'error')
  │
  └── Session.scheduleSave() → auto-save after 2s debounce
```

### Highlight → Child Node

```
User selects text in response → mouseup stores selection
        │
        ▼
User right-clicks → context menu appears
        │
        ▼
User clicks action (Explain/Deeper/Question)
        │
        ▼
ContextMenu.handleAction()
  ├── createHighlight() → wraps text in <mark>
  └── App.spawnChild(parentNodeId, highlightId, text, action)
        │
        ▼
  ├── Compute child position (500px right, stacked vertically)
  ├── Create node + edge data in session
  ├── NodeRenderer.createNode() → child appears
  ├── EdgeRenderer.redrawAll() → edge drawn from mark to child
  └── streamQueryToNode() → same SSE lifecycle as above
```

---

## Dependencies

**Python (backend):**
- `fastapi` — Web framework
- `uvicorn` — ASGI server
- `pydantic` — Data validation (comes with FastAPI)

**JavaScript (frontend):**
- `marked.min.js` — Markdown parser (vendored, no CDN)
- `KaTeX v0.16.21` — LaTeX math rendering (vendored in `static/vendor/katex/` — CSS, JS, auto-render extension, 60 font files)
- No other dependencies — vanilla JS

**External services:**
- Any OpenAI-compatible LLM server (configured via settings UI)
- Claude Code CLI binary (optional, for Claude Code subscription users)
- Default: chimera AI orchestrator at `192.168.1.221:8081` with web search, model `gpt-oss-120b`

---

## File Map

```
LearningSystem/
├── app.py                     # FastAPI server, routes, SSE streaming, settings endpoints
├── models.py                  # Pydantic request/response models
├── prompt_engineer.py         # Prompt templates with lineage context
├── llm_bridge.py              # OpenAICompatibleProvider, ProviderRegistry
├── claude_cli_provider.py     # Claude Code CLI subprocess integration
├── settings_manager.py        # Provider settings persistence (JSON)
├── session_manager.py         # File-based session CRUD + trash
├── static/
│   ├── index.html             # Single-page HTML shell
│   ├── css/
│   │   └── main.css           # All styles, dark/light themes
│   ├── js/
│   │   ├── api.js             # Fetch wrappers + SSE + settings API
│   │   ├── app.js             # Main controller, provider dropdown
│   │   ├── canvas.js          # Infinite canvas pan/zoom
│   │   ├── context_menu.js    # Text selection, highlighting, actions
│   │   ├── edge.js            # SVG Bezier edge rendering
│   │   ├── node.js            # Node DOM, drag, resize, streaming, math
│   │   ├── session.js         # Session CRUD, sidebar UI, auto-save
│   │   ├── settings.js        # Settings overlay UI (provider management)
│   │   └── marked.min.js      # Vendored markdown parser
│   └── vendor/
│       └── katex/             # Vendored KaTeX v0.16.21 (math rendering)
│           ├── katex.min.css
│           ├── katex.min.js
│           ├── contrib/auto-render.min.js
│           └── fonts/         # 60 font files
├── settings/                  # Provider config (gitignored, contains API keys)
│   └── providers.json         # Provider definitions + default/fallback
├── learning_sessions/         # Active session data (JSON files)
├── learning_sessions_trash/   # Soft-deleted sessions (30-day retention)
└── development-docs/          # This documentation
```
