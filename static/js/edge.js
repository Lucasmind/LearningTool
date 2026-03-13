/**
 * edge.js — SVG Bezier edge drawing between highlights and child nodes.
 * Uses world-space coordinates directly from node positions to avoid
 * screen-to-world conversion bugs.
 */

const EdgeRenderer = (() => {
    let svgLayer;

    function init() {
        svgLayer = document.getElementById('edge-layer');
    }

    /**
     * Draw an edge from a source element to a target node.
     * Uses a hybrid approach: tries to anchor to the highlight <mark> position,
     * falls back to the right edge of the source node.
     */
    function drawEdge(edgeId, sourceEl, targetEl) {
        if (!sourceEl || !targetEl) return;

        let path = svgLayer.querySelector(`#${CSS.escape(edgeId)}`);
        if (!path) {
            path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.id = edgeId;
            path.classList.add('edge-path');
            svgLayer.appendChild(path);
        }

        let x1, y1, x2, y2;

        // Target: left edge of target node, 1/3 down
        const tgtLeft = parseFloat(targetEl.style.left) || 0;
        const tgtTop = parseFloat(targetEl.style.top) || 0;
        x2 = tgtLeft;
        y2 = tgtTop + 50;  // near top of node (header area)

        // Source: try to get highlight position within its node
        const sourceNode = sourceEl.closest('.lt-node') || sourceEl;
        const srcLeft = parseFloat(sourceNode.style.left) || 0;
        const srcTop = parseFloat(sourceNode.style.top) || 0;
        const srcWidth = sourceNode.offsetWidth || 420;

        if (sourceEl.tagName === 'MARK') {
            const responseSection = sourceEl.closest('.node-response');
            const scrollContainer = sourceEl.closest('.node-section-scroll');
            const nodeRect = sourceNode.getBoundingClientRect();
            const markRect = sourceEl.getBoundingClientRect();
            const zoom = Canvas.getZoom();

            if (scrollContainer && responseSection) {
                // Mark is inside a scrollable collapsed section — clamp to the
                // response section's visible bounds (not the scroll container,
                // which may extend beyond the clipped response area)
                const respRect = responseSection.getBoundingClientRect();
                const markCenterY = markRect.top + markRect.height / 2;

                let screenY;
                if (markRect.height === 0 || markRect.width === 0) {
                    // Mark not rendered — center of response area
                    screenY = respRect.top + respRect.height / 2;
                } else if (markCenterY < respRect.top) {
                    // Mark scrolled above visible area — clamp to top
                    screenY = respRect.top;
                } else if (markCenterY > respRect.bottom) {
                    // Mark scrolled below visible area — clamp to bottom
                    screenY = respRect.bottom;
                } else {
                    // Mark is visible — use actual position
                    screenY = markCenterY;
                }

                const offsetY = (screenY - nodeRect.top) / zoom;
                x1 = srcLeft + srcWidth;
                y1 = srcTop + offsetY;
            } else if (markRect.width > 0 && markRect.height > 0) {
                // Mark is in expanded section — use direct position
                const markOffsetY = (markRect.top + markRect.height / 2 - nodeRect.top) / zoom;
                x1 = srcLeft + srcWidth;
                y1 = srcTop + markOffsetY;
            } else {
                // Fallback — right-center of node
                x1 = srcLeft + srcWidth;
                y1 = srcTop + (sourceNode.offsetHeight || 200) / 2;
            }
        } else {
            // No mark found, use right-center of source node
            x1 = srcLeft + srcWidth;
            y1 = srcTop + (sourceNode.offsetHeight || 200) / 2;
        }

        // Cubic bezier — smooth horizontal S-curve
        const dx = Math.abs(x2 - x1);
        const cx = Math.max(dx * 0.4, 80);
        const d = `M ${x1},${y1} C ${x1 + cx},${y1} ${x2 - cx},${y2} ${x2},${y2}`;
        path.setAttribute('d', d);
    }

    /** Remove an edge. */
    function removeEdge(edgeId) {
        const path = svgLayer.querySelector(`#${CSS.escape(edgeId)}`);
        if (path) path.remove();
    }

    /** Redraw all edges. */
    function redrawAll() {
        const session = Session.getCurrent();
        if (!session) return;
        for (const edge of session.edges) {
            const sourceHighlight = document.querySelector(
                `mark[data-highlight-id="${edge.source_highlight_id}"]`
            );
            const targetNode = document.getElementById(edge.target_node_id);
            const sourceEl = sourceHighlight || document.getElementById(edge.source_node_id);
            drawEdge(edge.id, sourceEl, targetNode);
        }
    }

    /** Clear all SVG edges. */
    function clearAll() {
        svgLayer.innerHTML = '';
    }

    return { init, drawEdge, removeEdge, redrawAll, clearAll };
})();
