# Learning Tool — Development Journey

This document captures the complete iterative development process of the Learning Tool, built through a series of conversational prompts with Claude Code (Opus). Each section shows the exact user prompt, what was built in response, and what problems were solved along the way.

**Session files:** The full conversation transcripts are stored in:
```
C:\Users\Rob_Lucas\.claude\projects\c--Users-Rob-Lucas-Automation\
├── 10160fdc-a2c7-4ad4-96c2-dd7327191fa8.jsonl  (initial attempt, 2 messages)
├── 5c3bde94-ab61-4b98-af40-2bfc097fc13e.jsonl  (main session, Phases 1-22, multiple compactions)
└── fa29c3d2-8999-4e9f-b059-66e5eb8538a6.jsonl  (brief continuation check-in)
```

---

## Phase 1: The Founding Prompt

### Prompt #1 — Full Project Specification
> "Hey Claude, I want to create a brand new website tool as part of our automation system. I want it to be hosted locally perhaps in a container that runs something like nginx or another small web server (like pythons web serving test tool) whatever makes sense from a simplicity standpoint. But also whatever works the best for our outcome and is open source so we can share this project later.
>
> The goal of this tool, is for its user to enter a prompt for an AI to give an answer. Then within the answer, the user should be able to select text by click-drag highlighting and then right click on the text. They can then select from a few options "explain in context" "dig deeper" or "ask a question". Explain in context should trigger a new prompt we have engineered which takes the context (the prompt and response) from the first/previous windows where we highlighted text and then ask for clarification of the highlighted text (what it means, what it is, etc) from the back end AI (our saleschat.py tool which is already included in the folder for this project). Dig Deeper should trigger a new prompt we have engineered which excludes the original context, but simply explains whatever concept was highlighted from base principles and tries to thoroughly explain the concept. Ask a question will allow the user to ask a specific question they have in mind about the highlighted word, which will then trigger the back end AI with context added, and should focus squarely on answering the users question in a short answer.
>
> The UI should show a list of prior "sessions" on the left that can be clicked on to open them in the browser.
>
> The center should be a canvas that can display a node edge graph, where the nodes are combinations of prompt and answer from the AI. The prompt should show only the key minimum detail at the top of it before fading out. You can click to expand and see the whole prompt if you want. The answer showing beneath the prompt will show a significant portion of the response before fading out and you can click to expand and see it all. These combined are the nodes. the edges are lines from highlighted text in previous nodes which helped form the basis for the next search which is a prompt-response node pair. The text in the nodes should be pretty printed markdown OR HTML text that looks pretty. Whichever is easiest.
>
> You should be able to click and drag the canvas to move it around.
>
> You should be able to scroll to zoom in and out on the canvas or push +/- buttons.
>
> Each of these actions listed above ("explain in context" "dig deeper" or "ask a question"), should trigger the drawing of a line from the now permanently highlighted text within the original prompt/answer node, the line should connect from behind the first highlighted text answer window (translucent), and then connect to the edge of the new prompt window along with the answer underneath the prompt that was run. When the prompt has been sent for this new box, we should see a portion of the prompt as we noted before and we should see the answer window beneath it, but while we are waiting for the answer we should see thinking... with some sort of animation happening so we know we are waiting on our answer. If the response in the users opinion is not adewaute we should have a try again button that can be clicked to run the prompt again and get a new answer.
>
> The prompt/response nodes should have a handle on them or the ability to be dragged around so they can be rearranged on the canvas as the user sees fit. The lines connecting the nodes should remain connected to their anchor points. By default the graph should try to place new nodes to the right of the node they have been spawned from.
>
> when context is passed into a new prompt when using explain in context or ask a question function, the context should be accumulated from the past lineage of nodes this prompt has been spawned from. It should not traverse the whole graph instead it should just travel back up the tree to the first node to accumulate that context from all the nodes on that path. This way long alternate branches do not pollute the context of an individual line of thinking.
>
> Whenever the AI is engaged to create a response we use the SalesChat.py tool to pass in the context generate the response from our saleschat tool, capture it, and put it into this tool.
>
> Each "session" should be stored as a folder which contains all the information to reconstruct the graph and all the information learned as part of the session. Then we should be able to open the session in our web tool and continue where we left off. The user should be able to name the session.
>
> Please make the interface modern and fresh, dark mode or light mode as an option with dark mode default. Use a modern color pallete.
>
> Build me a comprehensive plan for this, research other projects to see if this has been created previously, I have included a rough drawing of what I imagine the UI might look like. If you have any questions about the implmentation please ask me."

### Prompt #2 — Hand-drawn Wireframe
An attached hand-drawn wireframe image (1640x2360 pixels) showing the envisioned UI layout with sidebar, canvas, nodes, and edge connections.

### What was built
The complete foundational application in a single pass:

**Backend (Python/FastAPI):**
- `app.py` — FastAPI server on port 8100, REST API for queries/sessions, async job queue with polling
- `models.py` — Pydantic models for all request/response types
- `prompt_engineer.py` — Three prompt templates (explain/deeper/question) with parent-chain lineage context
- `saleschat_bridge.py` — Async wrapper around SalesChat.py subprocess with lock serialization
- `session_manager.py` — File-based session CRUD storing JSON in `learning_sessions/{id}/session.json`

**Frontend (Vanilla JS):**
- `index.html` — Single-page shell with sidebar, top bar, canvas viewport, context menu
- `main.css` — Complete styling with dark/light themes via CSS custom properties
- `api.js` — Fetch wrappers for all endpoints
- `app.js` — Main controller wiring all modules together
- `canvas.js` — Infinite canvas with CSS transform pan/zoom
- `node.js` — Node DOM creation, drag handling, expand/collapse
- `edge.js` — SVG Bezier curves between highlights and child nodes
- `context_menu.js` — Text selection, `<mark>` highlight creation, action dispatch
- `session.js` — Session list, create, load, auto-save with debounce
- `marked.min.js` — Vendored markdown parser

**Key design decisions:**
- Vanilla JS with IIFE module pattern — no framework, no build step
- World-space coordinates for nodes (CSS `left`/`top` inside transformed container)
- SVG overlay for edges with `overflow: visible`
- Async job queue with 3-second polling for LLM responses
- File-based persistence (no database)

---

## Phase 2: Local LLM Integration

### Prompt #3
> "Actually I just fired up a local llm inside of my WSL2 ubuntu image here on this windows machine. It's hosted in a container named nodeava-llm-1 can you see if you can make calls to the llm and use that as the --mock target for testing?"

### What was built
- `LocalLLMQueue` class in `saleschat_bridge.py` — calls llama.cpp server via OpenAI-compatible API
- `--mock` CLI flag to switch between SalesChat (VPN) and local LLM
- `--llm-url` and `--llm-model` CLI options
- Default endpoint: `http://localhost:8081/v1/chat/completions`
- Default model: `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- Uses `urllib.request` (no external dependencies) with thread executor for async

### Prompt #4 — Port Binding Error
> "PS C:\Users\Rob_Lucas\Automation\learning_tool> python app.py --mock ... ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8100)"

Resolved: previous instance was still running. Added `--port` CLI option.

---

## Phase 3: First Usability Pass

### Prompt #5
> "Okay this is an amazing first start. Claude you do really good work. Now let's make some usability changes. I like the expanding of the answers in the nodes, what I would like though is when the mouse is over top of one of the nodes I would like the scroll operation to switch from zoom to scrolling up or down so people can easily highlight what they want to read with their mouse and scroll down. I also notice the edge lines that should be connecting the highlighted text to the new node are missing. Can you fix that. I also notice that the learning session is untitled which is fine, but it would be cool if as part of the first ask of a question the local model looks at the question being asked and creates a title for the session. Don't use saleschat to come up with the title its too slow."

### What was built
- **Scroll-over-nodes**: Modified `onWheel()` to pan canvas instead of zoom when cursor is over a node
- **Edge lines**: Fixed SVG edge drawing — edges now connect from highlighted `<mark>` elements to child nodes
- **Auto-title**: New `/api/generate-title` endpoint that uses the local LLM directly (fast, bypasses SalesChat queue) to generate a 6-word session title from the first prompt

---

## Phase 4: Edge Lines, Expand Behavior, Transparency, Highlight Colors

### Prompt #6
> "Looks like we have some difficulty with the lines staying connected to the hightlighted text. Also. when I said scroll the answer boxes I should have been clear. I wanted the answer boxes to expand fully when you click on them and then when you mouse over them, insead of the canvas zooming, the entire canvas should scroll downward or upward depending on the scroll. That way we don't run into issues with the lines not redrawing properly. Also the boxes with answers should be mildly transparent so you can see the lines behind them. Also I noted the hightlighted text is dark highlight with black text, lets make the black text green."

### What was built
- **Edge anchoring fix**: Edges now use `getBoundingClientRect()` to find mark positions relative to the node, converting screen coords to world coords via zoom division
- **Click-to-expand**: Response sections expand fully on click (not on scroll)
- **Node transparency**: `color-mix(in srgb, var(--bg-node) 88%, transparent)` with `backdrop-filter: blur(6px)` — frosted glass effect so edges show through
- **Highlight colors**: Changed `mark.lt-highlight` text color to green (`#22c55e` dark, `#16a34a` light)

---

## Phase 5: Node Overlap and Drag Fixes

### Prompt #7
> "We have an overlapping display bug, the 3rd next layer node I brought up was covering the second one. I tried to click and drag the node that was overlapping and it didn't move, I was unable to move any of the nodes and that's functionality we need."

### What was built
- **Child positioning**: `computeChildPosition()` now accounts for actual rendered height of sibling nodes, stacking children vertically with a 40px gap
- **Drag fix**: Node dragging was broken — fixed event handling so header mousedown properly initiates drag, with `DRAG_THRESHOLD` of 5px to distinguish from clicks

---

## Phase 6: Collapsed Edge Detection and Transparency Refinement

### Prompt #8
> "Okay notice that once I restarted and opened an old session where nothing was expanded the lines still are trying to connect to the old highlighted words. We should detect when a box is minimized and the highlighted words are not visible so the lines draw to the answer block of the non expanded node. They don't have to line up with the highlighted words in this case, they just need to maintain the hierarchy and connectivity. Then when we expand that first node, it should draw the lines connected to the highlighted words again.
>
> Dragging is working which is really nice, transparency is juuuuust visible in the new boxes that get added but the very first box doesn't seem to be transparent. Also can you make the boxes just a tiny bit more transparent."

### What was built
- **Collapsed edge detection**: `drawEdge()` now checks if the mark's `getBoundingClientRect()` returns zero dimensions (hidden/collapsed). If so, falls back to right-center of the source node instead of trying to anchor to an invisible mark
- **First node transparency fix**: The first node was missing transparency because the fade gradient `::after` pseudo-elements used solid `var(--bg-node)`, painting an opaque strip. Fixed by ensuring all nodes use the same `color-mix` background
- **More transparency**: Increased from 88% to 80% opacity: `color-mix(in srgb, var(--bg-node) 80%, transparent)`

---

## Phase 7: Toggle Buttons, Resize Handles, and State Persistence

*Note: This phase started after a context compaction (session ran out of context and was resumed with a summary).*

### Prompt #9
> "Can you add buttons (example in image where the circles are) to toggle expand the prompt portion or the answer portion. Also can you make it so when I mouse over the right or left edge of any one of the nodes I can expand the mouse changes to the left right arrow icon and allows you to click drag to expand the size of the node. Also can you extend that functionality to the corners so you can expand height as well as width or of course shrink height and width. Finally for each 'session' can you keep the state of the diagram so that when you close and open all the nodes are where you left them, expanded/resized etc everything goes back to exactly how the user had it?"

An attached screenshot showed the desired toggle button positions.

### What was built

**Toggle expand/collapse buttons:**
- `btn-toggle-section` buttons in the node header (one for prompt, one for response)
- Icons switch between `▸` (collapsed) and `▾` (expanded)
- Clicking toggles the `.collapsed` CSS class
- Prompt defaults to collapsed (64px max-height), response defaults to collapsed (320px max-height)
- Both click-on-section and button-in-header methods work

**Resize handles:**
- Five invisible handles: east, west, south, southeast, southwest
- East/west resize width; south resizes height; corners resize both
- West/southwest also shift the node's `left` position to resize from the left edge
- Subtle corner dots appear on hover as visual affordance
- Minimum dimensions: 200px width, 80px height

**Event delegation pattern:**
- Drag and resize handlers attached to the outer `el` element (not inner HTML)
- Critical because `updateNode()` replaces `innerHTML` when status changes
- Inner interactions re-bind on every update via `wireInnerInteractions()`

**Full state persistence:**
- `doSave()` captures from DOM before saving: positions, dimensions, collapsed states, response HTML
- On session load, all state is restored
- Auto-save with 2-second debounce

### Side conversation
> User: "I just tried the delete function in the tool too. Can you confirm it deleted things"

Confirmed deletion was working, which led directly to the next prompt:

---

## Phase 8: Trash Can with 30-Day Retention

### Prompt #10
> "Can you implement a trash can functionality so that they can be pulled back from trash for 30 days? Just have the app check the trash folders files dates on startup and clean up what needs to be cleaned up. No need for a special scheduled tool etc to use a timer etc."

### What was built

**Backend (`session_manager.py`):**
- `delete()` — Soft-delete via `shutil.move()` to `learning_sessions_trash/`
- Stamps `deleted_at` ISO timestamp into the session JSON
- `list_trash()` — Lists trashed sessions with days remaining
- `restore()` — Moves back to active, removes `deleted_at`, updates `updated_at`
- `permanent_delete()` — `shutil.rmtree()` for immediate removal
- `cleanup_trash()` — Called on startup, removes sessions older than 30 days

**Backend (`app.py`):**
- Trash cleanup runs in `lifespan()` startup hook
- Three new endpoints: `GET /api/trash`, `POST /api/trash/{id}/restore`, `DELETE /api/trash/{id}`

**Frontend:**
- Trash toggle button in sidebar footer
- Trash list shows session name, node count, and days remaining
- Hover reveals restore (green) and permanent delete (red) buttons
- Delete confirmation says "moved to trash for 30 days"
- Trash list auto-refreshes when items are deleted or restored

### Design choice
No background timer or scheduled cleanup — the app simply checks on startup. Simple and sufficient for a local dev server.

---

## Phase 9: Resize + Content Reveal Fix

### Prompt #11
> "Small glitch claude, when I expand a window and the text in it is currently 'hidden' aka toggled to the fade setting. The visible text doesn't change during the expansion as well. It would be nice if while you're expanding the fade stays connected to the bottom edge and the amount of text you want becomes more and more visible. Does that make sense?"

### Problem
When a node had a collapsed response (max-height: 320px) and the user resized the node taller, the response section stayed at 320px — the extra height was wasted as empty space below the response.

### Solution
- Added `.has-custom-height` CSS class to nodes with user-set height
- `.has-custom-height .node-response.collapsed` overrides to `max-height: none; flex: 1;`
- This lets the collapsed response fill available space as the node is resized
- The fade gradient stays pinned at the bottom throughout
- When expanding via toggle button, `clearCustomHeight()` removes the custom height so the node auto-sizes

---

## Phase 10: Cursors, Native Scroll, and Edge Tracking

### Prompt #12
> "Okay! You're doing great Claude. Okay really minor changes. When a mouse is hovering over a node and we are in the state where that node will scroll rather than zoom, I would like the mouse cursor to change to a cursor that makes it clear you are going to scroll not zoom. Then when over the canvas, can it be a hand/magnify glass icon so its clear you can both grab and move the canvas OR zoom with the scroll. Then when actually zooming it should JUST show the magnify glass and when moving the canvas around it should be the closed grabby hand that we currently have? can you make that work? Also, when the text of the prompt or the answer in a node is larger than the visible space of the node (it's collapsed) there should be scroll bars beside the nodes text fields so that you can mouse over and scroll the text. Can we handle that? We should also keep the lines properly connected to highlighted sections and when you scroll up or down, the lines should move with the highlighted text until it goes off the visible section of the node. Then the line should stop moving either at the bottom edge of the node or at the edge between the answer and prompt text. Does that make sense? Ask clarifying questions if needed."

### Clarifying questions asked
Two design decisions needed user input:

1. **Scroll behavior over nodes**: "Native scroll inside node" vs "Wheel always zooms canvas"
   - User chose: **Native scroll inside node**

2. **Edge clamping when highlight scrolls out of view**: "Clamp to response section top/bottom" vs "Clamp to node top/bottom"
   - User chose: **Clamp to response section top**

### What was built

**A. Context-sensitive cursors (`canvas.js`, `main.css`):**
- Canvas at rest: `cursor: grab` (open hand)
- During pan drag: `cursor: grabbing` (closed hand) via `.panning` class
- During wheel zoom: `cursor: zoom-in` or `cursor: zoom-out` via transient CSS classes
- 150ms debounced timer removes zoom cursor after scrolling stops
- Over nodes: `cursor: default` (inherited from node styles)

**B. Native scroll inside collapsed nodes:**

This required a significant HTML restructure to solve a subtle CSS problem.

**The problem with `::after` fade gradients:**
The original collapsed sections used `::after` pseudo-elements with `position: absolute` to create a fade-to-transparent gradient at the bottom. When changing from `overflow: hidden` to `overflow-y: auto` for scrolling, the `::after` pseudo-element scrolls away with the content instead of staying visually pinned at the bottom.

**The solution — HTML restructure:**

Collapsed sections went from:
```html
<div class="node-response collapsed">
    <div class="node-response-content">...</div>
</div>
```

To:
```html
<div class="node-response collapsed">          <!-- overflow: hidden -->
    <div class="node-section-scroll">          <!-- overflow-y: auto -->
        <div class="node-response-content">...</div>
    </div>
    <div class="section-fade"></div>            <!-- absolute positioned overlay -->
</div>
```

The outer section keeps `overflow: hidden`. The inner `.node-section-scroll` does the actual scrolling. The `.section-fade` div sits as a sibling outside the scroll flow, staying visually pinned at the bottom.

Expanded sections keep the flat structure (no scroll wrapper needed).

**CSS changes:**
- Removed `::after` pseudo-elements from `.node-prompt.collapsed` and `.node-response.collapsed`
- Added `.node-section-scroll` with `overflow-y: auto`, thin 4px scrollbar
- Added `.section-fade` with absolute positioning and gradient using `color-mix(in srgb, var(--bg-node) 80%, transparent)` to match node transparency

**Canvas wheel handler change:**
```javascript
// Before: e.preventDefault() was first line — blocked all native scroll
// After: check for node first, return early to allow native scroll
function onWheel(e) {
    const nodeEl = e.target.closest('.lt-node');
    if (nodeEl) {
        return;  // Let browser handle native scroll
    }
    e.preventDefault();
    // ... zoom logic
}
```

**C. Edge tracking during scroll (`edge.js`, `node.js`):**

Scroll events on `.node-section-scroll` elements trigger throttled edge redraws via `requestAnimationFrame`:

```javascript
let _edgeRedrawScheduled = false;
function throttledEdgeRedraw() {
    if (_edgeRedrawScheduled) return;
    _edgeRedrawScheduled = true;
    requestAnimationFrame(() => {
        EdgeRenderer.redrawAll();
        _edgeRedrawScheduled = false;
    });
}
```

Edge anchor clamping in `drawEdge()`:
1. Find the scroll container: `mark.closest('.node-section-scroll')`
2. If no scroll container (expanded): use direct `getBoundingClientRect()` position
3. If scroll container exists (collapsed + scrollable):
   - Get `scrollRect` and `markRect` via `getBoundingClientRect()`
   - If mark center is within scroll bounds: use actual position
   - If mark scrolled above visible area: clamp to `scrollRect.top`
   - If mark scrolled below visible area: clamp to `scrollRect.bottom`
   - Convert screen Y to world offset: `(screenY - nodeRect.top) / zoom`

This makes edges smoothly follow highlights as you scroll, then pin to the response section top/bottom when the highlight goes out of view.

---

## Phase 11: Child Node Positioning — Tree Layout

*Continued in same session (5c3bde94), post-documentation.*

### Prompt #15
> "Okay now I see a small bug, when I create a new node and it appears in the interface to the right of the node it was connected to, it sometimes appears under the node it started from, I think the location for the new node isn't taking into account its parent was potentially resized. Take a look at the image for an example. Can you fix that?"

Attached screenshot showing a child node overlapping its parent.

### Prompt #16
> "I mean that kind of worked. Here is an example and where it placed the next node, which was off the bottom right corner. what would be better. is if it was placed at the top right, see the second image. I also added screenshots for a 3rd node off of the first a 4th node off the of the second, and then a corrected layout. Can you try to get it to build out like the corrected layout in the final image."

Five attached screenshots showing actual vs desired tree layout.

### What was built
Complete rewrite of `computeChildPosition()` in `app.js`:
- **Tree layout**: First child aligns to parent's **top Y** (not below parent), creating a horizontal tree
- **Sibling stacking**: Subsequent children stack below the last sibling using actual DOM height
- **Collision avoidance**: Iterative algorithm checks all existing nodes for overlap, pushing down only when actual bounding-box overlap is detected (checks both horizontal and vertical overlap)
- Constants: `OFFSET_X = 500` (horizontal distance), `GAP_Y = 40` (vertical gap between nodes)

---

## Phase 12: Node Dimension Persistence on Reload

### Prompt #17
> "I also notice that when I reload, the size of all the nodes even if they have been resized go back to the original default size. We should be keeping the exact layout and going back to that exact layout and sizing."

### Problem
Node width, height, and collapsed states were being silently stripped on save. The `NodeData` Pydantic model was missing these fields, and Pydantic's default behavior drops unknown fields during validation.

### Solution
Added four missing fields to the `NodeData` model in `models.py`:
```python
width: Optional[float] = None
height: Optional[float] = None
prompt_collapsed: Optional[bool] = None
response_collapsed: Optional[bool] = None
```

This was a one-line-per-field fix with a disproportionate impact — without it, all dimension customization was lost on every reload.

---

## Phase 13: Edge Line Robustness

### Prompt #18
> "The line logic is slightly broken I am not sure how I got the image to this state but you can see one line is slightly off in the middle. As soon as I resized that window it snapped into position. Make the line connectivity checking logic a bit more robust."

Attached screenshot showing an edge with a visible kink.

### Problem
Edges were only redrawn on explicit user actions (drag, zoom). When node content reflowed (e.g., after `updateNode()` replaced innerHTML with a response), mark positions shifted but edges weren't updated.

### Solution — Three improvements
1. **ResizeObserver**: Each node gets a `ResizeObserver` that triggers a throttled edge redraw whenever the node's size changes (content reflow, images loading, etc.)
2. **Post-update redraw**: `updateNode()` now calls `requestAnimationFrame(() => EdgeRenderer.redrawAll())` after replacing innerHTML
3. **Multi-pass redraw on session load**: Added staggered redraws at 0ms, 100ms, and 500ms to handle layout settling during session restoration

---

## Phase 14: Scroll Over Expanded Nodes

### Prompt #19
> "The scrolling handling logic is a bit broken. It works great when there is a scrollbar present on the node, we scroll the text really well. But if you look at this screenshot, the first node is expanded (so no scrollbar) and the window is larger than the field of view of the entire web page (it clips off the bottom of the screen) when having our mouse hovering over that expanded window AND it is larger than the screen viewport we should be able to scroll up or down and have the entire canvas move up or down to allow me to see whats in that expanded node."

### Problem
The wheel handler returned early for *all* nodes (letting the browser handle scroll), even when the node had no scrollable content. Expanded nodes with `overflow: visible` would eat the scroll event with no visible effect.

### Solution
Added `findScrollableAncestor()` function in `canvas.js`:
- Walks from the event target up to the node boundary
- Checks if any ancestor has `overflow-y: auto|scroll` AND `scrollHeight > clientHeight` AND can scroll in the wheel direction
- If a scrollable ancestor exists: let browser handle native scroll
- If not: fall through to canvas pan (moves the entire canvas)

---

## Phase 15: Scroll Direction Inversion Fix

### Prompt #20
> "Okay we are getting there, if I try to scroll up, the canvas scrolls down. When I try to scroll down, nothing moves."

### Problem
`findScrollableAncestor()` was checking `scrollHeight > clientHeight` but not the CSS `overflow-y` property. Expanded nodes with `overflow: visible` technically have `scrollHeight > clientHeight` (content overflows), so they were incorrectly detected as "scrollable" — but only in one direction (down), causing the asymmetric behavior.

### Solution
Added `window.getComputedStyle(el).overflowY` check to `findScrollableAncestor()`:
```javascript
const overflowY = style.overflowY;
if ((overflowY === 'auto' || overflowY === 'scroll') &&
    el.scrollHeight > el.clientHeight + 1) { ... }
```
Only elements with explicit scroll overflow are treated as scrollable. Elements with `overflow: visible` (expanded nodes) are correctly skipped, allowing the canvas pan to handle the wheel event.

---

## Phase 16: Edge Redraw on Collapse/Expand Toggle

*New session continuation (context compaction boundary).*

### Prompt #21
> "Take a look at the screenshot. What happened here was, the first node was expanded and those edges from it to the second nodes were lined up with highlighted text or locked at top or bottom of the answer section. When I collapsed the expanded node. The lines didn't redraw to the appropriate location in the text. Can you clean that up? If any of the highlighted text is still visible after the collapse the line should be correctly drawn otherwise the line should be redrawn to the locked edge it should be at."

Attached screenshot showing misaligned edge lines after collapsing.

### Problem
The toggle handlers (both header buttons and click-to-expand) only toggled the `.collapsed` CSS class — they didn't rebuild the HTML structure. The collapsed HTML structure uses `.node-section-scroll` wrapper divs that the edge code depends on for scroll-aware clamping. After toggling via CSS alone:
- Collapsing: No `.node-section-scroll` wrapper → edge code takes the "expanded" path → uses stale mark positions from the now-clipped content
- Expanding: `.node-section-scroll` wrapper still present → edge code takes the "collapsed" path incorrectly

### Solution
Created `rebuildInnerHTML(el, nodeData, opts)` function in `node.js`:
1. Syncs `nodeData` from the session (in case collapsed state was updated on a different object reference)
2. Saves current width/height
3. Calls `buildNodeHTML(nodeData)` to regenerate full HTML with correct structure
4. Restores saved dimensions
5. Re-wires inner interactions via `wireInnerInteractions()`
6. Triggers `requestAnimationFrame(() => EdgeRenderer.redrawAll())`

Both `setupToggleButtons()` and `setupExpandCollapse()` now call `rebuildInnerHTML()` instead of toggling CSS classes, ensuring the DOM structure always matches the collapsed state.

---

## Phase 17: Edge Anchor Precision and Scroll Absorption

### Prompt #22
> "Almost, the lines are just a bit too low. Also, I noticed when the window wasn't in the expanded state (so there is a scroll bar) and I was scrolling and the scroll bar got to the top, the canvas started scrolling. The canvas should never scroll when your mouse is hovering over a block that isn't expanded. It should only ever scroll the canvas when the node it is hovering over is in the expanded state."

### Two fixes

**A. Edge anchor Y offset:**

The edge clamping code was using `scrollContainer.getBoundingClientRect()` for clamp bounds, but the scroll container can extend beyond the visible area of `.node-response.collapsed` (which has `overflow: hidden` and `max-height: 320px`). The response section's rect is the correct visible bound.

Changed edge.js to clamp against `responseSection.getBoundingClientRect()` instead of `scrollContainer.getBoundingClientRect()`.

**B. Scroll absorption on collapsed nodes:**

When scrolling inside a collapsed node hit the top or bottom bound, `findScrollableAncestor()` returned null (can't scroll further), causing the wheel event to fall through to canvas pan. This created jarring behavior — the canvas would suddenly start moving when you hit the scroll bounds.

Added a check in `onWheel()`: if the cursor is over a `.node-section-scroll` element (collapsed section), always absorb the event (`preventDefault` + return). Canvas panning only happens when hovering an *expanded* node that has no scrollable content.

---

## Phase 18: Viewport State Persistence

*Note: Between Phase 17 and Phase 18, the development journey and system architecture documents were updated (Prompt #23). That was a documentation-only pass, not a code phase.*

### Prompt #24
> "I am noticing that when I open a canvas that already has work on it, it loads with the first node half off the screen to the left. Can you fix it so the page opens to the exact location it was at previously? So if I had the 5th node in the top left corner (for example) when I switch away from this or load after a restart the 5th node would be in the exact same spot in the top left corner."

Attached screenshot showing a node positioned half off-screen after reloading a session.

### Prompt #25
> "It's not quite working. I can't pinpoint why. What I do know is, when I move the canvas, then click the different session on the left and move the other canvas, then click back to the other session, it's not where I left it. I think I did get it to work after a reload, but then it didn't work again. I am not sure whats going on."

### Problem
Viewport state (pan/zoom) was not being reliably persisted. Three separate gaps:
1. **Pan and zoom changes never triggered a save** — only node edits and timer-based auto-saves captured viewport state
2. **Switching sessions didn't flush pending saves** — the debounced save for session A might fire *after* session B was already loaded, overwriting B's data with A's state
3. **Page close/reload lost state entirely** — the debounced save timer was cancelled by page teardown before it could fire

### Solution — Three coordinated fixes

**A. Save on viewport changes (`canvas.js`):**
- Added `Session.scheduleSave()` call in `onMouseUp()` after panning ends
- Added `Session.scheduleSave()` after wheel-pan over expanded nodes
- Added `Session.scheduleSave()` after zoom operations

**B. Flush before session switch (`session.js`):**
- Created `flushSave()` function that clears the debounce timer and calls `doSave()` immediately
- `loadSession()` now calls `await flushSave()` before loading the new session

**C. Reliable save on page close (`session.js`):**
- Added `beforeunload` event handler that synchronously captures viewport state and node positions into `currentSession`
- Uses `navigator.sendBeacon()` to reliably send the data during page teardown (fetch/XHR can be cancelled by the browser, but sendBeacon is guaranteed to complete)

**D. Dual-method endpoint (`app.py`):**
- `sendBeacon()` sends POST requests, but the save endpoint was PUT-only
- Changed to `@app.api_route("/api/sessions/{session_id}", methods=["PUT", "POST"])` to accept both

---

## Phase 19: Zoom Speed Reduction

### Prompt #26
> "Yeah this is working really well. Can you make the zoom less agressive. It zooms really fast on scroll can you slow that down a little."

### What was changed
Single constant change in `canvas.js`:
- `ZOOM_STEP` reduced from `0.1` to `0.04`
- This makes each scroll tick zoom 60% less, giving much finer control

---

## Phase 20: SalesChat Live Mode Debugging

### Prompt #27
> "Can you make sure that when the system in non-mock mode calls the SalesChat.py script it launches it in NON headless. I want to see the saleschat window working while I go debug this. There are flags in the saleschat script to accomplish this."

### What was changed
Removed the `--headless` flag from the subprocess command in `saleschat_bridge.py`:
```python
cmd = [
    self._python,
    self._script,
    "--prompt-file", str(prompt_path),
    "--output-dir", str(output_dir),
    "--auto-close",
    # No --headless: browser window visible for debugging
]
```

This allowed the user to observe SalesChat's browser automation in real time, which led directly to the discovery in Phase 21.

---

## Phase 21: Raw Response Extraction (Remove Email Formatting)

### Prompt #28
> "Hey Claude, why are the responses from saleschat coming back like they are formatted for our sales chat email report system. We don't want any of that. We are in this case just using the SalesChat.py code to act as a conduit into SalesChat, it lets us use the specialized AI. I just started the learning tool as a sub project of our automation directory because I wanted the knowledge and experience and code to be available for the learning_tool but the learning_tool is going to ultimately be its own standalone thing."

Attached screenshot showing a response node titled "SalesChat Report — 2026-03-10" with colored section headers and email-style formatting.

### Problem
SalesChat.py was designed for the Jarvis daily email report system. When it captures an AI response, it:
1. Saves the raw text as `saleschat_response_*.txt`
2. Parses it with Beautiful Soup and generates an email-formatted HTML version as `saleschat_response_*.html` (via `build_html_email()`)

The Learning Tool's `saleschat_bridge.py` was reading the `.html` file first (the email-formatted version), so responses came back with report titles, colored section headers, and email layout tables — completely wrong for a knowledge exploration tool.

### Solution
Changed `saleschat_bridge.py` to read only the `.txt` file (raw AI response), ignoring the email-formatted `.html` entirely:

```python
# Before: read .html first, then .txt as fallback
# After: read only .txt — the raw AI response
txt_files = sorted(
    output_dir.glob("saleschat_response_*.txt"),
    key=lambda f: f.stat().st_mtime, reverse=True,
)
if txt_files:
    text = txt_files[0].read_text(encoding="utf-8", errors="replace")
    return {"text": text, "html": ""}
```

---

## Phase 22: Markdown Normalization and Render Priority

### Prompt #29
> "Okay, that stripped out the report formatting but now the response is really hard to read. Do you think we could use our local AI to clean up the formatting for us before we put it into the text? OR is there a simple algorithm that can help clean it up. What do you think is the best approach to make it readable?"

### Prompt #30
> "can you run it against the existing example so I can see how it was corrected?"

### Prompt #31 (with screenshot)
> "Are you sure that worked? This is the output, it doesn't look all that great."

Screenshot showing VxRail response as flat, unformatted plain text — no headers, no bullets.

### Prompt #32 (with screenshots)
> "The dell automation platform one seems to look better (see screenshot) but the vxrail one doesn't. See the other screenshot. Not sure why. I restarted the web server, I closed and opened the pages in new tabs, did an F5 refresh."

Two screenshots: DAP response with proper headers/structure vs VxRail response still flat text.

### Problem (two parts)

**A. Raw text needed formatting normalization:**
The raw AI text from SalesChat was *almost* markdown but not quite. It used numbered section headers without `##` prefix (e.g., `1. What Dell Automation Platform is`), em-dash bullets (`–`) instead of `- `, and short label-like sub-headers without any markdown syntax. The `marked.js` parser couldn't recognize these patterns.

**B. Render priority was wrong:**
`renderResponse(html, text)` checked `html` first. When a session was saved, `doSave()` captured `response_html = responseContent.innerHTML` from the DOM. On reload, this saved HTML was truthy and used directly — bypassing `marked.js` entirely. For some responses, this meant the raw text went through `escapeHTML()` (plain text fallback) on first render, got saved as that escaped HTML, and then was served as-is on reload.

### Solution

**A. `normalizeMarkdown()` function in `node.js`:**

A deterministic text cleanup algorithm (no LLM needed) that runs before `marked.parse()`:

1. **Em-dash/en-dash bullets** → standard `- ` markdown bullets
   - `– central place to onboard...` → `- central place to onboard...`

2. **Numbered section headers** → `##` headers with blank line before
   - `1. What Dell Automation Platform is` → `## 1. What Dell Automation Platform is`

3. **Short title-like sub-headers** → `###` headers with blank lines around
   - Detects lines that are short (< 60 chars, ≤ 8 words), don't end with sentence punctuation (`. ! ? : , ;`), don't contain `: ` or `, ` (which indicate content lines, not headers), and are preceded by a section break (blank line, end of sentence, or another header) and followed by longer content
   - `Velocity` → `### Velocity`
   - `Core software stack` → `### Core software stack`
   - `Portal (Control Plane)` → `### Portal (Control Plane)`

The algorithm was tested against two real SalesChat responses (Dell Automation Platform and PowerScale/VxRail) with very different formatting patterns. The DAP response had numbered sections; the VxRail response had unnumbered headers with no blank lines between sections. Both required different detection strategies.

**Key refinements during testing:**
- Added `:` to sentence-ending punctuation exclusions to prevent lines like "From the general and services FAQs plus the ordering guide:" from becoming false headers
- Added `, ` (comma-space) check to prevent list-like content lines from becoming headers (e.g., "Flexible erasure-coding style protection levels across the cluster")
- Added word count limit (≤ 8 words) to further restrict to true label-like headers
- Relaxed the "must be preceded by blank line" requirement — instead checks for section breaks (blank line OR end of previous sentence OR previous line is a header)
- Ensures blank lines before and after detected headers so `marked.js` treats them as proper headers

**B. Render priority flip in `renderResponse()`:**

```javascript
// Before: prefer HTML, fallback to markdown
function renderResponse(html, text) {
    if (html) { return html; }
    if (text && typeof marked !== 'undefined') { return marked.parse(normalizeMarkdown(text)); }
    return escapeHTML(text || '');
}

// After: prefer markdown from raw text, fallback to HTML
function renderResponse(html, text) {
    if (text && typeof marked !== 'undefined') { return marked.parse(normalizeMarkdown(text)); }
    if (html) { return html; }
    return escapeHTML(text || '');
}
```

This ensures `response_text` is always re-rendered through `marked.js` + `normalizeMarkdown()`, even after save/reload cycles. The saved `response_html` (from `doSave()` capturing innerHTML) is only used as a fallback when no raw text is available.

---

## Phase 23: Platform Migration — Remove SalesChat, Target Chimera AI Server

### Context

The Learning Tool was originally developed on Windows, using SalesChat.py (a browser automation tool for Glean Chat) as the LLM backend when on VPN, with a local llama.cpp instance as the `--mock` fallback. The project was migrated to a Linux workstation (Ubuntu) with a dedicated AI server ("chimera") on the local network running an OpenAI-compatible LLM endpoint.

### Changes

**Removed SalesChat entirely:**
- Deleted the `SalesChatQueue` class from `saleschat_bridge.py` (subprocess launcher, asyncio lock, temp file handling, SSO error messages)
- Removed `--mock` flag — the local LLM is now the only backend, not a "mock"
- Removed `--saleschat-dir` and `--saleschat-script` CLI args
- Removed `MOCK_MODE` logic, `SALESCHAT_DIR` path, and all SalesChat references from `app.py`
- Simplified startup messages to just show LLM endpoint and model

**Renamed `saleschat_bridge.py` → `llm_bridge.py`:**
- Updated import in `app.py` and reference in `CLAUDE.md`
- File now contains only `LocalLLMQueue` — a clean async wrapper around the OpenAI-compatible API

**Retargeted LLM endpoint:**
- Default URL changed from `http://localhost:8081/v1/chat/completions` to `http://192.168.1.221:8080/v1/chat/completions` (chimera AI server)
- Default model name set to empty string (server serves whichever model is loaded)

**Pydantic v1 compatibility:**
- The apt-installed FastAPI/Pydantic on Ubuntu is v1, which uses `.dict()` instead of v2's `.model_dump()`
- Fixed both calls in `app.py` (`req.dict()` in `submit_query` and `save_session`)

**Updated `CLAUDE.md`:**
- Simplified quick start (no `--mock`), CLI args table, architecture description, and dependency list

---

## Phase 24: LLM Thinking Token Filtering

### Problem

The OSS-120b model on chimera produces chain-of-thought reasoning before its actual response. The thinking content leaked into the displayed output in multiple formats:
1. Full special token format: `<|start|>assistant<|channel|>analysis<|message|>...thinking...<|end|><|start|>assistant<|channel|>final<|message|>...response...`
2. Bare "analysis" prefix (when the server strips token delimiters but leaves content)
3. `<think>...</think>` blocks (common in other models)

### Solution

Added `_strip_thinking()` function in `llm_bridge.py` that handles all three formats:
- Regex removal of `<think>...</think>` blocks
- Regex removal of everything up to `<|channel|>final<|message|>` marker
- Cleanup of remaining stray `<|...|>` tokens
- Detection of bare "analysis" prefix → cut everything before the first markdown header (`## `)

Added `_has_thinking()` helper for streaming detection of thinking content regardless of token format.

---

## Phase 25: SSE Streaming with Progressive Token Display

### Problem

The original architecture used a poll-based approach: submit query → get job ID → poll `/api/query/{job_id}/status` every 3 seconds. Users saw "Thinking..." for the entire duration (often 30+ seconds for long responses), with no indication of progress until the full response arrived at once.

### Architecture Change

Replaced polling with Server-Sent Events (SSE) for real-time token streaming.

**Backend (`llm_bridge.py`):**
- Added `stream()` async generator method that yields typed events: `thinking`, `token`, `done`, `error`
- Added `_stream_llm()` synchronous generator that calls the OpenAI API with `stream: true`, parses SSE chunks via `readline()`, and detects thinking vs content phases
- Phase detection state machine: `detecting` → `thinking` → `content`
  - In `detecting`: buffers first ~15 chars, checks for thinking indicators (`analysis`, `<|channel|>analysis`, `<think>`)
  - In `thinking`: watches for content transition (first markdown header `^#{1,6}\s` or `<|channel|>final<|message|>`)
  - In `content`: yields individual tokens directly
- Thread-to-async bridge using `asyncio.Queue` + `loop.call_soon_threadsafe()` to keep the blocking HTTP stream async
- Non-streaming fallback: if server returns `application/json` instead of `text/event-stream`, reads full response and applies `_strip_thinking()` as if non-streaming
- Final safety net: always applies `_strip_thinking()` to the complete content buffer before the `done` event

**Backend (`app.py`):**
- Added `POST /api/query/stream` endpoint returning `StreamingResponse` with `text/event-stream` content type
- SSE event sequence: `prompt` (engineered prompt for storage) → `thinking` → `token` × N → `done`
- Old polling endpoints (`/api/query`, `/api/query/{job_id}/status`) retained as fallback

**Frontend (`api.js`):**
- Added `streamQuery(data, callbacks)` function using `fetch` + `ReadableStream` reader
- Parses SSE `event:` and `data:` lines from chunked responses
- Dispatches to callbacks: `onPrompt`, `onThinking`, `onToken`, `onDone`, `onError`
- Handles remaining buffer after stream ends (edge case where last event doesn't end with newline)

**Frontend (`app.js`):**
- Replaced all `API.submitQuery()` + `pollJob()` patterns with `streamQueryToNode()`
- `streamQueryToNode` wires SSE callbacks to node rendering:
  - `onPrompt`: stores engineered prompt in session data
  - `onThinking`: updates node to "running" state (only if content hasn't started)
  - `onToken`: calls `NodeRenderer.streamToken()` for incremental display
  - `onDone`: calls `NodeRenderer.finishStreaming()` for final render
- Removed `POLL_INTERVAL` constant and `pollJob()` function

**Frontend (`node.js`):**
- Added `streamToken(nodeId, text)`: initializes streaming container on first token (replacing thinking indicator), appends text to buffer, debounced markdown render every 150ms via `marked.parse(normalizeMarkdown(buffer))`
- Added `finishStreaming(nodeId, fullText)`: clears streaming state, explicitly sets collapsed defaults, calls `updateNode` for final render with full features (highlights, collapse/expand, etc.)
- Streaming container uses collapsed layout (`node-response collapsed streaming` with scroll wrapper and fade overlay) to match the default collapsed appearance

**Frontend (`main.css`):**
- Added blinking cursor indicator (`.node-response.streaming .node-response-content::after`) with `cursor-blink` animation

### UX Flow

1. User submits query → node shows "Thinking..." with animated dots
2. Model starts outputting content → thinking indicator replaced by streaming response area with blinking cursor
3. Tokens render progressively as markdown (debounced every 150ms)
4. Stream completes → cursor disappears, final render with full features (collapse/expand toggles, highlight selection, etc.)

---

## Phase 26: Table Formatting Fix in Markdown Normalizer

### Problem

The `normalizeMarkdown()` function's sub-header detection was incorrectly matching markdown table rows. Lines like `| Source | How it's used |` are short, don't end with sentence punctuation, and passed all the heuristic checks — getting wrapped in `### ` which broke the table syntax and caused extra empty rows in rendered output.

### Fix

Added table-row exclusions to the sub-header detection in `node.js`:
- Skip lines starting with `|` (pipe character)
- Skip lines ending with `|`
- Skip lines containing ` | ` (pipe with spaces — table column separator)

---

## Phase 27: LaTeX Math Rendering with KaTeX

### Prompt #42 — Math formulas displaying as raw LaTeX
> "Notice in this screenshot the model is attempting to print math formulas but we don't seem to be equipped to display them. Can you help with that?"

Screenshot showed a node about Transformer-based embedding models where LaTeX math notation (`\mathbf{E}`, `\mathbb{R}^{d\times V}`, `\in`, etc.) was rendering as raw text instead of formatted equations. Display math blocks using `\[...\]` and inline math using `\(...\)` were all plaintext.

### What was built

**KaTeX integration** — full client-side LaTeX math rendering vendored locally (no CDN), integrated into the existing markdown rendering pipeline.

**Vendored library (`static/vendor/katex/`):**
- Downloaded KaTeX v0.16.21 (CSS, JS, auto-render extension, 60 font files)
- Served from existing FastAPI static mount — no config changes needed

**HTML (`index.html`):**
- Added `katex.min.css` stylesheet
- Added `katex.min.js` and `contrib/auto-render.min.js` scripts

**Rendering pipeline (`node.js`):**
- `renderMath(el)` — calls KaTeX `renderMathInElement()` on a DOM element with standard delimiter support (`$$`, `\[...\]`, `\(...\)`, `$...$`)
- `parseMdWithMath(text)` — protects LaTeX blocks from marked.js corruption by stashing math expressions as `%%MATH_N%%` placeholders before markdown parsing, then restoring them after. Handles display math (`$$`, `\[...\]`), inline math (`\(...\)`, `$...$`), and avoids false positives on currency (`$10`)
- `renderMath()` called at all four HTML insertion points: `createNode`, `updateNode`, `rebuildInnerHTML`, and streaming token render
- Streaming render uses `parseMdWithMath()` instead of raw `marked.parse()` so math renders progressively during streaming

**CSS (`main.css`):**
- `.katex-display` gets horizontal scroll for wide equations that exceed node width
- `.katex` font size normalized to `1em` to match surrounding text

### Technical approach

The key challenge was that marked.js (the markdown parser) mangles LaTeX backslash sequences. The solution uses a two-pass approach:
1. **Pre-process**: Regex-extract all math delimited blocks, replace with unique placeholders
2. **Markdown parse**: Run `marked.parse()` on the placeholder-safe text
3. **Restore**: Replace placeholders with original LaTeX strings in the HTML output
4. **KaTeX render**: Call `renderMathInElement()` on the DOM element to convert LaTeX to rendered math

This preserves both markdown formatting and math rendering without conflicts.

---

## Phase 28: Question Badge Shows User's Question

### Prompt #43 — Show the question text in the node header
> "When we use the right click option to ask a question, can you make sure the header of the question box has beside QUESTION the actual short form question that was asked?"

### What was built

- Store user's question in `user_question` field on node data when submitting a question
- Badge rendering in `buildNodeHTML()` appends the question text after "QUESTION" for question-mode nodes: `QUESTION — Can you show me a fully calculated small scale...`
- Question text truncated to 60 chars with `...` if longer
- CSS: `.badge-question-text` renders in normal case (not uppercase), lighter weight, slight opacity reduction to distinguish from the badge label
- Badge element gets `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` for graceful overflow

---

## Phase 29: Linear Context Growth — Prompt/Lineage Separation

### Prompt #44 — LLM returning 400 Bad Request due to context size
> "We are having a failure reaching the LLM"

Error: `HTTP Error 400: Bad Request` from the LLM server. Investigation revealed the lineage context was growing **exponentially** — each node's `prompt_text` was being overwritten with the full engineered prompt (which itself contained all previous lineage), so each successive layer doubled the context size.

### Prompt #45 — Fix context growth without losing "in context" design
> "Can we fix that so we build the context from history lineage but we don't append previous context to each successive layers stored prompt... Only using the user question defeats the purpose of the in context nature of this design."

### Root cause

The `onPrompt` SSE callback in `streamQueryToNode()` was storing the full engineered prompt (containing accumulated lineage from all ancestors) into `session.nodes[nodeId].prompt_text`. When building lineage for a child node, `prompt_engineer.py` walked the parent chain reading each node's `prompt_text` — which now contained nested copies of all prior context. Result: exponential growth.

### Fix — separate storage, linear reconstruction

**Data model change:**
- `prompt_text` — stores only the **user-facing description** (what the user typed or a summary of their action)
- `engineered_prompt` — stores the full prompt actually sent to the LLM (for display when user expands the prompt section)

**`app.js` changes:**
- `onPrompt` callback now writes to `session.nodes[nodeId].engineered_prompt` instead of overwriting `prompt_text`
- `spawnChild()` sets meaningful `prompt_text` summaries: `'Explain: "highlighted text"'`, `'Deep dive: "highlighted text"'`
- `submitQuestion()` keeps `prompt_text` as the user's typed question (unchanged)

**`node.js` changes:**
- `buildNodeHTML()` displays `engineered_prompt` (if available) in the expandable prompt section, falling back to `prompt_text`
- `showPromptToggle` checks both fields

**Result:**
- Lineage context now grows **linearly** — each node contributes only its short user-facing prompt + truncated response (max 1500 chars)
- The full engineered prompt is still viewable by expanding the prompt section
- The backend rebuilds the full context from lineage each time, so no information is lost

### Also fixed: KaTeX strict mode warnings
- Set `strict: false` in `renderMathInElement()` options to suppress warnings about Unicode characters (zero-width spaces, non-breaking hyphens) in LLM output

---

## Phase 30: Multi-Line Highlight Fix — Empty Gaps and Reapply Robustness

### Prompt #47 — Empty lines between highlighted bullet points
> "Look at these multi line highlighting queries. These once the new node is created after the question is asked or other action is taken it seems to screw up the text so there are empty lines between the highlighted lines."

Screenshots showed that when highlighting text across multiple `<li>` bullet items, the resulting highlights had visible empty gaps between the bullet lines. This happened because the TreeWalker in `createHighlight()` was wrapping whitespace-only text nodes (newlines between `</li>` and `<li>` in the DOM) in `<mark>` elements, which rendered as empty highlighted lines.

### Prompt #48 — Fix broke all multi-line highlighting
> "Looks like that broke some of the highlighting. Single words seem fine but some of it has disappeared entirely. I think all multiline is broken now."

First fix attempt was too aggressive — filtering whitespace nodes by all block-level parents (`LI`, `DIV`, etc.) caused legitimate text nodes to be excluded from highlights. Narrowed the filter scope.

### Prompt #49 — Still broken after narrowing filter
> "Still broken for multiline."

Revealed the deeper issue: highlights were being created correctly in the DOM, but lost on re-render. When a node re-renders (collapse/expand toggle, session reload), `buildNodeHTML()` regenerates HTML from `response_text` via `renderResponse()` which prefers raw text → markdown, discarding all `<mark>` elements. The `reapplyHighlights()` function then calls `findAndWrapText()` to restore them, but its `indexOf` search failed for cross-element selections because `window.getSelection().toString()` normalizes whitespace differently than the concatenated DOM text content (which includes newline/space characters between block elements).

### Root cause (two issues)

1. **Highlight creation**: `createHighlight()` TreeWalker wrapped whitespace-only text nodes between `<li>` elements in `<mark>`, creating visible empty highlighted lines
2. **Highlight reapply**: `findAndWrapText()` used exact `indexOf` matching which failed when selection text whitespace didn't match DOM whitespace

### Fix

**`context_menu.js` — targeted whitespace filtering:**
- Only skip whitespace-only text nodes that are direct children of `UL`, `OL`, `TABLE`, or `TBODY` — the structural whitespace between list items and table rows
- Leave all other text nodes alone (including those inside `LI`, `DIV`, inline elements)

**`node.js` `findAndWrapText()` — whitespace-normalized fallback matching:**
- First tries exact `indexOf` match (fast path for single-element highlights)
- If that fails, collapses all whitespace runs to single spaces in both the search text and the concatenated DOM text
- Builds a position map (`normMap`) from normalized string positions back to original DOM text positions
- Uses the map to translate the normalized match back to exact DOM offsets for wrapping

**`main.css` — defensive CSS:**
- `mark.lt-highlight:empty { display: none }` — hides any truly empty marks
- `ul > mark.lt-highlight`, `ol > mark.lt-highlight`, etc. — hides stray marks that are direct children of block containers (from old saved sessions)

---

## Summary of All User Prompts (Chronological)

| # | Prompt Summary | Phase |
|---|---------------|-------|
| 1 | Full project specification with wireframe | 1 |
| 2 | Hand-drawn wireframe image | 1 |
| 3 | "Please continue" (after interruption) | 1 |
| 4 | Use local LLM in WSL2 container as mock backend | 2 |
| 5 | Port binding error report | 2 |
| 6 | Scroll-over-nodes, fix edges, auto-title sessions | 3 |
| 7 | Edge line fixes, expand-on-click, transparency, green highlights | 4 |
| 8 | Node overlap bug, drag-to-move broken | 5 |
| 9 | Collapsed edge detection, first node transparency, more transparent | 6 |
| 10 | Toggle buttons, resize handles, state persistence (with screenshot) | 7 |
| 11 | "Did delete work?" | 7 |
| 12 | Trash can with 30-day retention | 8 |
| 13 | Resize doesn't reveal more text (fade stays fixed) | 9 |
| 14 | Cursors, scrollbars, edge tracking during scroll | 10 |
| 15 | Child node overlapping parent (screenshot) | 11 |
| 16 | Tree layout — first child at top-right, not bottom (5 screenshots) | 11 |
| 17 | Node dimensions lost on reload | 12 |
| 18 | Edge line kink — snaps into place on resize (screenshot) | 13 |
| 19 | Can't scroll canvas when hovering expanded node larger than viewport | 14 |
| 20 | Scroll direction inverted — up scrolls down, down does nothing | 15 |
| 21 | Edge lines don't redraw when collapsing expanded node (screenshot) | 16 |
| 22 | Edge lines too low + canvas scrolls when at scroll bounds of collapsed node | 17 |
| 23 | Update development journey and system architecture docs | — (docs) |
| 24 | Viewport not restored when reopening sessions (screenshot) | 18 |
| 25 | Viewport still not persisting when switching sessions | 18 |
| 26 | Zoom too aggressive on scroll wheel | 19 |
| 27 | Launch SalesChat in non-headless mode for debugging | 20 |
| 28 | Responses formatted as email reports instead of raw AI output (screenshot) | 21 |
| 29 | Response hard to read after stripping email format — need formatting | 22 |
| 30 | Run normalizer against example to verify output | 22 |
| 31 | VxRail response still unformatted (screenshot) | 22 |
| 32 | DAP formatted correctly but VxRail not — different text patterns (screenshots) | 22 |
| 33 | Remove SalesChat, target chimera AI server | 23 |
| 34 | Rename saleschat_bridge.py to llm_bridge.py | 23 |
| 35 | Fix Pydantic v1 `.dict()` compatibility | 23 |
| 36 | Filter out LLM thinking tokens from output | 24 |
| 37 | Handle bare "analysis" prefix when server strips token delimiters | 24 |
| 38 | Switch from polling to SSE streaming with progressive token display | 25 |
| 39 | Streaming tokens not showing — fix SSE buffer parsing and race conditions | 25 |
| 40 | Fix table rows being misidentified as sub-headers in normalizeMarkdown | 26 |
| 41 | Fix new nodes showing expanded instead of collapsed after streaming | 25 |
| 42 | Math formulas displaying as raw LaTeX — add KaTeX rendering | 27 |
| 43 | Show question text in QUESTION node badge header | 28 |
| 44 | LLM 400 error — context too large from exponential lineage growth | 29 |
| 45 | Fix context growth linearly without losing "in context" design | 29 |
| 46 | KaTeX strict mode warnings for Unicode characters in LLM output | 29 |
| 47 | Multi-line highlights create empty gaps between bullet lines | 30 |
| 48 | First fix broke all multi-line highlighting | 30 |
| 49 | Still broken — deeper issue with highlight reapply after re-render | 30 |

## Summary of All Changes by File

| File | Changes |
|------|---------|
| `app.py` | Trash cleanup on startup, trash API endpoints, title generation endpoint, CLI args, dual-method PUT/POST save endpoint for sendBeacon (Phase 18), removed SalesChat/mock mode, added SSE streaming endpoint `/api/query/stream`, Pydantic v1 `.dict()` fix (Phase 23, 25) |
| `models.py` | Added `width`, `height`, `prompt_collapsed`, `response_collapsed` to `NodeData` (Phase 12) |
| `prompt_engineer.py` | Three prompt modes with lineage context. Now reads short `prompt_text` (user-facing) instead of full engineered prompts — enables linear context growth (Phase 29) |
| `llm_bridge.py` | Renamed from `saleschat_bridge.py`. Removed `SalesChatQueue` class. `LocalLLMQueue` with non-streaming `submit()` and streaming `stream()` async generator. `_strip_thinking()` for multi-format thinking token removal. `_has_thinking()` for streaming detection. Non-streaming fallback when server doesn't support SSE (Phases 23-25) |
| `session_manager.py` | Added soft-delete, trash CRUD, 30-day auto-cleanup |
| `static/index.html` | Added trash section in sidebar, KaTeX CSS/JS includes (Phase 27) |
| `static/css/main.css` | Resize handles, cursor classes, scroll containers, fade overlays, trash styles, transparency, highlight colors, streaming cursor animation (Phase 25), KaTeX display math scroll and font sizing (Phase 27), `.badge-question-text` styling for question node headers (Phase 28), defensive hide rules for stray highlight marks in block containers (Phase 30) |
| `static/js/api.js` | Added trash, title generation, and `streamQuery()` SSE streaming endpoints (Phase 25) |
| `static/js/app.js` | Auto-title generation on first prompt, tree-layout child positioning with collision avoidance (Phase 11), replaced polling with `streamQueryToNode()` SSE streaming (Phase 25), `user_question` field + badge text for question nodes (Phase 28), separated `engineered_prompt` from `prompt_text` storage for linear context growth (Phase 29) |
| `static/js/canvas.js` | Native scroll pass-through, zoom cursor feedback, `findScrollableAncestor()` with overflow-y check, scroll absorption on collapsed nodes (Phases 14-15, 17), viewport save on pan/zoom (Phase 18), reduced `ZOOM_STEP` 0.1→0.04 (Phase 19) |
| `static/js/context_menu.js` | Highlight creation, targeted whitespace node filtering for cross-element selections (Phase 30) |
| `static/js/edge.js` | Collapsed mark detection, scroll-aware clamping against response section bounds (Phases 6, 10, 17) |
| `static/js/node.js` | Toggle buttons, resize handles, HTML restructure, scroll listeners, `ResizeObserver` for edge redraws, `rebuildInnerHTML()` for collapse/expand toggle, state persistence, drag fixes (Phases 7-10, 13, 16), `normalizeMarkdown()` text cleanup + `renderResponse()` priority flip (Phase 22), table-row exclusion in sub-header detection (Phase 26), `streamToken()` and `finishStreaming()` for progressive streaming display (Phase 25), `renderMath()` + `parseMdWithMath()` for KaTeX LaTeX rendering with placeholder protection from marked.js (Phase 27), question text in badge header + `engineered_prompt` display in prompt section + force collapse on running status (Phases 28-29), `findAndWrapText()` whitespace-normalized fallback for cross-element highlight reapply (Phase 30) |
| `static/vendor/katex/` | Vendored KaTeX v0.16.21 — CSS, JS, auto-render extension, 60 font files (Phase 27) |
| `static/js/session.js` | DOM state capture in save, trash UI, restore, multi-pass edge redraw on load (Phase 13), `flushSave()` before session switch, `beforeunload` + `sendBeacon` for reliable save on page close (Phase 18) |
