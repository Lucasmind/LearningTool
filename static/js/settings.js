/**
 * settings.js — Settings overlay for managing LLM providers.
 */

const Settings = (() => {
    let overlay = null;
    let providers = [];
    let defaultId = null;
    let fallbackId = null;

    function init() {
        overlay = document.getElementById('settings-overlay');
    }

    function show() {
        if (!overlay) return;
        overlay.classList.remove('hidden');
        loadProviders();
    }

    function hide() {
        if (!overlay) return;
        overlay.classList.add('hidden');
    }

    async function loadProviders() {
        try {
            const data = await API.getProviders();
            providers = data.providers;
            defaultId = data.default_provider_id;
            fallbackId = data.fallback_provider_id;
            render();
        } catch (e) {
            console.error('Failed to load providers:', e);
        }
    }

    function render() {
        const panel = overlay.querySelector('.settings-panel');
        if (!panel) return;

        // Clear content using DOM methods
        while (panel.firstChild) panel.removeChild(panel.firstChild);

        // Header
        const header = document.createElement('div');
        header.className = 'settings-header';
        const h2 = document.createElement('h2');
        h2.textContent = 'LLM Providers';
        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-icon settings-close';
        closeBtn.textContent = '\u00D7';
        closeBtn.addEventListener('click', hide);
        header.appendChild(h2);
        header.appendChild(closeBtn);
        panel.appendChild(header);

        // Add provider button
        const addBtn = document.createElement('button');
        addBtn.className = 'btn btn-primary settings-add-btn';
        addBtn.textContent = '+ Add Provider';
        addBtn.addEventListener('click', () => showForm(null));
        panel.appendChild(addBtn);

        // Provider cards
        const list = document.createElement('div');
        list.className = 'provider-list';
        for (const p of providers) {
            list.appendChild(createCard(p));
        }
        panel.appendChild(list);

        // Fallback section
        const fbSection = document.createElement('div');
        fbSection.className = 'settings-fallback-section';
        const fbLabel = document.createElement('label');
        fbLabel.textContent = 'Fallback Provider: ';
        const fbSelect = document.createElement('select');
        fbSelect.className = 'provider-select';
        const noneOpt = document.createElement('option');
        noneOpt.value = '';
        noneOpt.textContent = '(None)';
        fbSelect.appendChild(noneOpt);
        for (const p of providers) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.alias;
            if (p.id === fallbackId) opt.selected = true;
            fbSelect.appendChild(opt);
        }
        fbSelect.addEventListener('change', async () => {
            await API.setFallbackProvider(fbSelect.value || null);
            fallbackId = fbSelect.value || null;
        });
        fbSection.appendChild(fbLabel);
        fbSection.appendChild(fbSelect);
        panel.appendChild(fbSection);
    }

    function createCard(p) {
        const card = document.createElement('div');
        card.className = 'provider-card';
        if (!p.enabled) card.classList.add('provider-disabled');

        // Info row
        const info = document.createElement('div');
        info.className = 'provider-card-info';

        const aliasEl = document.createElement('span');
        aliasEl.className = 'provider-alias';
        aliasEl.textContent = p.alias;
        info.appendChild(aliasEl);

        const typeEl = document.createElement('span');
        typeEl.className = 'provider-type-badge';
        typeEl.textContent = p.type === 'claude-cli' ? 'CLI' : 'API';
        info.appendChild(typeEl);

        if (p.id === defaultId) {
            const defBadge = document.createElement('span');
            defBadge.className = 'provider-badge provider-badge-default';
            defBadge.textContent = 'DEFAULT';
            info.appendChild(defBadge);
        }
        if (p.id === fallbackId) {
            const fbBadge = document.createElement('span');
            fbBadge.className = 'provider-badge provider-badge-fallback';
            fbBadge.textContent = 'FALLBACK';
            info.appendChild(fbBadge);
        }

        card.appendChild(info);

        // Details
        const details = document.createElement('div');
        details.className = 'provider-card-details';
        if (p.type !== 'claude-cli' && p.url) {
            const urlEl = document.createElement('div');
            urlEl.className = 'provider-detail';
            urlEl.textContent = p.url;
            details.appendChild(urlEl);
        }
        if (p.model) {
            const modelEl = document.createElement('div');
            modelEl.className = 'provider-detail';
            modelEl.textContent = 'Model: ' + p.model;
            details.appendChild(modelEl);
        }
        card.appendChild(details);

        // Test result area
        const testResult = document.createElement('div');
        testResult.className = 'provider-test-result hidden';
        card.appendChild(testResult);

        // Actions
        const actions = document.createElement('div');
        actions.className = 'provider-card-actions';

        const testBtn = document.createElement('button');
        testBtn.className = 'btn btn-sm';
        testBtn.textContent = 'Test';
        testBtn.addEventListener('click', async () => {
            testBtn.disabled = true;
            testBtn.textContent = 'Testing...';
            testResult.classList.remove('hidden', 'test-success', 'test-error');
            try {
                const result = await API.testProvider(p.id);
                testResult.classList.add(result.success ? 'test-success' : 'test-error');
                testResult.textContent = result.message + (result.response_preview ? ' — "' + result.response_preview.slice(0, 100) + '"' : '');
            } catch (e) {
                testResult.classList.add('test-error');
                testResult.textContent = 'Test failed: ' + e.message;
            }
            testResult.classList.remove('hidden');
            testBtn.disabled = false;
            testBtn.textContent = 'Test';
        });

        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => showForm(p));

        const defBtn = document.createElement('button');
        defBtn.className = 'btn btn-sm';
        if (p.id === defaultId) {
            defBtn.textContent = 'Is Default';
            defBtn.disabled = true;
            defBtn.style.opacity = '0.5';
        } else {
            defBtn.textContent = 'Set Default';
        }
        defBtn.addEventListener('click', async () => {
            try {
                await API.setDefaultProvider(p.id);
                defaultId = p.id;
                await loadProviders();
                App.loadProviderDropdown();
            } catch (e) {
                console.error('Set default failed:', e);
                alert('Failed to set default: ' + e.message);
            }
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-sm btn-danger';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', async () => {
            if (!confirm('Delete provider "' + p.alias + '"?')) return;
            try {
                await API.deleteProvider(p.id);
                loadProviders();
                App.loadProviderDropdown();
            } catch (e) {
                alert('Cannot delete: ' + e.message);
            }
        });

        actions.appendChild(testBtn);
        actions.appendChild(editBtn);
        actions.appendChild(defBtn);
        actions.appendChild(delBtn);
        card.appendChild(actions);

        return card;
    }

    function showForm(existing) {
        const panel = overlay.querySelector('.settings-panel');
        if (!panel) return;

        // Clear
        while (panel.firstChild) panel.removeChild(panel.firstChild);

        const header = document.createElement('div');
        header.className = 'settings-header';
        const h2 = document.createElement('h2');
        h2.textContent = existing ? 'Edit Provider' : 'Add Provider';
        const backBtn = document.createElement('button');
        backBtn.className = 'btn btn-sm';
        backBtn.textContent = 'Back';
        backBtn.addEventListener('click', () => render());
        header.appendChild(h2);
        header.appendChild(backBtn);
        panel.appendChild(header);

        const form = document.createElement('div');
        form.className = 'provider-form';

        const fields = [
            { key: 'alias', label: 'Alias / Name', type: 'text', value: existing?.alias || '' },
            { key: 'type', label: 'Type', type: 'select', options: [
                { value: 'openai-compatible', label: 'OpenAI-Compatible API' },
                { value: 'claude-cli', label: 'Claude Code (CLI)' },
            ], value: existing?.type || 'openai-compatible' },
            { key: 'url', label: 'API URL', type: 'text', value: existing?.url || '', hideFor: 'claude-cli', placeholder: 'e.g. http://localhost:8080 or http://api.openai.com/v1/chat/completions' },
            { key: 'model', label: 'Model', type: 'text', value: existing?.model || '', placeholder: 'e.g. opus, sonnet, haiku (for CLI) or gpt-4o (for API)' },
            { key: 'api_key', label: 'API Key', type: 'password', value: existing?.api_key || '', hideFor: 'claude-cli' },
            { key: 'max_tokens', label: 'Max Tokens', type: 'number', value: existing?.max_tokens ?? 4096 },
            { key: 'temperature', label: 'Temperature', type: 'number', value: existing?.temperature ?? 0.7, step: '0.1' },
            { key: 'timeout', label: 'Timeout (seconds)', type: 'number', value: existing?.timeout ?? 300 },
            { key: 'enabled', label: 'Enabled', type: 'checkbox', value: existing?.enabled ?? true },
        ];

        const inputs = {};
        const fieldRows = {};

        for (const f of fields) {
            const row = document.createElement('div');
            row.className = 'form-row';
            if (f.hideFor) row.dataset.hideFor = f.hideFor;

            const label = document.createElement('label');
            label.textContent = f.label;
            row.appendChild(label);

            let input;
            if (f.type === 'select') {
                input = document.createElement('select');
                input.className = 'form-input';
                for (const opt of f.options) {
                    const o = document.createElement('option');
                    o.value = opt.value;
                    o.textContent = opt.label;
                    if (opt.value === f.value) o.selected = true;
                    input.appendChild(o);
                }
            } else if (f.type === 'checkbox') {
                input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = f.value;
            } else {
                input = document.createElement('input');
                input.className = 'form-input';
                input.type = f.type;
                input.value = f.value;
                if (f.step) input.step = f.step;
                if (f.placeholder) input.placeholder = f.placeholder;
                if (f.type === 'password') input.placeholder = existing ? '(unchanged)' : '';
            }

            inputs[f.key] = input;
            row.appendChild(input);
            form.appendChild(row);
            fieldRows[f.key] = row;
        }

        // Toggle visibility based on type
        function updateVisibility() {
            const type = inputs.type.value;
            for (const f of fields) {
                if (f.hideFor && fieldRows[f.key]) {
                    fieldRows[f.key].style.display = type === f.hideFor ? 'none' : '';
                }
            }
        }
        inputs.type.addEventListener('change', updateVisibility);
        updateVisibility();

        panel.appendChild(form);

        // Save button
        const saveRow = document.createElement('div');
        saveRow.className = 'form-actions';
        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-primary';
        saveBtn.textContent = existing ? 'Save Changes' : 'Add Provider';
        saveBtn.addEventListener('click', async () => {
            const data = {};
            for (const f of fields) {
                if (f.type === 'checkbox') {
                    data[f.key] = inputs[f.key].checked;
                } else if (f.type === 'number') {
                    data[f.key] = parseFloat(inputs[f.key].value);
                } else {
                    data[f.key] = inputs[f.key].value;
                }
            }
            // Don't send empty password (means "keep existing")
            if (existing && !data.api_key) {
                delete data.api_key;
            }

            try {
                if (existing) {
                    await API.updateProvider(existing.id, data);
                } else {
                    await API.addProvider(data);
                }
                loadProviders();
                App.loadProviderDropdown();
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });
        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', () => render());
        saveRow.appendChild(saveBtn);
        saveRow.appendChild(cancelBtn);
        panel.appendChild(saveRow);
    }

    return { init, show, hide };
})();
