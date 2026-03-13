/**
 * node.js — Node creation, rendering, drag, expand/collapse, resize.
 * Each node is a prompt/response pair displayed as an HTML div on the canvas.
 */

const NodeRenderer = (() => {
    const DRAG_THRESHOLD = 5;
    const MIN_WIDTH = 200;
    const MIN_HEIGHT = 80;

    // Throttled edge redraw for scroll events (at most once per animation frame)
    let _edgeRedrawScheduled = false;
    function throttledEdgeRedraw() {
        if (_edgeRedrawScheduled) return;
        _edgeRedrawScheduled = true;
        requestAnimationFrame(() => {
            EdgeRenderer.redrawAll();
            _edgeRedrawScheduled = false;
        });
    }

    // Configure marked for safe rendering
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true });
    }

    /** Render LaTeX math expressions in an element using KaTeX auto-render. */
    function renderMath(el) {
        if (typeof renderMathInElement !== 'function') return;
        try {
            renderMathInElement(el, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '\\[', right: '\\]', display: true },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '$', right: '$', display: false },
                ],
                throwOnError: false,
                strict: false,
            });
        } catch (e) {
            // KaTeX parse errors are non-fatal
        }
    }

    /**
     * Create a node DOM element and add it to the canvas.
     * @param {object} nodeData — { id, x, y, prompt_text, prompt_mode, response_html, response_text, status, width, height, prompt_collapsed, response_collapsed }
     * @param {object} opts — { editable: bool (for "ask a question" mode) }
     * @returns {HTMLElement}
     */
    function createNode(nodeData, opts = {}) {
        const el = document.createElement('div');
        el.className = 'lt-node';
        el.id = nodeData.id;
        el.style.left = nodeData.x + 'px';
        el.style.top = nodeData.y + 'px';

        // Apply saved dimensions
        if (nodeData.width) {
            el.style.width = nodeData.width + 'px';
        }
        if (nodeData.height) {
            el.style.height = nodeData.height + 'px';
            el.style.overflow = 'hidden';
            el.classList.add('has-custom-height');
        }

        el.innerHTML = buildNodeHTML(nodeData, opts);
        renderMath(el);

        Canvas.getWorld().appendChild(el);

        // Wire drag on the outer element (survives innerHTML replacements)
        setupDrag(el, nodeData);

        // Wire resize on the outer element (survives innerHTML replacements)
        setupResize(el, nodeData);

        // Wire inner interactions (these re-bind on updateNode)
        wireInnerInteractions(el, nodeData, opts);

        // Re-apply highlights from session data (needed when loading saved sessions)
        reapplyHighlights(el, nodeData.id);

        // Watch for size changes (content reflow, images loading, etc.) to redraw edges
        if (typeof ResizeObserver !== 'undefined') {
            const ro = new ResizeObserver(throttledEdgeRedraw);
            ro.observe(el);
        }

        return el;
    }

    /** Wire interactions on inner elements (call after every innerHTML update). */
    function wireInnerInteractions(el, nodeData, opts = {}) {
        setupExpandCollapse(el, nodeData);
        setupToggleButtons(el, nodeData);

        if (opts.editable) {
            setupEditablePrompt(el, nodeData);
        }

        const retryBtn = el.querySelector('.btn-retry');
        if (retryBtn) {
            retryBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (typeof App !== 'undefined') App.retryNode(nodeData.id);
            });
        }

        // Wire scroll listeners for edge tracking
        el.querySelectorAll('.node-section-scroll').forEach(scrollEl => {
            scrollEl.addEventListener('scroll', throttledEdgeRedraw);
        });
    }

    function buildNodeHTML(nodeData, opts = {}) {
        const modeBadges = {
            initial: 'Initial',
            explain: 'Explain',
            deeper: 'Deep Dive',
            question: 'Question',
        };
        let badge = modeBadges[nodeData.prompt_mode] || nodeData.prompt_mode;
        if (nodeData.prompt_mode === 'question' && nodeData.user_question) {
            const short = nodeData.user_question.length > 60
                ? nodeData.user_question.slice(0, 57) + '...'
                : nodeData.user_question;
            badge += `<span class="badge-question-text"> — ${escapeHTML(short)}</span>`;
        }

        // Collapsed state: default to collapsed (true) if not set
        const promptCollapsed = nodeData.prompt_collapsed !== false;
        const responseCollapsed = nodeData.response_collapsed !== false;

        // Toggle button icons
        const promptIcon = promptCollapsed ? '&#9656;' : '&#9662;';  // ▸ / ▾
        const responseIcon = responseCollapsed ? '&#9656;' : '&#9662;';

        // Determine which toggle buttons to show
        const showPromptToggle = !opts.editable && (nodeData.engineered_prompt || nodeData.prompt_text);
        const showResponseToggle = nodeData.status === 'complete';

        let promptSection;
        if (opts.editable) {
            promptSection = `
                <div class="node-prompt">
                    <textarea class="node-prompt-edit" placeholder="Type your question here..."
                              rows="2">${escapeHTML(nodeData.prompt_text || '')}</textarea>
                    <div class="node-prompt-submit-row">
                        <button class="btn btn-primary btn-sm btn-submit-question">Send</button>
                    </div>
                </div>`;
        } else {
            // Show engineered prompt (full context) if available, otherwise prompt_text
            const displayPrompt = nodeData.engineered_prompt || nodeData.prompt_text;
            if (promptCollapsed) {
                promptSection = `
                    <div class="node-prompt collapsed" title="Click to expand/collapse">
                        <div class="node-section-scroll">
                            <div class="node-prompt-text">${escapeHTML(displayPrompt)}</div>
                        </div>
                        <div class="section-fade"></div>
                    </div>`;
            } else {
                promptSection = `
                    <div class="node-prompt" title="Click to expand/collapse">
                        <div class="node-prompt-text">${escapeHTML(displayPrompt)}</div>
                    </div>`;
            }
        }

        let responseSection;
        if (nodeData.status === 'pending' || nodeData.status === 'queued') {
            responseSection = `
                <div class="node-queued">Queued, waiting for AI...</div>`;
        } else if (nodeData.status === 'running') {
            responseSection = `
                <div class="node-thinking">
                    Thinking
                    <div class="thinking-dots"><span></span><span></span><span></span></div>
                </div>`;
        } else if (nodeData.status === 'error') {
            responseSection = `
                <div class="node-error">${escapeHTML(nodeData.response_text || 'An error occurred')}</div>`;
        } else if (nodeData.status === 'complete') {
            const content = renderResponse(nodeData.response_html, nodeData.response_text);
            if (responseCollapsed) {
                responseSection = `
                    <div class="node-response collapsed" title="Click to expand/collapse">
                        <div class="node-section-scroll">
                            <div class="node-response-content">${content}</div>
                        </div>
                        <div class="section-fade"></div>
                    </div>`;
            } else {
                responseSection = `
                    <div class="node-response" title="Click to expand/collapse">
                        <div class="node-response-content">${content}</div>
                    </div>`;
            }
        } else {
            // "waiting" for user input (ask a question editable)
            responseSection = '';
        }

        return `
            <div class="node-header">
                <span class="node-mode-badge">${badge}</span>
                <div class="node-actions">
                    ${showPromptToggle ? `<button class="btn btn-sm btn-toggle-section" data-section="prompt" title="Toggle prompt">${promptIcon}</button>` : ''}
                    ${showResponseToggle ? `<button class="btn btn-sm btn-toggle-section" data-section="response" title="Toggle answer">${responseIcon}</button>` : ''}
                    ${nodeData.status === 'complete' || nodeData.status === 'error' ? '<button class="btn btn-sm btn-retry" title="Retry">↻</button>' : ''}
                </div>
            </div>
            ${promptSection}
            ${responseSection}
            <div class="resize-handle resize-e" data-resize="e"></div>
            <div class="resize-handle resize-w" data-resize="w"></div>
            <div class="resize-handle resize-s" data-resize="s"></div>
            <div class="resize-handle resize-se" data-resize="se"></div>
            <div class="resize-handle resize-sw" data-resize="sw"></div>
        `;
    }

    /**
     * Protect LaTeX math from markdown parsing by replacing with placeholders,
     * then restoring after marked.parse().
     */
    function parseMdWithMath(text) {
        const placeholders = [];
        let idx = 0;

        function stash(match) {
            const ph = `%%MATH_${idx}%%`;
            placeholders.push({ ph, val: match });
            idx++;
            return ph;
        }

        // Protect display math: $$ ... $$
        let safe = text.replace(/\$\$[\s\S]*?\$\$/g, stash);
        // Protect display math: \[ ... \]
        safe = safe.replace(/\\\[[\s\S]*?\\\]/g, stash);
        // Protect inline math: \( ... \)
        safe = safe.replace(/\\\([\s\S]*?\\\)/g, stash);
        // Protect inline math: $ ... $ (single, not empty, not currency like $10)
        safe = safe.replace(/\$(?!\d)([^\$\n]+?)\$/g, (m) => stash(m));

        let html = marked.parse(normalizeMarkdown(safe));

        // Restore placeholders
        for (const { ph, val } of placeholders) {
            html = html.replace(ph, val);
        }

        return html;
    }

    /** Render response: use markdown via marked.js when text is available, fall back to HTML. */
    function renderResponse(html, text) {
        // Prefer markdown rendering from raw text (clean, structured output)
        if (text && typeof marked !== 'undefined') {
            return parseMdWithMath(text);
        }
        if (html) {
            return html;
        }
        return escapeHTML(text || '');
    }

    /**
     * Normalize raw AI text into clean markdown before passing to marked.js.
     * Handles numbered section headers, dash-style bullets, and spacing.
     */
    function normalizeMarkdown(text) {
        const lines = text.split('\n');
        const out = [];

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];

            // Normalize em-dash / en-dash bullets to standard markdown bullets
            line = line.replace(/^(\s*)[\u2013\u2014]\s+/, '$1- ');

            // Detect numbered section headers: "1. Title text", "7. How to talk..."
            const headerMatch = line.match(/^(\d+)\.\s+(.+)$/);
            if (headerMatch && line.length < 120) {
                if (out.length > 0 && out[out.length - 1].trim() !== '') {
                    out.push('');
                }
                out.push(`## ${headerMatch[0]}`);
                continue;
            }

            // Detect sub-headers: short title-like lines that aren't sentences.
            // Works with or without a preceding blank line.
            // e.g., "Velocity", "Portal (Control Plane)", "Core software stack", "Key advantages"
            const trimmed = line.trim();
            const wordCount = trimmed.split(/\s+/).length;
            if (trimmed && trimmed.length > 1 && trimmed.length < 60 &&
                wordCount <= 8 &&                         // Headers are short phrases
                !trimmed.startsWith('-') && !trimmed.startsWith('*') &&
                !trimmed.startsWith('#') && !trimmed.startsWith('>') &&
                !trimmed.startsWith('|') &&               // Not a table row
                !trimmed.match(/^[\d]/) &&
                !trimmed.match(/[.!?:,;|]$/) &&          // Not a sentence, intro line, or table row
                !trimmed.includes(': ') &&                // Not a "Key: value" content line
                !trimmed.includes(', ') &&                // Not a list of items
                !trimmed.includes(' | ') &&               // Not a table row
                i + 1 < lines.length) {

                const nextLine = lines[i + 1].trim();
                const prevOut = out.length > 0 ? out[out.length - 1].trim() : '';

                // Must be followed by content (longer line, bullet, or blank then content)
                const nextIsContent = nextLine.length > trimmed.length ||
                    nextLine.match(/^[\u2013\u2014\-*]/) ||
                    nextLine === '';
                // Must be preceded by blank line, start of text, or end of previous section (sentence)
                const prevIsBreak = prevOut === '' || out.length === 0 ||
                    prevOut.match(/[.!?:]$/) || prevOut.startsWith('#');

                if (nextIsContent && prevIsBreak) {
                    if (out.length > 0 && prevOut !== '') {
                        out.push('');
                    }
                    out.push(`### ${trimmed}`);
                    // Ensure blank line after header for markdown parsing
                    if (lines[i + 1] && lines[i + 1].trim() !== '') {
                        out.push('');
                    }
                    continue;
                }
            }

            out.push(line);
        }

        return out.join('\n');
    }

    /** Update a node's status and content. */
    function updateNode(nodeId, updates) {
        const el = document.getElementById(nodeId);
        if (!el) return;

        const session = Session.getCurrent();
        if (!session || !session.nodes[nodeId]) return;

        // Merge updates into session data
        Object.assign(session.nodes[nodeId], updates);
        const nodeData = session.nodes[nodeId];

        // Force prompt collapsed when a node starts running (e.g. question submitted)
        if (updates.status === 'running' && nodeData.prompt_mode !== 'initial') {
            nodeData.prompt_collapsed = true;
        }

        // Preserve custom width before innerHTML replacement
        const savedWidth = el.style.width;
        const savedHeight = el.style.height;

        // Re-render inner HTML (drag + resize handlers are on el itself, so they survive)
        el.innerHTML = buildNodeHTML(nodeData);
        renderMath(el);

        // Restore custom dimensions
        if (savedWidth) el.style.width = savedWidth;
        if (savedHeight) {
            el.style.height = savedHeight;
            el.style.overflow = 'hidden';
        }

        // Re-wire inner interactions
        wireInnerInteractions(el, nodeData);

        // Re-apply highlights that were lost during innerHTML rebuild
        reapplyHighlights(el, nodeData.id);

        // Redraw edges after layout settles (content change may shift mark positions)
        requestAnimationFrame(() => EdgeRenderer.redrawAll());
    }

    /**
     * Setup node dragging via mousedown on the header.
     * Attached via event delegation on the outer el so it survives innerHTML updates.
     */
    function setupDrag(el, nodeData) {
        let startX, startY, startLeft, startTop, dragging = false, moved = false;

        // Use event delegation: listen on el, but only start drag if target is in .node-header
        el.addEventListener('mousedown', (e) => {
            // Only drag from the header bar (not from toggle buttons or resize handles)
            const header = e.target.closest('.node-header');
            if (!header || !el.contains(header)) return;
            if (e.target.closest('.btn')) return;  // Don't drag from buttons
            if (e.target.closest('.resize-handle')) return;
            if (e.button !== 0) return;
            e.stopPropagation();
            e.preventDefault();

            startX = e.clientX;
            startY = e.clientY;
            startLeft = parseFloat(el.style.left);
            startTop = parseFloat(el.style.top);
            dragging = true;
            moved = false;
        });

        const onMove = (e) => {
            if (!dragging) return;
            const dx = (e.clientX - startX) / Canvas.getZoom();
            const dy = (e.clientY - startY) / Canvas.getZoom();
            if (!moved && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
                moved = true;
                el.classList.add('dragging');
            }
            if (moved) {
                el.style.left = (startLeft + dx) + 'px';
                el.style.top = (startTop + dy) + 'px';
                EdgeRenderer.redrawAll();
            }
        };

        const onUp = () => {
            if (!dragging) return;
            dragging = false;
            el.classList.remove('dragging');
            if (moved) {
                nodeData.x = parseFloat(el.style.left);
                nodeData.y = parseFloat(el.style.top);
                const session = Session.getCurrent();
                if (session && session.nodes[nodeData.id]) {
                    session.nodes[nodeData.id].x = nodeData.x;
                    session.nodes[nodeData.id].y = nodeData.y;
                }
                Session.scheduleSave();
                EdgeRenderer.redrawAll();
            }
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    }

    /**
     * Setup node resizing via edge/corner handles.
     * Attached via event delegation on the outer el so it survives innerHTML updates.
     */
    function setupResize(el, nodeData) {
        let resizing = false, resizeDir = '';
        let startX, startY, startW, startH, startLeft;

        el.addEventListener('mousedown', (e) => {
            const handle = e.target.closest('.resize-handle');
            if (!handle) return;

            e.stopPropagation();
            e.preventDefault();

            resizing = true;
            resizeDir = handle.dataset.resize;
            startX = e.clientX;
            startY = e.clientY;
            startW = el.offsetWidth;
            startH = el.offsetHeight;
            startLeft = parseFloat(el.style.left) || 0;
            el.classList.add('resizing');
        });

        const onMove = (e) => {
            if (!resizing) return;
            const zoom = Canvas.getZoom();
            const dx = (e.clientX - startX) / zoom;
            const dy = (e.clientY - startY) / zoom;

            // Width from right edge
            if (resizeDir === 'e' || resizeDir === 'se') {
                el.style.width = Math.max(MIN_WIDTH, startW + dx) + 'px';
            }
            // Width from left edge (also shifts position)
            if (resizeDir === 'w' || resizeDir === 'sw') {
                const newW = Math.max(MIN_WIDTH, startW - dx);
                el.style.width = newW + 'px';
                el.style.left = (startLeft + (startW - newW)) + 'px';
            }
            // Height from bottom
            if (resizeDir === 's' || resizeDir === 'se' || resizeDir === 'sw') {
                el.style.height = Math.max(MIN_HEIGHT, startH + dy) + 'px';
                el.style.overflow = 'hidden';
                el.classList.add('has-custom-height');
            }

            EdgeRenderer.redrawAll();
        };

        const onUp = () => {
            if (!resizing) return;
            resizing = false;
            el.classList.remove('resizing');

            // Save dimensions to nodeData
            nodeData.width = el.offsetWidth;
            nodeData.x = parseFloat(el.style.left) || 0;
            if (el.style.height) {
                nodeData.height = el.offsetHeight;
            }

            const session = Session.getCurrent();
            if (session && session.nodes[nodeData.id]) {
                session.nodes[nodeData.id].width = nodeData.width;
                session.nodes[nodeData.id].x = nodeData.x;
                if (nodeData.height) {
                    session.nodes[nodeData.id].height = nodeData.height;
                }
            }

            Session.scheduleSave();
            EdgeRenderer.redrawAll();
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    }

    /** Wire toggle buttons in the header for prompt/response sections. */
    function setupToggleButtons(el, nodeData) {
        el.querySelectorAll('.btn-toggle-section').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const section = btn.dataset.section;

                if (section === 'prompt') {
                    const isCollapsed = !(nodeData.prompt_collapsed !== false);
                    updateNodeCollapsedState(nodeData.id, 'prompt', isCollapsed);
                } else if (section === 'response') {
                    const isCollapsed = !(nodeData.response_collapsed !== false);
                    updateNodeCollapsedState(nodeData.id, 'response', isCollapsed);

                    // When expanding response, clear custom height so node auto-sizes
                    if (!isCollapsed && el.style.height) {
                        clearCustomHeight(el, nodeData);
                    }
                }

                // Rebuild HTML so structure matches collapsed state (scroll wrappers, fade overlays)
                rebuildInnerHTML(el, nodeData);
                Session.scheduleSave();
            });
        });
    }

    /** Update collapsed state in session data. */
    function updateNodeCollapsedState(nodeId, section, isCollapsed) {
        const session = Session.getCurrent();
        if (session && session.nodes[nodeId]) {
            if (section === 'prompt') {
                session.nodes[nodeId].prompt_collapsed = isCollapsed;
            } else {
                session.nodes[nodeId].response_collapsed = isCollapsed;
            }
        }
    }

    /** Clear custom height from a node (used when expanding). */
    function clearCustomHeight(el, nodeData) {
        el.style.height = '';
        el.style.overflow = '';
        el.classList.remove('has-custom-height');
        nodeData.height = null;
        const session = Session.getCurrent();
        if (session && session.nodes[nodeData.id]) {
            session.nodes[nodeData.id].height = null;
        }
    }

    /** Rebuild inner HTML to match current collapsed state, preserving dimensions. */
    function rebuildInnerHTML(el, nodeData, opts = {}) {
        // Sync nodeData from session (in case collapsed state was updated on session object)
        const session = Session.getCurrent();
        if (session && session.nodes[nodeData.id]) {
            Object.assign(nodeData, session.nodes[nodeData.id]);
        }

        const savedWidth = el.style.width;
        const savedHeight = el.style.height;

        el.innerHTML = buildNodeHTML(nodeData, opts);
        renderMath(el);

        if (savedWidth) el.style.width = savedWidth;
        if (savedHeight) {
            el.style.height = savedHeight;
            el.style.overflow = 'hidden';
        }

        wireInnerInteractions(el, nodeData, opts);
        reapplyHighlights(el, nodeData.id);
        requestAnimationFrame(() => EdgeRenderer.redrawAll());
    }

    /** Setup click-to-expand/collapse on prompt and response sections. */
    function setupExpandCollapse(el, nodeData) {
        const prompt = el.querySelector('.node-prompt:not(:has(.node-prompt-edit))');
        if (prompt) {
            prompt.addEventListener('click', (e) => {
                if (window.getSelection().toString().length > 0) return;
                const isCollapsed = !(nodeData.prompt_collapsed !== false);
                updateNodeCollapsedState(nodeData.id, 'prompt', isCollapsed);
                rebuildInnerHTML(el, nodeData);
                Session.scheduleSave();
            });
        }

        const response = el.querySelector('.node-response');
        if (response) {
            response.addEventListener('click', (e) => {
                if (window.getSelection().toString().length > 0) return;
                if (response.classList.contains('collapsed')) {
                    const rect = response.getBoundingClientRect();
                    const clickY = e.clientY - rect.top;
                    if (clickY > rect.height - 50) {
                        updateNodeCollapsedState(nodeData.id, 'response', false);
                        // Clear custom height when expanding
                        if (el.style.height) {
                            clearCustomHeight(el, nodeData);
                        }
                        rebuildInnerHTML(el, nodeData);
                        Session.scheduleSave();
                    }
                }
            });
        }
    }

    /** Update a toggle button icon to match collapsed state. */
    function updateToggleButtonIcon(el, section, isCollapsed) {
        const btn = el.querySelector(`.btn-toggle-section[data-section="${section}"]`);
        if (btn) btn.innerHTML = isCollapsed ? '&#9656;' : '&#9662;';
    }

    /** Setup editable prompt for "ask a question" mode. */
    function setupEditablePrompt(el, nodeData) {
        const textarea = el.querySelector('.node-prompt-edit');
        const submitBtn = el.querySelector('.btn-submit-question');
        if (!textarea || !submitBtn) return;

        setTimeout(() => textarea.focus(), 100);

        const submit = () => {
            const question = textarea.value.trim();
            if (!question) return;
            if (typeof App !== 'undefined') {
                App.submitQuestion(nodeData.id, question);
            }
        };

        submitBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            submit();
        });

        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
            }
        });
    }

    /**
     * Re-apply highlights from session.highlights after an HTML rebuild.
     * Finds the highlight text in the rendered response and wraps it in <mark>.
     */
    function reapplyHighlights(el, nodeId) {
        const session = Session.getCurrent();
        if (!session || !session.highlights) return;

        const responseContent = el.querySelector('.node-response-content');
        if (!responseContent) return;

        for (const [hlId, hl] of Object.entries(session.highlights)) {
            if (hl.node_id !== nodeId) continue;
            // Skip if this mark already exists in the DOM
            if (responseContent.querySelector(`mark[data-highlight-id="${CSS.escape(hlId)}"]`)) continue;
            findAndWrapText(responseContent, hl.text, hlId);
        }
    }

    /**
     * Find searchText within container's text nodes and wrap it in a <mark>.
     * Handles both single-node and cross-node matches.
     */
    function findAndWrapText(container, searchText, highlightId) {
        // Build a map of all text nodes and their positions in the concatenated text
        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        let fullText = '';

        while (walker.nextNode()) {
            textNodes.push({ node: walker.currentNode, start: fullText.length });
            fullText += walker.currentNode.textContent;
        }

        // Try exact match first, then normalize whitespace for cross-element matches
        let matchIndex = fullText.indexOf(searchText);
        let matchEnd;
        if (matchIndex !== -1) {
            matchEnd = matchIndex + searchText.length;
        } else {
            // Normalize whitespace: collapse runs of whitespace in both strings
            // This handles cross-element selections where DOM whitespace differs
            // from window.getSelection().toString() whitespace
            const normSearch = searchText.replace(/\s+/g, ' ').trim();
            // Build a mapping from normalized positions back to original positions
            const normMap = [];  // normMap[normIdx] = originalIdx
            let normText = '';
            let inSpace = false;
            // skip leading whitespace
            let started = false;
            for (let i = 0; i < fullText.length; i++) {
                const ch = fullText[i];
                if (/\s/.test(ch)) {
                    if (started && !inSpace) {
                        normMap.push(i);
                        normText += ' ';
                        inSpace = true;
                    }
                } else {
                    started = true;
                    inSpace = false;
                    normMap.push(i);
                    normText += ch;
                }
            }

            const normMatchIdx = normText.indexOf(normSearch);
            if (normMatchIdx === -1) return false;

            matchIndex = normMap[normMatchIdx];
            matchEnd = normMap[normMatchIdx + normSearch.length - 1] + 1;
        }

        // Find which text nodes the match spans
        const nodesToWrap = [];
        for (const entry of textNodes) {
            const nodeStart = entry.start;
            const nodeEnd = nodeStart + entry.node.textContent.length;
            if (nodeEnd <= matchIndex || nodeStart >= matchEnd) continue;
            nodesToWrap.push({
                node: entry.node,
                localStart: Math.max(0, matchIndex - nodeStart),
                localEnd: Math.min(entry.node.textContent.length, matchEnd - nodeStart),
            });
        }

        if (nodesToWrap.length === 0) return false;

        // Simple case: match is entirely within one text node
        if (nodesToWrap.length === 1) {
            const { node, localStart, localEnd } = nodesToWrap[0];
            const range = document.createRange();
            range.setStart(node, localStart);
            range.setEnd(node, localEnd);
            const mark = document.createElement('mark');
            mark.className = 'lt-highlight';
            mark.dataset.highlightId = highlightId;
            range.surroundContents(mark);
            return true;
        }

        // Multi-node case: process in reverse to avoid invalidating earlier references
        for (let i = nodesToWrap.length - 1; i >= 0; i--) {
            const { node, localStart, localEnd } = nodesToWrap[i];
            const mark = document.createElement('mark');
            mark.className = 'lt-highlight';
            mark.dataset.highlightId = highlightId;

            if (localStart === 0 && localEnd === node.textContent.length) {
                // Full text node
                node.parentNode.insertBefore(mark, node);
                mark.appendChild(node);
            } else if (localStart === 0) {
                // Start portion of text node
                node.splitText(localEnd);
                node.parentNode.insertBefore(mark, node.nextSibling);
                mark.appendChild(node);
            } else {
                // Middle or end portion of text node
                const matchNode = node.splitText(localStart);
                if (localEnd - localStart < matchNode.textContent.length) {
                    matchNode.splitText(localEnd - localStart);
                }
                matchNode.parentNode.insertBefore(mark, matchNode);
                mark.appendChild(matchNode);
            }
        }

        return true;
    }

    /** Begin streaming content into a node. Replaces thinking indicator with response area. */
    function streamToken(nodeId, text) {
        const el = document.getElementById(nodeId);
        if (!el) return;

        // Initialize streaming state on first token
        if (el._streamBuffer == null) {
            el._streamBuffer = '';
            // Replace thinking/queued indicator with streaming response container
            const thinking = el.querySelector('.node-thinking');
            const queued = el.querySelector('.node-queued');
            const target = thinking || queued;
            if (target) {
                target.outerHTML =
                    '<div class="node-response collapsed streaming">' +
                    '<div class="node-section-scroll">' +
                    '<div class="node-response-content"></div>' +
                    '</div>' +
                    '<div class="section-fade"></div>' +
                    '</div>';
            }
        }

        el._streamBuffer += text;

        // Debounced markdown render (every 150ms)
        if (!el._streamRenderTimer) {
            el._streamRenderTimer = setTimeout(() => {
                el._streamRenderTimer = null;
                const content = el.querySelector('.node-response-content');
                if (content && el._streamBuffer) {
                    content.innerHTML = parseMdWithMath(el._streamBuffer);
                    renderMath(content);
                }
                EdgeRenderer.redrawAll();
            }, 150);
        }
    }

    /** Finalize streaming — do final render and switch to complete status. */
    function finishStreaming(nodeId, fullText) {
        const el = document.getElementById(nodeId);
        if (!el) return;

        // Clear streaming state
        clearTimeout(el._streamRenderTimer);
        delete el._streamBuffer;
        delete el._streamRenderTimer;

        // Remove streaming class
        const streamingEl = el.querySelector('.node-response.streaming');
        if (streamingEl) streamingEl.classList.remove('streaming');

        // Update via standard path for final render with full features
        // Ensure both sections default to collapsed for new nodes
        const session = Session.getCurrent();
        const nd = session && session.nodes[nodeId];
        const updates = {
            status: 'complete',
            response_text: fullText,
            response_html: '',
        };
        updates.response_collapsed = true;
        updates.prompt_collapsed = true;
        updateNode(nodeId, updates);
    }

    /** Remove a node from DOM. */
    function removeNode(nodeId) {
        const el = document.getElementById(nodeId);
        if (el) el.remove();
    }

    /** Clear all nodes from canvas. */
    function clearAll() {
        const world = Canvas.getWorld();
        world.querySelectorAll('.lt-node').forEach(el => el.remove());
    }

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { createNode, updateNode, removeNode, clearAll, renderResponse, streamToken, finishStreaming };
})();
