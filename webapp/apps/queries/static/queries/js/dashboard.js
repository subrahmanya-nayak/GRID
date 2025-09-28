(function () {
    const modalElement = document.getElementById('processingModal');
    const processingModal = modalElement ? new bootstrap.Modal(modalElement, {backdrop: 'static', keyboard: false}) : null;
    const templateModalElement = document.getElementById('templateModal');
    const templateModal = templateModalElement ? new bootstrap.Modal(templateModalElement) : null;
    const drawerElement = document.getElementById('resultDrawer');
    const resultDrawer = drawerElement ? new bootstrap.Offcanvas(drawerElement) : null;
    const toastElement = document.getElementById('completion-toast');
    const completionToast = toastElement ? new bootstrap.Toast(toastElement, {delay: 5000}) : null;

    const initialDataElement = document.getElementById('initial-data');
    const initialData = initialDataElement ? JSON.parse(initialDataElement.textContent || '[]') : [];
    const templateDataElement = document.getElementById('template-data');
    const templateData = templateDataElement ? JSON.parse(templateDataElement.textContent || '[]') : [];

    const csrftoken = document.querySelector('#query-form [name=csrfmiddlewaretoken]').value;
    let historyList = document.getElementById('history-list');
    const queryTextarea = document.querySelector('#query-form textarea');
    const templateForm = document.getElementById('template-form');
    const healthContainer = document.getElementById('health-metrics');

    const pollers = {};
    let activeFilter = null;
    let drawerQueryId = null;
    let pendingTemplateId = null;

    const statusBadge = (status) => {
        const map = {
            pending: 'secondary',
            running: 'info',
            success: 'success',
            failed: 'danger'
        };
        const label = status.charAt(0).toUpperCase() + status.slice(1);
        return `<span class="badge text-bg-${map[status] || 'secondary'}">${label}</span>`;
    };

    const progressCell = (progress, stage) => {
        const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
        const stageLabel = stage || '';
        return `<div class="d-flex flex-column gap-1">
                    <div class="progress-pill"><span style="width:${safeProgress}%"></span></div>
                    <small class="text-muted">${safeProgress}% · ${stageLabel}</small>
                </div>`;
    };

    const sourcesCell = (results) => {
        if (!results || !results.length) {
            return '<span class="text-muted">—</span>';
        }
        const unique = Array.from(new Set(results.map((item) => item.source || 'Result')));
        return unique.map((source) => `<span class="badge text-bg-light text-uppercase fw-semibold">${source}</span>`).join(' ');
    };

    const actionsCell = (payload) => {
        const disabled = payload.status === 'pending' ? 'disabled' : '';
        return `<div class="d-flex justify-content-end gap-2">
                    <button class="btn btn-sm btn-outline-primary inspect-btn" data-query-id="${payload.id}" ${disabled}>
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-success export-btn" data-query-id="${payload.id}" ${disabled}>
                        <i class="bi bi-download"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary rerun-btn" data-query-id="${payload.id}">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>
                </div>`;
    };

    const table = $('#results-table').DataTable({
        responsive: true,
        order: [[0, 'desc']],
        columnDefs: [
            {targets: [5], orderable: false}
        ]
    });

    const upsertRow = (payload, options = {}) => {
        const rowSelector = `#query-${payload.id}`;
        const existingRow = table.row(rowSelector);
        const rowData = [
            payload.created_at,
            statusBadge(payload.status),
            progressCell(payload.progress, payload.stage),
            payload.classification ? `<span class="badge text-bg-dark-subtle text-dark">${payload.classification}</span>` : '<span class="text-muted">—</span>',
            sourcesCell(payload.results),
            actionsCell(payload)
        ];
        let rowNode;
        if (existingRow && existingRow.length) {
            existingRow.data(rowData).draw(false);
            rowNode = existingRow.node();
        } else {
            rowNode = table.row.add(rowData).draw(false).node();
            if (rowNode) {
                rowNode.id = rowSelector.replace('#', '');
            }
        }
        if (rowNode) {
            rowNode.dataset.status = payload.status;
        }
        if (!options.silent && payload.status === 'success' && completionToast) {
            toastElement.querySelector('.toast-body').textContent = 'Query completed successfully.';
            completionToast.show();
        }
        return rowNode;
    };

    const applyFilter = (status) => {
        activeFilter = status;
        table.rows().every(function () {
            const node = this.node();
            if (!status || node.dataset.status === status) {
                $(node).show();
            } else {
                $(node).hide();
            }
        });
    };

    const healthUrl = healthContainer ? healthContainer.dataset.healthUrl : null;
    const renderHealth = (data) => {
        if (!healthContainer) {
            return;
        }
        const valueFor = (key) => {
            const valueEl = healthContainer.querySelector(`[data-health-key="${key}"]`);
            if (!valueEl) {
                return;
            }
            const ok = key === 'celery' ? data.celery_ok : data.checks?.[key];
            const label = ok ? '<span class="text-success fw-semibold">Healthy</span>' : '<span class="text-danger fw-semibold">Issue</span>';
            valueEl.innerHTML = label;
        };
        ['celery', 'clinical_trials', 'open_targets'].forEach((key) => valueFor(key));
    };

    const refreshHealth = () => {
        if (!healthUrl) {
            return;
        }
        fetch(healthUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then((response) => response.json())
            .then(renderHealth)
            .catch(() => {
                if (!healthContainer) {
                    return;
                }
                healthContainer.querySelectorAll('[data-health-key]').forEach((node) => {
                    node.innerHTML = '<span class="text-warning fw-semibold">Unknown</span>';
                });
            });
    };

    const populateDrawer = (payload) => {
        if (!resultDrawer || !drawerElement) {
            return;
        }
        drawerQueryId = payload.id;
        drawerElement.querySelector('#resultDrawerLabel').textContent = payload.text || 'Query insights';
        const metaEl = drawerElement.querySelector('#drawer-meta');
        metaEl.innerHTML = `${statusBadge(payload.status)} · Routed as <strong>${payload.resolution || payload.classification || '—'}</strong>`;
        const rationaleEl = drawerElement.querySelector('#drawer-rationale');
        rationaleEl.textContent = payload.router_rationale || '—';
        const durationEl = drawerElement.querySelector('#drawer-duration');
        if (payload.duration_ms) {
            durationEl.textContent = `Completed in ${(payload.duration_ms / 1000).toFixed(1)}s`;
        } else {
            durationEl.textContent = '';
        }
        const tagsWrapper = drawerElement.querySelector('#drawer-tags');
        tagsWrapper.innerHTML = '';
        (payload.tags || []).forEach((tag) => {
            const span = document.createElement('span');
            span.className = 'badge';
            span.textContent = tag;
            tagsWrapper.appendChild(span);
        });
        const tagsInput = drawerElement.querySelector('#tags-input');
        tagsInput.value = (payload.tags || []).join(', ');
        const exportBtn = drawerElement.querySelector('#drawer-export');
        exportBtn.dataset.queryId = payload.id;

        const tabs = drawerElement.querySelector('#sourceTabs');
        const tabContent = drawerElement.querySelector('#sourceTabContent');
        tabs.innerHTML = '';
        tabContent.innerHTML = '';

        const results = payload.results || [];
        if (!results.length) {
            tabContent.innerHTML = '<p class="text-muted">No data available yet.</p>';
            resultDrawer.show();
            return;
        }
        const grouped = results.reduce((acc, entry) => {
            const source = entry.source || 'Result';
            if (!acc[source]) {
                acc[source] = [];
            }
            acc[source].push(entry);
            return acc;
        }, {});
        const sources = Object.keys(grouped);
        sources.forEach((source, index) => {
            const tabId = `source-${payload.id}-${index}`;
            const navItem = document.createElement('li');
            navItem.className = 'nav-item';
            navItem.innerHTML = `<button class="nav-link${index === 0 ? ' active' : ''}" data-bs-toggle="tab" data-bs-target="#${tabId}" type="button" role="tab">${source}</button>`;
            tabs.appendChild(navItem);

            const pane = document.createElement('div');
            pane.className = `tab-pane fade${index === 0 ? ' show active' : ''}`;
            pane.id = tabId;
            pane.setAttribute('role', 'tabpanel');
            const entries = grouped[source].map((entry) => {
                const summary = (entry.summary || '').replace(/\n/g, '<br>');
                const fields = (entry.fields || []).map((field) => `<div><span class="fw-semibold">${field.label}:</span> ${field.value}</div>`).join('');
                const link = entry.link ? `<a href="${entry.link}" target="_blank" rel="noopener" class="small">Open source</a>` : '';
                return `<div class="source-card">
                            <div class="fw-semibold mb-1">${entry.title || 'Result'}</div>
                            <div class="text-muted small mb-2">${summary || 'No summary available.'}</div>
                            <div class="small mb-2">${fields}</div>
                            ${link}
                        </div>`;
            }).join('');
            pane.innerHTML = entries;
            tabContent.appendChild(pane);
        });
        resultDrawer.show();
    };

    const payloadById = {};
    initialData.forEach((item) => {
        payloadById[item.id] = item;
        upsertRow(item, {silent: true});
        addHistoryItem(item);
    });

    const syncHistoryTags = (payload) => {
        const historyItem = document.querySelector(`.history-item[data-query-id="${payload.id}"]`);
        if (!historyItem) {
            return;
        }
        const tagContainer = historyItem.querySelector('.history-tags');
        if (!payload.tags || !payload.tags.length) {
            if (tagContainer) {
                tagContainer.remove();
            }
            return;
        }
        if (!tagContainer) {
            const body = historyItem.querySelector('.history-body');
            const div = document.createElement('div');
            div.className = 'history-tags';
            body.appendChild(div);
            payload.tags.forEach((tag) => {
                const span = document.createElement('span');
                span.className = 'badge bg-dark-subtle text-dark-emphasis';
                span.textContent = tag;
                div.appendChild(span);
            });
            return;
        }
        tagContainer.innerHTML = '';
        payload.tags.forEach((tag) => {
            const span = document.createElement('span');
            span.className = 'badge bg-dark-subtle text-dark-emphasis';
            span.textContent = tag;
            tagContainer.appendChild(span);
        });
    };

    const ensureHistoryList = () => {
        if (historyList) {
            return historyList;
        }
        const emptyState = document.getElementById('history-empty-state');
        if (emptyState) {
            const wrapper = document.createElement('div');
            wrapper.id = 'history-list';
            wrapper.className = 'history-timeline';
            emptyState.replaceWith(wrapper);
            historyList = wrapper;
        }
        return historyList;
    };

    const addHistoryItem = (payload) => {
        const list = ensureHistoryList();
        if (!list) {
            return;
        }
        let article = list.querySelector(`.history-item[data-query-id="${payload.id}"]`);
        if (!article) {
            article = document.createElement('article');
            article.className = 'history-item';
            article.dataset.queryId = payload.id;
            article.innerHTML = `
                <div class="history-status"></div>
                <div class="history-body">
                    <div class="history-title"></div>
                    <div class="history-meta"></div>
                    <div class="history-tags"></div>
                </div>
                <div class="history-actions">
                    <button class="btn btn-link text-primary p-0 me-2 rerun-query" data-query-id="${payload.id}" title="Re-run query">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>
                    <button class="btn btn-link text-danger p-0 delete-query" data-query-id="${payload.id}" title="Delete conversation">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>`;
            list.prepend(article);
        }
        const statusNode = article.querySelector('.history-status');
        if (statusNode) {
            statusNode.innerHTML = statusBadge(payload.status);
        }
        const titleNode = article.querySelector('.history-title');
        if (titleNode) {
            titleNode.textContent = payload.text || '';
        }
        const metaNode = article.querySelector('.history-meta');
        if (metaNode) {
            metaNode.textContent = payload.created_at;
        }
        syncHistoryTags(payload);
    };

    const pollQuery = (queryId) => {
        if (pollers[queryId]) {
            clearInterval(pollers[queryId]);
        }
        const poller = setInterval(() => {
            fetch(`/queries/status/${queryId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }).then((response) => response.json())
              .then((data) => {
                  const existing = payloadById[data.id] || {};
                  payloadById[data.id] = {...existing, ...data};
                  upsertRow(payloadById[data.id]);
                  addHistoryItem(payloadById[data.id]);
                  syncHistoryTags(payloadById[data.id]);
                  if (['success', 'failed'].includes(data.status)) {
                      clearInterval(poller);
                      delete pollers[queryId];
                      if (processingModal) {
                          processingModal.hide();
                      }
                  }
              })
              .catch(() => {
                  clearInterval(poller);
                  delete pollers[queryId];
                  if (processingModal) {
                      processingModal.hide();
                  }
              });
        }, 2000);
        pollers[queryId] = poller;
    };

    document.getElementById('query-form').addEventListener('submit', (event) => {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const submittedText = formData.get('text') || (queryTextarea ? queryTextarea.value : '');
        if (pendingTemplateId) {
            formData.append('template_id', pendingTemplateId);
        }
        if (processingModal) {
            processingModal.show();
        }
        fetch('/queries/submit/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        }).then((response) => {
            if (!response.ok) {
                throw response;
            }
            return response.json();
        }).then((data) => {
            const now = new Date();
            const createdAt = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
            const payload = {
                id: data.query_id,
                text: submittedText,
                created_at: createdAt,
                status: 'pending',
                classification: '',
                resolution: '',
                results: [],
                error: null,
                progress: 5,
                stage: 'Queued',
                tags: [],
            };
            payloadById[data.query_id] = payload;
            upsertRow(payload, {silent: true});
            addHistoryItem(payload);
            form.reset();
            pendingTemplateId = null;
            pollQuery(data.query_id);
        }).catch(async (errorResponse) => {
            if (processingModal) {
                processingModal.hide();
            }
            let message = 'There was a problem submitting your query.';
            if (errorResponse.json) {
                try {
                    const details = await errorResponse.json();
                    if (details.errors) {
                        message = Object.values(details.errors).flat().join(' ');
                    }
                } catch (e) {
                    // ignore parsing errors
                }
            }
            alert(message);
        });
    });

    document.addEventListener('click', (event) => {
        const target = event.target.closest('button');
        if (!target) {
            return;
        }
        if (target.classList.contains('delete-query')) {
            event.preventDefault();
            const queryId = target.dataset.queryId;
            if (!confirm('Delete this conversation?')) {
                return;
            }
            fetch(`/queries/delete/${queryId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then((response) => response.json())
              .then(() => {
                  const item = document.querySelector(`[data-query-id="${queryId}"]`);
                  if (item) {
                      item.remove();
                  }
                  const row = table.row(`#query-${queryId}`);
                  if (row && row.length) {
                      row.remove().draw(false);
                  }
              });
            return;
        }
        if (target.classList.contains('rerun-query') || target.classList.contains('rerun-btn')) {
            event.preventDefault();
            const queryId = target.dataset.queryId;
            fetch(`/queries/rerun/${queryId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then((response) => response.json())
              .then((data) => {
                  pollQuery(data.query_id);
              });
            return;
        }
        if (target.classList.contains('inspect-btn')) {
            event.preventDefault();
            const queryId = target.dataset.queryId;
            const payload = payloadById[queryId];
            if (payload) {
                populateDrawer(payload);
            }
            return;
        }
        if (target.classList.contains('export-btn')) {
            event.preventDefault();
            const queryId = target.dataset.queryId;
            window.open(`/queries/export/${queryId}/`, '_blank');
            return;
        }
        if (target.id === 'save-template-btn') {
            event.preventDefault();
            const formData = new FormData(templateForm);
            const currentQuery = queryTextarea ? queryTextarea.value : '';
            if (!formData.get('text')) {
                formData.set('text', currentQuery);
            }
            fetch('/queries/templates/create/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            }).then((response) => {
                if (!response.ok) {
                    return response.json().then((payload) => Promise.reject(payload));
                }
                return response.json();
            }).then((data) => {
                templateModal?.hide();
                templateForm.reset();
                addOrUpdateTemplate(data);
            }).catch((error) => {
                alert(error.errors ? Object.values(error.errors).flat().join(' ') : 'Unable to save template.');
            });
            return;
        }
        if (target.classList.contains('delete-template')) {
            event.preventDefault();
            const templateId = target.dataset.templateId;
            fetch(`/queries/templates/${templateId}/delete/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then((response) => response.json())
              .then(() => {
                  const item = document.querySelector(`.template-item[data-template-id="${templateId}"]`);
                  if (item) {
                      item.remove();
                  }
              });
            return;
        }
        if (target.classList.contains('load-template')) {
            event.preventDefault();
            const templateId = target.dataset.templateId;
            const template = templateData.find((item) => String(item.id) === String(templateId));
            if (template && queryTextarea) {
                queryTextarea.value = template.text;
            }
            return;
        }
        if (target.classList.contains('run-template')) {
            event.preventDefault();
            const templateId = target.dataset.templateId;
            const template = templateData.find((item) => String(item.id) === String(templateId));
            if (template && queryTextarea) {
                queryTextarea.value = template.text;
                pendingTemplateId = templateId;
                document.getElementById('query-form').requestSubmit();
            }
            return;
        }
        if (target.id === 'save-tags-btn') {
            event.preventDefault();
            if (!drawerQueryId) {
                return;
            }
            const tagsInput = drawerElement.querySelector('#tags-input');
            const tags = tagsInput.value;
            fetch(`/queries/tags/${drawerQueryId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: new URLSearchParams({tags})
            }).then((response) => response.json())
              .then((data) => {
                  const payload = payloadById[drawerQueryId];
                  payload.tags = data.tags;
                  populateDrawer(payload);
                  syncHistoryTags(payload);
              });
            return;
        }
        if (target.id === 'drawer-export') {
            event.preventDefault();
            const queryId = target.dataset.queryId;
            window.open(`/queries/export/${queryId}/`, '_blank');
        }
    });

    const addOrUpdateTemplate = (payload) => {
        const existing = templateData.find((item) => item.id === payload.id);
        if (existing) {
            Object.assign(existing, payload);
        } else {
            templateData.push(payload);
        }
        const list = document.getElementById('template-list');
        if (!list) {
            return;
        }
        let item = list.querySelector(`.template-item[data-template-id="${payload.id}"]`);
        if (!item) {
            item = document.createElement('li');
            item.className = 'template-item d-flex align-items-start gap-3';
            item.dataset.templateId = payload.id;
            item.innerHTML = `<div class="icon-circle bg-info-subtle text-info"><i class="bi bi-journal-text"></i></div>
                <div class="flex-grow-1">
                    <div class="fw-semibold">${payload.name}</div>
                    <p class="text-muted small mb-1">${payload.text}</p>
                </div>
                <div class="d-flex flex-column align-items-end gap-1">
                    <button class="btn btn-sm btn-outline-primary load-template" data-template-id="${payload.id}"><i class="bi bi-upload"></i></button>
                    <button class="btn btn-sm btn-outline-success run-template" data-template-id="${payload.id}"><i class="bi bi-play"></i></button>
                    <button class="btn btn-sm btn-outline-danger delete-template" data-template-id="${payload.id}"><i class="bi bi-x"></i></button>
                </div>`;
            list.appendChild(item);
        } else {
            const title = item.querySelector('.fw-semibold');
            const summary = item.querySelector('p');
            if (title) {
                title.textContent = payload.name;
            }
            if (summary) {
                summary.textContent = payload.text;
            }
        }
    };

    document.getElementById('status-filter-success').addEventListener('click', (event) => {
        event.preventDefault();
        applyFilter('success');
    });
    document.getElementById('status-filter-running').addEventListener('click', (event) => {
        event.preventDefault();
        applyFilter('running');
    });
    document.getElementById('status-filter-clear').addEventListener('click', (event) => {
        event.preventDefault();
        applyFilter(null);
    });

    templateData.forEach((template) => addOrUpdateTemplate(template));

    refreshHealth();
    setInterval(refreshHealth, 60000);

    templateModalElement?.addEventListener('show.bs.modal', () => {
        if (queryTextarea) {
            const promptField = templateForm.querySelector('textarea');
            if (promptField) {
                promptField.value = queryTextarea.value;
            }
        }
    });
})();
