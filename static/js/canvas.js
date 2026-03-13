/**
 * canvas.js — Infinite canvas with pan and zoom.
 * Uses CSS transform on #canvas-world inside #canvas-viewport.
 */

const Canvas = (() => {
    let viewport, world;
    let panX = 0, panY = 0, zoom = 1.0;
    let isPanning = false;
    let panStartX = 0, panStartY = 0;
    let panStartPanX = 0, panStartPanY = 0;

    const MIN_ZOOM = 0.15;
    const MAX_ZOOM = 3.0;
    const ZOOM_STEP = 0.04;

    function init() {
        viewport = document.getElementById('canvas-viewport');
        world = document.getElementById('canvas-world');

        viewport.addEventListener('mousedown', onMouseDown);
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        viewport.addEventListener('wheel', onWheel, { passive: false });

        // Zoom buttons
        document.getElementById('btn-zoom-in').addEventListener('click', () => zoomAtCenter(ZOOM_STEP));
        document.getElementById('btn-zoom-out').addEventListener('click', () => zoomAtCenter(-ZOOM_STEP));
        document.getElementById('btn-zoom-reset').addEventListener('click', resetView);

        applyTransform();
    }

    function onMouseDown(e) {
        // Only pan on left-click directly on viewport or canvas world (not on nodes)
        if (e.button !== 0) return;
        if (e.target !== viewport && e.target !== world && e.target.tagName === 'svg' ? false : !e.target.closest('#canvas-viewport') || e.target.closest('.lt-node') || e.target.closest('.context-menu')) return;
        // Start pan only if clicking on empty canvas space
        if (e.target !== viewport && e.target !== world && !e.target.closest('.edge-layer')) return;

        isPanning = true;
        panStartX = e.clientX;
        panStartY = e.clientY;
        panStartPanX = panX;
        panStartPanY = panY;
        viewport.classList.add('panning');
        e.preventDefault();
    }

    function onMouseMove(e) {
        if (!isPanning) return;
        panX = panStartPanX + (e.clientX - panStartX);
        panY = panStartPanY + (e.clientY - panStartY);
        applyTransform();
    }

    function onMouseUp(e) {
        if (!isPanning) return;
        isPanning = false;
        viewport.classList.remove('panning');
        // Save viewport state after panning
        Session.scheduleSave();
    }

    let zoomCursorTimer = null;

    function onWheel(e) {
        // If cursor is over a node, check if there's actually scrollable content
        const nodeEl = e.target.closest('.lt-node');
        if (nodeEl) {
            // Find the nearest scroll container that can actually scroll
            const scrollEl = findScrollableAncestor(e.target, nodeEl, e.deltaY);
            if (scrollEl) {
                return;  // Let browser handle native scroll inside the node
            }

            // Check if any section under cursor is collapsed (has scroll wrapper)
            // If so, absorb the wheel event — never pan/zoom when over a collapsed node
            const sectionScroll = e.target.closest('.node-section-scroll');
            if (sectionScroll) {
                e.preventDefault();
                return;  // Absorb — don't pan canvas when over a collapsed node at scroll bounds
            }

            // Node is expanded with no scrollable content — fall through to canvas pan
        }

        e.preventDefault();

        if (nodeEl) {
            // Over an expanded node with no scrollable content — pan the canvas
            // deltaY positive = wheel down = content should move up = panY decreases
            panY += -e.deltaY;
            panX += -e.deltaX;
            applyTransform();
            EdgeRenderer.redrawAll();
            Session.scheduleSave();
            return;
        }

        // Zoom on empty canvas with cursor feedback
        const delta = -Math.sign(e.deltaY) * ZOOM_STEP;
        viewport.classList.remove('zooming', 'zooming-out');
        viewport.classList.add(delta > 0 ? 'zooming' : 'zooming-out');

        clearTimeout(zoomCursorTimer);
        zoomCursorTimer = setTimeout(() => {
            viewport.classList.remove('zooming', 'zooming-out');
        }, 150);

        zoomAtPoint(delta, e.clientX, e.clientY);
        Session.scheduleSave();
    }

    /**
     * Walk from target up to nodeEl looking for an ancestor that can scroll
     * in the direction the user is wheeling. Returns the element or null.
     */
    function findScrollableAncestor(target, boundary, deltaY) {
        let el = target;
        while (el && el !== boundary.parentNode) {
            const style = window.getComputedStyle(el);
            const overflowY = style.overflowY;
            // Only consider elements with actual scroll overflow (auto or scroll),
            // not 'visible' or 'hidden'
            if ((overflowY === 'auto' || overflowY === 'scroll') &&
                el.scrollHeight > el.clientHeight + 1) {
                const canScrollDown = deltaY > 0 && el.scrollTop < el.scrollHeight - el.clientHeight - 1;
                const canScrollUp = deltaY < 0 && el.scrollTop > 1;
                if (canScrollDown || canScrollUp) {
                    return el;
                }
            }
            el = el.parentElement;
        }
        return null;
    }

    function zoomAtPoint(delta, clientX, clientY) {
        const oldZoom = zoom;
        zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom + delta));
        const scale = zoom / oldZoom;

        // Get cursor position relative to viewport
        const rect = viewport.getBoundingClientRect();
        const cx = clientX - rect.left;
        const cy = clientY - rect.top;

        // Adjust pan so zoom targets cursor position
        panX = cx - scale * (cx - panX);
        panY = cy - scale * (cy - panY);

        applyTransform();
    }

    function zoomAtCenter(delta) {
        const rect = viewport.getBoundingClientRect();
        zoomAtPoint(delta, rect.left + rect.width / 2, rect.top + rect.height / 2);
    }

    function resetView() {
        panX = 0;
        panY = 0;
        zoom = 1.0;
        applyTransform();
    }

    function applyTransform() {
        world.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
    }

    /** Convert screen (client) coords to world coords. */
    function screenToWorld(clientX, clientY) {
        const rect = viewport.getBoundingClientRect();
        return {
            x: (clientX - rect.left - panX) / zoom,
            y: (clientY - rect.top - panY) / zoom,
        };
    }

    /** Convert world coords to screen (client) coords. */
    function worldToScreen(wx, wy) {
        const rect = viewport.getBoundingClientRect();
        return {
            x: wx * zoom + panX + rect.left,
            y: wy * zoom + panY + rect.top,
        };
    }

    function getState() {
        return { panX, panY, zoom };
    }

    function setState(state) {
        panX = state.panX || 0;
        panY = state.panY || 0;
        zoom = state.zoom || 1.0;
        applyTransform();
    }

    function getWorld() { return world; }
    function getViewport() { return viewport; }
    function getZoom() { return zoom; }

    return { init, screenToWorld, worldToScreen, getState, setState, getWorld, getViewport, getZoom, resetView };
})();
