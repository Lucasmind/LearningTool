/**
 * session.js — Session management: sidebar list, save/load, naming, auto-save, trash.
 */

const Session = (() => {
    let currentSession = null;
    let saveTimeout = null;
    const SAVE_DEBOUNCE = 2000;  // 2 seconds

    function init() {
        document.getElementById('btn-new-session').addEventListener('click', createNew);

        // Sidebar toggle
        const sidebar = document.getElementById('sidebar');
        const mainArea = document.getElementById('main-area');
        document.getElementById('btn-toggle-sidebar').addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            mainArea.classList.toggle('sidebar-collapsed');
        });

        // Session name double-click to rename
        const nameDisplay = document.getElementById('session-name-display');
        nameDisplay.addEventListener('dblclick', () => {
            const newName = prompt('Rename session:', currentSession?.name || '');
            if (newName && newName.trim() && currentSession) {
                currentSession.name = newName.trim();
                nameDisplay.textContent = newName.trim();
                API.renameSession(currentSession.id, newName.trim()).catch(console.error);
                refreshList();
            }
        });

        // Trash toggle
        document.getElementById('btn-toggle-trash').addEventListener('click', () => {
            const trashList = document.getElementById('trash-list');
            const isHidden = trashList.classList.contains('hidden');
            if (isHidden) {
                trashList.classList.remove('hidden');
                refreshTrash();
            } else {
                trashList.classList.add('hidden');
            }
        });

        // Save on page close/reload so viewport state is never lost
        window.addEventListener('beforeunload', () => {
            if (currentSession) {
                // Synchronous: capture state into currentSession, then send via sendBeacon
                currentSession.viewport = Canvas.getState();
                currentSession.updated_at = new Date().toISOString();
                for (const [id, nodeData] of Object.entries(currentSession.nodes)) {
                    const el = document.getElementById(id);
                    if (el) {
                        nodeData.x = parseFloat(el.style.left) || 0;
                        nodeData.y = parseFloat(el.style.top) || 0;
                        const w = parseFloat(el.style.width);
                        if (w && w > 0) nodeData.width = w;
                        const h = el.style.height ? parseFloat(el.style.height) : null;
                        if (h && h > 0) nodeData.height = h;
                        else nodeData.height = null;
                    }
                }
                const url = `/api/sessions/${currentSession.id}`;
                const blob = new Blob([JSON.stringify(currentSession)], { type: 'application/json' });
                navigator.sendBeacon(url, blob);
            }
        });

        // Load session list
        refreshList();
    }

    async function refreshList() {
        try {
            const sessions = await API.listSessions();
            const listEl = document.getElementById('session-list');
            listEl.innerHTML = '';
            for (const s of sessions) {
                const item = document.createElement('div');
                item.className = 'session-item' + (currentSession?.id === s.id ? ' active' : '');
                item.innerHTML = `
                    <div class="session-item-name">${escapeHTML(s.name)}</div>
                    <div class="session-item-meta">${formatDate(s.updated_at)} · ${s.node_count} nodes</div>
                    <div class="session-item-actions">
                        <button class="btn btn-sm btn-delete" title="Delete">✕</button>
                    </div>
                `;
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.btn-delete')) return;
                    loadSession(s.id);
                });
                const delBtn = item.querySelector('.btn-delete');
                delBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm(`Delete "${s.name}"?\nIt will be moved to trash for 30 days.`)) {
                        await API.deleteSession(s.id);
                        if (currentSession?.id === s.id) {
                            currentSession = null;
                            NodeRenderer.clearAll();
                            EdgeRenderer.clearAll();
                            document.getElementById('session-name-display').textContent = '';
                        }
                        refreshList();
                        // Refresh trash if visible
                        const trashList = document.getElementById('trash-list');
                        if (!trashList.classList.contains('hidden')) {
                            refreshTrash();
                        }
                    }
                });
                listEl.appendChild(item);
            }
        } catch (err) {
            console.error('Failed to load sessions:', err);
        }
    }

    async function refreshTrash() {
        try {
            const items = await API.listTrash();
            const trashEl = document.getElementById('trash-list');
            if (items.length === 0) {
                trashEl.innerHTML = '<div class="trash-empty">Trash is empty</div>';
                return;
            }
            trashEl.innerHTML = '';
            for (const s of items) {
                const item = document.createElement('div');
                item.className = 'trash-item';
                const daysText = s.days_left > 0 ? `${s.days_left}d left` : 'expiring soon';
                item.innerHTML = `
                    <div class="trash-item-name">${escapeHTML(s.name)}</div>
                    <div class="trash-item-meta">${s.node_count} nodes · ${daysText}</div>
                    <div class="trash-item-actions">
                        <button class="btn btn-sm btn-restore" title="Restore">↩</button>
                        <button class="btn btn-sm btn-perm-delete" title="Delete permanently">✕</button>
                    </div>
                `;
                const restoreBtn = item.querySelector('.btn-restore');
                restoreBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await API.restoreSession(s.id);
                    refreshList();
                    refreshTrash();
                });
                const permDelBtn = item.querySelector('.btn-perm-delete');
                permDelBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm(`Permanently delete "${s.name}"?\nThis cannot be undone.`)) {
                        await API.permanentDeleteSession(s.id);
                        refreshTrash();
                    }
                });
                trashEl.appendChild(item);
            }
        } catch (err) {
            console.error('Failed to load trash:', err);
        }
    }

    async function createNew() {
        try {
            const summary = await API.createSession('Untitled Session');
            currentSession = {
                id: summary.id,
                name: summary.name,
                created_at: summary.created_at,
                updated_at: summary.updated_at,
                viewport: { panX: 0, panY: 0, zoom: 1.0 },
                nodes: {},
                edges: [],
                highlights: {},
            };
            document.getElementById('session-name-display').textContent = currentSession.name;
            NodeRenderer.clearAll();
            EdgeRenderer.clearAll();
            Canvas.resetView();
            refreshList();

            // Focus prompt input
            document.getElementById('prompt-input').focus();
        } catch (err) {
            console.error('Failed to create session:', err);
        }
    }

    async function loadSession(sessionId) {
        try {
            // Flush any pending save for the current session before switching
            await flushSave();

            const data = await API.loadSession(sessionId);
            currentSession = data;
            document.getElementById('session-name-display').textContent = data.name;

            // Clear canvas
            NodeRenderer.clearAll();
            EdgeRenderer.clearAll();

            // Restore viewport
            if (data.viewport) {
                Canvas.setState(data.viewport);
            }

            // Recreate nodes
            for (const [id, nodeData] of Object.entries(data.nodes)) {
                NodeRenderer.createNode(nodeData);
            }

            // Redraw edges after DOM settles (multiple passes for layout reflow)
            requestAnimationFrame(() => {
                EdgeRenderer.redrawAll();
                setTimeout(() => EdgeRenderer.redrawAll(), 100);
                setTimeout(() => EdgeRenderer.redrawAll(), 500);
            });

            refreshList();
        } catch (err) {
            console.error('Failed to load session:', err);
        }
    }

    function getCurrent() {
        return currentSession;
    }

    /** Schedule a debounced auto-save. */
    function scheduleSave() {
        if (!currentSession) return;
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(doSave, SAVE_DEBOUNCE);
    }

    /** Immediately flush any pending save (cancel debounce and save now). */
    async function flushSave() {
        clearTimeout(saveTimeout);
        await doSave();
    }

    async function doSave() {
        if (!currentSession) return;
        // Capture current viewport state
        currentSession.viewport = Canvas.getState();
        currentSession.updated_at = new Date().toISOString();

        // Capture node positions, dimensions, and collapsed state from DOM
        for (const [id, nodeData] of Object.entries(currentSession.nodes)) {
            const el = document.getElementById(id);
            if (el) {
                nodeData.x = parseFloat(el.style.left) || 0;
                nodeData.y = parseFloat(el.style.top) || 0;

                // Capture custom width/height
                const w = parseFloat(el.style.width);
                if (w && w > 0) nodeData.width = w;
                const h = el.style.height ? parseFloat(el.style.height) : null;
                if (h && h > 0) nodeData.height = h;
                else nodeData.height = null;

                // Capture collapsed state
                const promptEl = el.querySelector('.node-prompt');
                if (promptEl) {
                    nodeData.prompt_collapsed = promptEl.classList.contains('collapsed');
                }
                const responseEl = el.querySelector('.node-response');
                if (responseEl) {
                    nodeData.response_collapsed = responseEl.classList.contains('collapsed');
                }
            }
            // Capture response_html from DOM (includes highlights)
            const responseContent = el?.querySelector('.node-response-content');
            if (responseContent && nodeData.status === 'complete') {
                nodeData.response_html = responseContent.innerHTML;
            }
        }

        try {
            await API.saveSession(currentSession.id, currentSession);
        } catch (err) {
            console.error('Auto-save failed:', err);
        }
    }

    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    return { init, getCurrent, scheduleSave, refreshList, createNew, loadSession };
})();
