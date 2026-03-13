/**
 * api.js — Fetch wrappers for all backend endpoints.
 */

const API = (() => {
    const BASE = '';  // Same origin

    async function _fetch(url, opts = {}) {
        const resp = await fetch(BASE + url, {
            headers: { 'Content-Type': 'application/json' },
            ...opts,
        });
        if (!resp.ok) {
            const err = await resp.text();
            throw new Error(`API ${resp.status}: ${err}`);
        }
        return resp.json();
    }

    // ---- Query ----
    function submitQuery(data) {
        return _fetch('/api/query', { method: 'POST', body: JSON.stringify(data) });
    }

    function queryStatus(jobId) {
        return _fetch(`/api/query/${jobId}/status`);
    }

    function retryQuery(jobId) {
        return _fetch(`/api/query/${jobId}/retry`, { method: 'POST' });
    }

    // ---- Sessions ----
    function listSessions() {
        return _fetch('/api/sessions');
    }

    function createSession(name) {
        return _fetch('/api/sessions', { method: 'POST', body: JSON.stringify({ name }) });
    }

    function loadSession(id) {
        return _fetch(`/api/sessions/${id}`);
    }

    function saveSession(id, data) {
        return _fetch(`/api/sessions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    }

    function renameSession(id, name) {
        return _fetch(`/api/sessions/${id}/rename`, { method: 'PUT', body: JSON.stringify({ name }) });
    }

    function deleteSession(id) {
        return _fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    }

    // ---- Trash ----
    function listTrash() {
        return _fetch('/api/trash');
    }

    function restoreSession(id) {
        return _fetch(`/api/trash/${id}/restore`, { method: 'POST' });
    }

    function permanentDeleteSession(id) {
        return _fetch(`/api/trash/${id}`, { method: 'DELETE' });
    }

    // ---- Streaming query ----
    /**
     * Stream a query via SSE. Calls callbacks as events arrive.
     * @param {object} data — query request body
     * @param {object} callbacks — { onPrompt, onThinking, onToken, onDone, onError, onFallback }
     */
    async function streamQuery(data, callbacks) {
        const resp = await fetch(BASE + '/api/query/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!resp.ok) {
            const err = await resp.text();
            if (callbacks.onError) callbacks.onError(`API ${resp.status}: ${err}`);
            return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processLines(lines) {
            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7);
                } else if (line.startsWith('data: ')) {
                    try {
                        const payload = JSON.parse(line.slice(6));
                        if (eventType === 'prompt' && callbacks.onPrompt) callbacks.onPrompt(payload.engineered_prompt);
                        else if (eventType === 'thinking' && callbacks.onThinking) callbacks.onThinking();
                        else if (eventType === 'token' && callbacks.onToken) callbacks.onToken(payload.text);
                        else if (eventType === 'done' && callbacks.onDone) callbacks.onDone(payload.text);
                        else if (eventType === 'fallback' && callbacks.onFallback) callbacks.onFallback(payload.from, payload.to);
                        else if (eventType === 'error' && callbacks.onError) callbacks.onError(payload.error);
                    } catch (e) {
                        // skip malformed JSON
                    }
                    eventType = '';
                }
            }
        }

        let eventType = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();  // keep incomplete line
            processLines(lines);
        }

        // Process any remaining data in the buffer after stream ends
        if (buffer.trim()) {
            processLines(buffer.split('\n'));
        }
    }

    // ---- Title generation ----
    function generateTitle(promptText) {
        return _fetch('/api/generate-title', {
            method: 'POST',
            body: JSON.stringify({ prompt_text: promptText }),
        });
    }

    // ---- Settings / Providers ----
    function getProviderList() {
        return _fetch('/api/settings/provider-list');
    }

    function getProviders() {
        return _fetch('/api/settings/providers');
    }

    function addProvider(config) {
        return _fetch('/api/settings/providers', { method: 'POST', body: JSON.stringify(config) });
    }

    function updateProvider(id, data) {
        return _fetch(`/api/settings/providers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    }

    function deleteProvider(id) {
        return _fetch(`/api/settings/providers/${id}`, { method: 'DELETE' });
    }

    function testProvider(id) {
        return _fetch(`/api/settings/providers/${id}/test`, { method: 'POST' });
    }

    function setDefaultProvider(id) {
        return _fetch('/api/settings/default-provider', { method: 'PUT', body: JSON.stringify({ provider_id: id }) });
    }

    function setFallbackProvider(id) {
        return _fetch('/api/settings/fallback-provider', { method: 'PUT', body: JSON.stringify({ provider_id: id || null }) });
    }

    return { submitQuery, queryStatus, retryQuery, streamQuery, listSessions, createSession, loadSession, saveSession, renameSession, deleteSession, listTrash, restoreSession, permanentDeleteSession, generateTitle, getProviderList, getProviders, addProvider, updateProvider, deleteProvider, testProvider, setDefaultProvider, setFallbackProvider };
})();
