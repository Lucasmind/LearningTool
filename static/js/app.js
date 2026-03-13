/**
 * app.js — Main entry point. Wires everything together.
 */

const App = (() => {
    let nodeCounter = 0;

    function init() {
        Canvas.init();
        EdgeRenderer.init();
        Session.init();
        ContextMenu.init();

        // Theme toggle
        const themeBtn = document.getElementById('btn-theme-toggle');
        const savedTheme = localStorage.getItem('lt-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeIcon(themeBtn, savedTheme);
        themeBtn.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('lt-theme', next);
            updateThemeIcon(themeBtn, next);
        });

        // Prompt input
        const promptInput = document.getElementById('prompt-input');
        const submitBtn = document.getElementById('btn-submit-prompt');

        submitBtn.addEventListener('click', () => submitInitialPrompt(promptInput));
        promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitInitialPrompt(promptInput);
            }
        });

        // Auto-layout button
        document.getElementById('btn-auto-layout').addEventListener('click', autoLayout);

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                ContextMenu.hide();
            }
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                Session.scheduleSave();
            }
        });
    }

    function updateThemeIcon(btn, theme) {
        btn.textContent = theme === 'dark' ? '☀' : '🌙';
    }

    async function submitInitialPrompt(input) {
        const text = input.value.trim();
        if (!text) return;

        // Ensure we have a session
        let session = Session.getCurrent();
        if (!session) {
            await Session.createNew();
            session = Session.getCurrent();
        }

        input.value = '';

        // Create node data
        const nodeId = generateNodeId();
        const nodeData = {
            id: nodeId,
            parent_id: null,
            highlight_id: null,
            x: computeInitialPosition(session).x,
            y: computeInitialPosition(session).y,
            prompt_text: text,
            prompt_mode: 'initial',
            response_html: '',
            response_text: '',
            highlighted_text: null,
            status: 'queued',
            created_at: new Date().toISOString(),
        };

        // Add to session
        session.nodes[nodeId] = nodeData;

        // Create DOM node
        NodeRenderer.createNode(nodeData);

        // Auto-title the session if this is the first prompt
        const isFirstPrompt = Object.keys(session.nodes).length === 1;
        if (isFirstPrompt && session.name === 'Untitled Session') {
            API.generateTitle(text).then(result => {
                if (result.title && result.title !== 'Untitled Session') {
                    session.name = result.title;
                    document.getElementById('session-name-display').textContent = result.title;
                    API.renameSession(session.id, result.title).catch(console.error);
                    Session.refreshList();
                }
            }).catch(console.error);
        }

        // Submit to API via streaming
        streamQueryToNode({
            session_id: session.id,
            parent_node_id: null,
            prompt_text: text,
            mode: 'initial',
        }, nodeId);

        Session.scheduleSave();
    }

    /**
     * Spawn a child node from a highlight action.
     * @param {string} parentNodeId
     * @param {string} highlightId
     * @param {string} highlightedText
     * @param {string} action — 'explain' | 'deeper' | 'question'
     */
    async function spawnChild(parentNodeId, highlightId, highlightedText, action) {
        const session = Session.getCurrent();
        if (!session) return;

        const parentNode = session.nodes[parentNodeId];
        if (!parentNode) return;

        // Compute child position, anchored near the highlight that spawned it
        const pos = computeChildPosition(parentNode, session, highlightId);

        const nodeId = generateNodeId();
        const edgeId = 'edge_' + Date.now().toString(36);

        // For "question" mode, create an editable node first
        const isQuestion = action === 'question';

        // Build a user-facing prompt summary (not the full engineered prompt)
        const promptSummaries = {
            explain: `Explain: "${highlightedText}"`,
            deeper: `Deep dive: "${highlightedText}"`,
            question: '',
        };

        const nodeData = {
            id: nodeId,
            parent_id: parentNodeId,
            highlight_id: highlightId,
            x: pos.x,
            y: pos.y,
            prompt_text: promptSummaries[action] || '',
            prompt_mode: action,
            response_html: '',
            response_text: '',
            highlighted_text: highlightedText,
            status: isQuestion ? 'waiting' : 'queued',
            created_at: new Date().toISOString(),
        };

        // Add to session
        session.nodes[nodeId] = nodeData;
        session.edges.push({
            id: edgeId,
            source_node_id: parentNodeId,
            source_highlight_id: highlightId,
            target_node_id: nodeId,
        });
        session.highlights[highlightId] = {
            id: highlightId,
            node_id: parentNodeId,
            text: highlightedText,
            color: 'rgba(59,130,246,0.3)',
        };

        // Create DOM node
        NodeRenderer.createNode(nodeData, { editable: isQuestion });

        // Draw edge (delay to let DOM settle)
        requestAnimationFrame(() => {
            EdgeRenderer.redrawAll();
            // Second pass after layout reflow
            setTimeout(() => EdgeRenderer.redrawAll(), 100);
        });

        // If not a question, submit immediately via streaming
        if (!isQuestion) {
            streamQueryToNode({
                session_id: session.id,
                parent_node_id: parentNodeId,
                prompt_text: '',
                mode: action,
                highlighted_text: highlightedText,
            }, nodeId);
        }

        Session.scheduleSave();
    }

    /**
     * Submit a user-typed question from an editable node.
     */
    async function submitQuestion(nodeId, question) {
        const session = Session.getCurrent();
        if (!session || !session.nodes[nodeId]) return;

        const nodeData = session.nodes[nodeId];

        nodeData.user_question = question;
        NodeRenderer.updateNode(nodeId, { status: 'running', prompt_text: question });
        streamQueryToNode({
            session_id: session.id,
            parent_node_id: nodeData.parent_id,
            prompt_text: question,
            mode: 'question',
            highlighted_text: nodeData.highlighted_text,
            user_question: question,
        }, nodeId);

        Session.scheduleSave();
    }

    /**
     * Retry a node's query.
     */
    async function retryNode(nodeId) {
        const session = Session.getCurrent();
        if (!session || !session.nodes[nodeId]) return;

        // Find the original job (we need to store job_id on the node or re-submit)
        // Simplest: re-submit the same query
        const nodeData = session.nodes[nodeId];
        NodeRenderer.updateNode(nodeId, { status: 'running', response_html: '', response_text: '' });

        streamQueryToNode({
            session_id: session.id,
            parent_node_id: nodeData.parent_id,
            prompt_text: nodeData.prompt_mode === 'initial' ? nodeData.prompt_text : '',
            mode: nodeData.prompt_mode,
            highlighted_text: nodeData.highlighted_text,
            user_question: nodeData.prompt_mode === 'question' ? nodeData.prompt_text : undefined,
        }, nodeId);
    }

    /** Stream a query to a node via SSE. Shows thinking, then streams content tokens. */
    function streamQueryToNode(queryData, nodeId) {
        const session = Session.getCurrent();
        let contentStarted = false;

        API.streamQuery(queryData, {
            onPrompt(engineeredPrompt) {
                if (session && session.nodes[nodeId]) {
                    session.nodes[nodeId].engineered_prompt = engineeredPrompt;
                }
            },
            onThinking() {
                // Only update to thinking state if content hasn't started streaming
                if (!contentStarted) {
                    NodeRenderer.updateNode(nodeId, { status: 'running' });
                }
            },
            onToken(text) {
                contentStarted = true;
                NodeRenderer.streamToken(nodeId, text);
            },
            onDone(fullText) {
                NodeRenderer.finishStreaming(nodeId, fullText);
                Session.scheduleSave();
                requestAnimationFrame(() => {
                    EdgeRenderer.redrawAll();
                    setTimeout(() => EdgeRenderer.redrawAll(), 150);
                });
            },
            onError(msg) {
                NodeRenderer.updateNode(nodeId, {
                    status: 'error',
                    response_text: msg || 'Unknown error',
                });
                Session.scheduleSave();
            },
        });
    }

    function generateNodeId() {
        nodeCounter++;
        return 'node_' + Date.now().toString(36) + '_' + nodeCounter;
    }

    function computeInitialPosition(session) {
        const nodes = Object.values(session.nodes);
        if (nodes.length === 0) {
            return { x: 80, y: 80 };
        }
        // Place below the last root node, using actual DOM height
        const rootNodes = nodes.filter(n => !n.parent_id);
        const lastRoot = rootNodes[rootNodes.length - 1];
        const lastEl = lastRoot ? document.getElementById(lastRoot.id) : null;
        const lastHeight = lastEl ? lastEl.offsetHeight : 400;
        return { x: (lastRoot || nodes[nodes.length - 1]).x, y: (lastRoot || nodes[nodes.length - 1]).y + lastHeight + 60 };
    }

    function computeChildPosition(parentNode, session, highlightId) {
        const GAP_X = 60;
        const GAP_Y = 40;
        const thisW = 420;
        const estimatedH = 200;  // Approximate height for a fresh node

        // Place child to the right of the parent, clearing its actual width
        const parentEl = document.getElementById(parentNode.id);
        const parentW = parentEl ? parentEl.offsetWidth : 420;
        const x = parentNode.x + parentW + GAP_X;

        // Ideal Y: align with the highlight mark that spawned this child
        let idealY = parentNode.y;  // fallback to parent top
        if (highlightId) {
            const mark = document.querySelector(`mark[data-highlight-id="${CSS.escape(highlightId)}"]`);
            if (mark && parentEl) {
                const markRect = mark.getBoundingClientRect();
                const parentRect = parentEl.getBoundingClientRect();
                const zoom = Canvas.getZoom();
                // Convert mark's screen position to world Y offset from parent
                const markOffsetY = (markRect.top - parentRect.top) / zoom;
                idealY = parentNode.y + markOffsetY;
            }
        }

        // Collect ALL nodes that horizontally overlap with our target column
        const allNodes = Object.values(session.nodes);
        const obstacles = [];
        for (const other of allNodes) {
            const otherEl = document.getElementById(other.id);
            if (!otherEl) continue;
            const otherW = otherEl.offsetWidth || 420;
            const otherH = otherEl.offsetHeight || 400;
            const otherX = parseFloat(otherEl.style.left) || other.x;
            const otherY = parseFloat(otherEl.style.top) || other.y;

            if (x < otherX + otherW && x + thisW > otherX) {
                obstacles.push({ top: otherY, bottom: otherY + otherH });
            }
        }

        // Sort obstacles top-to-bottom
        obstacles.sort((a, b) => a.top - b.top);

        // First-fit from ideal Y: scan down, place in the first gap that fits
        let y = idealY;
        for (const obs of obstacles) {
            if (y + estimatedH + GAP_Y <= obs.top) {
                break;
            }
            if (y < obs.bottom + GAP_Y) {
                y = obs.bottom + GAP_Y;
            }
        }

        return { x, y };
    }

    /**
     * Auto-layout: organize all nodes into a clean left-to-right tree.
     * Layered by depth, subtrees centered, no overlaps, no edge crossings.
     */
    function autoLayout() {
        const session = Session.getCurrent();
        if (!session || Object.keys(session.nodes).length === 0) return;

        const nodes = session.nodes;
        const GAP_X = 240;  // horizontal gap between parent and children
        const GAP_Y = 40;   // vertical gap between sibling subtrees
        const START_X = 80;
        const START_Y = 80;

        // Build parent -> children map (maintains creation order)
        const childrenOf = {};
        const roots = [];

        for (const [id, node] of Object.entries(nodes)) {
            if (!node.parent_id || !nodes[node.parent_id]) {
                roots.push(id);
            } else {
                if (!childrenOf[node.parent_id]) childrenOf[node.parent_id] = [];
                childrenOf[node.parent_id].push(id);
            }
        }

        // Get actual DOM dimensions for each node
        function getDims(nodeId) {
            const el = document.getElementById(nodeId);
            return {
                w: el ? el.offsetWidth : 420,
                h: el ? el.offsetHeight : 200,
            };
        }

        // Compute subtree height for each node (bottom-up)
        const subtreeH = {};
        function computeSubtreeHeight(nodeId) {
            const kids = childrenOf[nodeId] || [];
            const ownH = getDims(nodeId).h;

            if (kids.length === 0) {
                subtreeH[nodeId] = ownH;
                return ownH;
            }

            let totalKidsH = 0;
            for (const kid of kids) {
                totalKidsH += computeSubtreeHeight(kid);
            }
            totalKidsH += (kids.length - 1) * GAP_Y;

            subtreeH[nodeId] = Math.max(ownH, totalKidsH);
            return subtreeH[nodeId];
        }
        for (const root of roots) {
            computeSubtreeHeight(root);
        }

        // Assign positions top-down: each node centered in its subtree's vertical span
        // X is based on parent's actual width, not a fixed column grid
        const positions = {};
        function assignPositions(nodeId, x, yStart) {
            const ownW = getDims(nodeId).w;
            const ownH = getDims(nodeId).h;
            const treeH = subtreeH[nodeId];
            const kids = childrenOf[nodeId] || [];

            // Center this node in its subtree space
            const y = yStart + treeH / 2 - ownH / 2;
            positions[nodeId] = { x, y };

            if (kids.length === 0) return;

            // Children X based on this node's actual width
            const childX = x + ownW + GAP_X;

            // Center children block within the subtree space
            const totalKidsH = kids.reduce((s, k) => s + subtreeH[k], 0)
                + (kids.length - 1) * GAP_Y;
            let childY = yStart + treeH / 2 - totalKidsH / 2;

            for (const kid of kids) {
                assignPositions(kid, childX, childY);
                childY += subtreeH[kid] + GAP_Y;
            }
        }

        let rootY = START_Y;
        for (const root of roots) {
            assignPositions(root, START_X, rootY);
            rootY += subtreeH[root] + GAP_Y * 2;
        }

        // Apply positions with a brief transition
        const nodeIds = Object.keys(positions);
        for (const id of nodeIds) {
            const el = document.getElementById(id);
            if (el) el.style.transition = 'left 0.4s ease, top 0.4s ease';
        }

        requestAnimationFrame(() => {
            for (const [id, pos] of Object.entries(positions)) {
                const el = document.getElementById(id);
                if (el) {
                    el.style.left = pos.x + 'px';
                    el.style.top = pos.y + 'px';
                }
                if (nodes[id]) {
                    nodes[id].x = pos.x;
                    nodes[id].y = pos.y;
                }
            }

            // Reset viewport to show the tree from the top-left
            Canvas.resetView();

            // Continuously redraw edges during the transition
            const redrawInterval = setInterval(() => EdgeRenderer.redrawAll(), 30);
            setTimeout(() => {
                clearInterval(redrawInterval);
                // Clean up transitions
                for (const id of nodeIds) {
                    const el = document.getElementById(id);
                    if (el) el.style.transition = '';
                }
                EdgeRenderer.redrawAll();
                Session.scheduleSave();
            }, 450);
        });
    }

    // Public API
    return { init, spawnChild, submitQuestion, retryNode, autoLayout };
})();

// Boot
document.addEventListener('DOMContentLoaded', App.init);
