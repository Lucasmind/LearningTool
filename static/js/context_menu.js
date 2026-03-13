/**
 * context_menu.js — Right-click context menu for text selection in response nodes.
 * Handles highlight creation and spawning follow-up queries.
 */

const ContextMenu = (() => {
    let menuEl;
    let currentSelection = null;  // { text, range, nodeId }

    function init() {
        menuEl = document.getElementById('context-menu');

        // Listen for mouseup on response content to detect text selection
        document.addEventListener('mouseup', onMouseUp);

        // Hide menu on click elsewhere
        document.addEventListener('mousedown', (e) => {
            if (!menuEl.contains(e.target)) {
                hide();
            }
        });

        // Wire menu buttons
        menuEl.querySelectorAll('.ctx-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = btn.dataset.action;
                handleAction(action);
            });
        });

        // Suppress default context menu inside response areas
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.node-response-content') && currentSelection) {
                e.preventDefault();
                showAt(e.clientX, e.clientY);
            }
        });
    }

    function onMouseUp(e) {
        // Small delay to let selection finalize
        setTimeout(() => {
            const sel = window.getSelection();
            if (!sel || sel.isCollapsed || !sel.toString().trim()) {
                currentSelection = null;
                return;
            }

            // Check if selection is inside a node-response-content
            const range = sel.getRangeAt(0);
            const container = range.commonAncestorContainer.nodeType === 3
                ? range.commonAncestorContainer.parentElement
                : range.commonAncestorContainer;
            const responseContent = container.closest('.node-response-content');
            if (!responseContent) {
                currentSelection = null;
                return;
            }

            const nodeEl = responseContent.closest('.lt-node');
            if (!nodeEl) {
                currentSelection = null;
                return;
            }

            currentSelection = {
                text: sel.toString().trim(),
                range: range.cloneRange(),
                nodeId: nodeEl.id,
            };
        }, 10);
    }

    function showAt(x, y) {
        if (!currentSelection) return;
        menuEl.classList.remove('hidden');
        // Position near click, keep on screen
        const mw = menuEl.offsetWidth;
        const mh = menuEl.offsetHeight;
        const nx = Math.min(x, window.innerWidth - mw - 10);
        const ny = Math.min(y, window.innerHeight - mh - 10);
        menuEl.style.left = nx + 'px';
        menuEl.style.top = ny + 'px';
    }

    function hide() {
        menuEl.classList.add('hidden');
    }

    function handleAction(action) {
        if (!currentSelection) return;
        hide();

        const { text, range, nodeId } = currentSelection;

        // Create persistent highlight
        const highlightId = 'hl_' + Date.now().toString(36);
        createHighlight(range, highlightId);

        // Clear browser selection
        window.getSelection().removeAllRanges();

        // Dispatch to App
        if (typeof App !== 'undefined') {
            App.spawnChild(nodeId, highlightId, text, action);
        }

        currentSelection = null;
    }

    /**
     * Wrap the selected range in <mark> elements.
     * Handles cross-element selections using TreeWalker.
     */
    function createHighlight(range, highlightId) {
        try {
            // Simple case: selection within a single text node
            if (range.startContainer === range.endContainer && range.startContainer.nodeType === 3) {
                const mark = document.createElement('mark');
                mark.className = 'lt-highlight';
                mark.dataset.highlightId = highlightId;
                range.surroundContents(mark);
                return;
            }

            // Complex case: spans multiple nodes
            const marks = [];
            const treeWalker = document.createTreeWalker(
                range.commonAncestorContainer,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        const nodeRange = document.createRange();
                        nodeRange.selectNodeContents(node);
                        return range.compareBoundaryPoints(Range.END_TO_START, nodeRange) < 0 &&
                               range.compareBoundaryPoints(Range.START_TO_END, nodeRange) > 0
                            ? NodeFilter.FILTER_ACCEPT
                            : NodeFilter.FILTER_REJECT;
                    }
                }
            );

            const textNodes = [];
            while (treeWalker.nextNode()) {
                const node = treeWalker.currentNode;
                // Skip whitespace-only text nodes that are direct children of list/table
                // containers (newlines between <li>, <tr> elements) — wrapping these
                // in <mark> creates visible empty highlighted lines
                if (node.textContent.trim() === '') {
                    const parent = node.parentElement?.tagName;
                    if (parent === 'UL' || parent === 'OL' || parent === 'TABLE' || parent === 'TBODY') {
                        continue;
                    }
                }
                textNodes.push(node);
            }

            for (const textNode of textNodes) {
                const mark = document.createElement('mark');
                mark.className = 'lt-highlight';
                mark.dataset.highlightId = highlightId;

                if (textNode === range.startContainer) {
                    // Partial start node
                    const splitNode = textNode.splitText(range.startOffset);
                    splitNode.parentNode.insertBefore(mark, splitNode);
                    mark.appendChild(splitNode);
                } else if (textNode === range.endContainer) {
                    // Partial end node
                    const splitNode = textNode.splitText(range.endOffset);
                    textNode.parentNode.insertBefore(mark, textNode.nextSibling);
                    mark.appendChild(textNode);
                } else {
                    // Full text node
                    textNode.parentNode.insertBefore(mark, textNode);
                    mark.appendChild(textNode);
                }
                marks.push(mark);
            }
        } catch (e) {
            console.warn('Highlight creation failed:', e);
            // Fallback: try simple approach
            try {
                const mark = document.createElement('mark');
                mark.className = 'lt-highlight';
                mark.dataset.highlightId = highlightId;
                range.surroundContents(mark);
            } catch (e2) {
                console.warn('Highlight fallback also failed:', e2);
            }
        }
    }

    return { init, hide };
})();
