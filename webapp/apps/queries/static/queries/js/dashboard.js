(function () {
    const modalElement = document.getElementById('processingModal');
    const processingModal = modalElement ? new bootstrap.Modal(modalElement, {backdrop: 'static', keyboard: false}) : null;
    const initialDataElement = document.getElementById('initial-data');
    const initialData = initialDataElement ? JSON.parse(initialDataElement.textContent || '[]') : [];

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

    const renderResults = (payload) => {
        if (payload.error) {
            return `<span class="text-danger">${payload.error}</span>`;
        }
        const resultRows = payload.results;
        if (!resultRows || !resultRows.length) {
            return '<span class="text-muted">No data yet.</span>';
        }
        return resultRows.map((row) => {
            const content = (row.content || '').replace(/\n/g, '<br>');
            return `<div class="mb-3">
                        <div class="fw-semibold">${row.source || 'Result'}</div>
                        <div class="small text-muted">${content}</div>
                    </div>`;
        }).join('');
    };

    const table = $('#results-table').DataTable({
        responsive: true,
        order: [[0, 'desc']],
        columnDefs: [
            {targets: [3], orderable: false}
        ]
    });

    const upsertRow = (payload) => {
        const rowSelector = `#query-${payload.id}`;
        const existingRow = table.row(rowSelector);
        const rowData = [
            payload.created_at,
            statusBadge(payload.status),
            payload.classification || '<span class="text-muted">—</span>',
            renderResults(payload)
        ];
        if (existingRow && existingRow.length) {
            existingRow.data(rowData).draw(false);
        } else {
            const node = table.row.add(rowData).draw(false).node();
            if (node) {
                node.id = rowSelector.replace('#', '');
            }
        }
    };

    initialData.forEach((item) => upsertRow(item));

    const csrftoken = document.querySelector('#query-form [name=csrfmiddlewaretoken]').value;

    const pollQuery = (queryId) => {
        const poller = setInterval(() => {
            fetch(`/queries/status/${queryId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }).then((response) => response.json())
              .then((data) => {
                  upsertRow(data);
                  if (['success', 'failed'].includes(data.status)) {
                      clearInterval(poller);
                      if (processingModal) {
                          processingModal.hide();
                      }
                  }
              })
              .catch(() => {
                  clearInterval(poller);
                  if (processingModal) {
                      processingModal.hide();
                  }
              });
        }, 2000);
    };

    document.getElementById('query-form').addEventListener('submit', (event) => {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
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
            form.reset();
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
                    // ignore
                }
            }
            alert(message);
        });
    });

    document.querySelectorAll('.delete-query').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            const queryId = button.getAttribute('data-query-id');
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
        });
    });
})();
