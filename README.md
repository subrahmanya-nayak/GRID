# GRID Biomedical Assistant Web UI

A modern Django 5 application that wraps the GRID biomedical knowledge agents with a user-friendly dashboard. The UI supports secure authentication, asynchronous query execution via Celery, and rich result exploration powered by DataTables.

## Features

- **Authentication flows** – Email-enabled signup, login, logout, and Django's built-in password reset templates so researchers can manage their own access.
- **Interactive query workspace** – Submit biomedical questions through a polished Bootstrap form that surfaces progress indicators and a modal spinner while Celery processes requests.
- **Results with DataTables** – View historical task outcomes in a responsive table enhanced by [DataTables](https://datatables.net/), including live status updates and formatted payloads.
- **Collapsible conversation history** – Quickly revisit or delete previous conversations from the accordion side panel without leaving the dashboard.
- **Celery task pipeline** – Each query is persisted to SQLite and dispatched to a Celery worker that orchestrates the underlying `DBFinder` routing logic, ensuring concurrent workloads across users.

## Project structure

```
webapp/
├── gridsite/              # Django project settings, URLs, Celery bootstrap
├── queries/               # Query submission, forms, tasks, and dashboard assets
└── templates/             # Shared base templates for authentication + layout
```

## Prerequisites

- Python 3.11+
- Redis 5+ (for the Celery broker/result backend)
- Ollama (to serve the `gemma2` model used by the router LLM)

These are provisioned automatically when you build the Docker image, but you can also install them manually for local development.

## Local development (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Start required services in separate terminals
redis-server
ollama serve  # ensure the gemma2 model is pulled: `ollama pull gemma2`

# Apply database migrations and create a superuser (optional)
python webapp/manage.py migrate
python webapp/manage.py createsuperuser

# Start Celery worker and Django development server
CELERY_BROKER_URL=redis://localhost:6379/0 \
CELERY_RESULT_BACKEND=redis://localhost:6379/0 \
celery -A gridsite worker --loglevel=info

# In another terminal
python webapp/manage.py runserver 0.0.0.0:8000
```

With the services running, open <http://localhost:8000> to access the dashboard.

## Running with Docker

```bash
docker build -t grid-webapp .
docker run -p 8000:8000 \
  -e CELERY_BROKER_URL=redis://localhost:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://localhost:6379/0 \
  grid-webapp
```

The container automatically:

1. Installs Python dependencies and the Ollama runtime.
2. Starts Redis for Celery message brokering.
3. Launches Ollama, Celery, applies Django migrations, and serves the web UI on port `8000`.

> **Note:** The bundled settings default `CELERY_TASK_ALWAYS_EAGER` to `False` so tasks run asynchronously. If you prefer synchronous execution (useful for quick demos), set `CELERY_TASK_ALWAYS_EAGER=true` when launching the server and worker.

## Verifying key UX flows

The following project files implement the requested functionality:

| Requirement | Implementation |
|-------------|----------------|
| Authentication (signup, login, logout, password reset) | Django auth URLs + custom signup view/templates in `webapp/queries/views.py`, `webapp/queries/forms.py`, and `webapp/queries/templates/registration/`. |
| Query submission with modal progress | Dashboard form + Bootstrap modal spinner in `webapp/queries/templates/queries/dashboard.html` and JavaScript handling in `webapp/queries/static/queries/js/dashboard.js`. |
| DataTables results display | Table markup in the dashboard template and initialization in the dashboard JavaScript. |
| Collapsible history with deletion | Accordion markup and delete endpoints in `dashboard.html`, with AJAX delete logic in `dashboard.js`. |
| Celery-backed concurrent processing | Task definition in `webapp/queries/tasks.py`, Celery app bootstrap in `webapp/gridsite/celery.py`, and async submission wiring in `views.py`. |

For a deeper dive into how results are normalized and persisted, review `webapp/queries/services.py` and `webapp/queries/models.py`.

## Running tests

The project currently relies on Django's built-in validation. You can run standard checks with:

```bash
python webapp/manage.py check
```

Add your own unit tests under `webapp/queries/tests/` as you expand the feature set.
