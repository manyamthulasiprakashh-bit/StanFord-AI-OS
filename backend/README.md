# Stanford-AI OS Backend (Phase 2)

Stanford-AI OS is an AI-powered operating system for Stanford.au. This repository
contains an independent implementation inspired by architectural study of the
open-source oc8 project. The `oc8/` directory is a read-only reference and is
not part of this backend.

## Current scope

Phase 2 adds a small persistent task management system:

- FastAPI application
- Health endpoint
- Task create/list/get API
- SQLite persistence
- Pydantic request/response schemas
- Service layer separate from routes
- pytest suite and Ruff configuration

Deliberately excluded: AI agent loops, LLM integration, Redis, background
workers, authentication, multi-tenancy, PostgreSQL, frontend dashboards, and
production deployment.

## Architecture

```text
API routes (api/tasks.py)
  -> Task service (services/task_service.py)
  -> SQLAlchemy ORM model (db/models.py)
  -> SQLite database
```

- Routes validate input and serialize responses.
- The service layer owns task operations.
- Database access is isolated in `db/session.py` and `db/models.py`.
- A shared SQLAlchemy engine is reused across requests; sessions remain request-scoped.
- Tables are created safely with `checkfirst=True`; existing data is not
  deleted on startup.

## Configuration

Settings use the `STANFORD_AI_OS_` environment variable prefix.

| Setting | Default | Description |
| --- | --- | --- |
| `STANFORD_AI_OS_APP_NAME` | `Stanford-AI OS` | Application name |
| `STANFORD_AI_OS_ENVIRONMENT` | `development` | Runtime environment |
| `STANFORD_AI_OS_DATABASE_URL` | `sqlite:///./stanford_ai_os.db` | Database URL |

The default SQLite database is created in the current working directory, outside
the Python source package. Use an absolute path or environment variable for a
different location.

## Installation

Use Python 3.12+.

```bash
cd backend
python -m pip install -e ".[dev]"
```

## Run tests

```bash
cd backend
pytest
```

## Lint

```bash
cd backend
ruff check .
```

## Start the server

```bash
cd backend
uvicorn stanford_ai_os.main:app --reload
```

Then open http://127.0.0.1:8000/health.

## API examples

Create a task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title": "First task", "description": "Example"}'
```

List tasks:

```bash
curl http://127.0.0.1:8000/tasks
```

Retrieve one task:

```bash
curl http://127.0.0.1:8000/tasks/<task-id>
```

Interactive API documentation is available at http://127.0.0.1:8000/docs.

## Model provider abstraction (Phase 3)

Stanford-AI OS can generate text through a provider-neutral interface.

Current provider:
- `ollama`: calls Ollama's local `/api/generate` endpoint.

Configuration:

```bash
export STANFORD_AI_OS_MODEL_PROVIDER=ollama
export STANFORD_AI_OS_OLLAMA_BASE_URL=http://localhost:11434
export STANFORD_AI_OS_OLLAMA_MODEL=qwen3:4b
export STANFORD_AI_OS_MODEL_TIMEOUT_SECONDS=60
```

The default model name is only a default. It is not assumed to be installed.

Provider tests are mocked and do not require a running Ollama server, installed
model, API key, or internet access.

To verify a real local setup after starting Ollama separately:

```bash
ollama serve
ollama pull qwen3:4b
```

Then use the provider from Python:

```python
from stanford_ai_os.config import get_settings
from stanford_ai_os.modelrouter.router import get_model_router
from stanford_ai_os.modelrouter.types import ModelRequest

settings = get_settings()
provider = get_model_router(settings).get_provider()
response = provider.generate(ModelRequest(prompt="Hello"))
print(response.text)
```

Limitations:
- No agent reasoning loop.
- No automatic model fallback.
- No tool execution.
- No OpenAI, NVIDIA, or other providers yet, although the interface supports adding them.

## NVIDIA provider (Phase 3B)

Stanford-AI OS can also use NVIDIA's OpenAI-compatible hosted chat completions
API.

Configuration:

```bash
export STANFORD_AI_OS_MODEL_PROVIDER=nvidia
export STANFORD_AI_OS_NVIDIA_API_KEY=your-api-key
export STANFORD_AI_OS_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
export STANFORD_AI_OS_NVIDIA_MODEL=meta/llama-3.3-70b-instruct
```

The API key must be provided through the environment or a local `.env` file.
Never commit `.env` or a real API key. `.env.example` contains placeholders only.

The implementation uses:
- Endpoint: `{NVIDIA_BASE_URL}/chat/completions`
- Header: `Authorization: Bearer <api-key>`
- Request body: OpenAI-compatible `messages` payload

The default model name is only a default and may need to be changed to a model
available to your NVIDIA account.

Live verification requires a valid API key and network access. Automated tests
use mocked HTTP responses and do not require credentials.

## Task execution (Phase 4)

Stanford-AI OS can execute a single task through the configured model provider.

Endpoint:

```bash
curl -X POST http://127.0.0.1:8000/tasks/<task-id>/execute
```

Response:

```json
{
  "task_id": "...",
  "output": "...",
  "provider": "...",
  "model": "..."
}
```

Behavior:
- The task must already exist.
- The task title and description are sent to the configured model provider.
- The configured provider is selected from application settings.
- One model call is made per request.
- Execution results are not persisted.
- Task status is not changed.
- No tools, shell commands, filesystem access, or multi-step agent behavior are supported.

## SQLite on a Render Persistent Disk

Stanford-AI OS can use SQLite on a Render persistent disk for a small,
single-instance deployment. This is documentation only; no code changes are
required.

Set the database URL to an absolute path under the disk's mount point:

```bash
STANFORD_AI_OS_DATABASE_URL=sqlite:////var/data/stanford_ai_os.db
```

Important:

- `/var/data` is a **placeholder**. It must match the mount path configured for
  the actual Render disk. The database file must reside on persistent storage;
  Render's ephemeral filesystem is not suitable because data is lost on
  restart or redeploy.
- This setup assumes a **single instance and a single worker**. SQLite is not
  appropriate for multi-instance or high-concurrency deployments.
- Local development continues to use the existing default
  (`sqlite:///./stanford_ai_os.db`) unless this environment variable is
  overridden.
- The project does not currently include a database migration framework.
  `create_all()` creates missing tables but does not alter existing schemas.
  Schema changes require manual handling.
- Backup and restore cautions:
  - Stop the service before copying the database file.
  - Copy the complete `.db` file (and any `-wal`/`-shm` files if present).
  - Avoid copying while writes are in progress to prevent a partial backup.

## Deployment (Render)

For a Render web service:

- Root directory: `backend`
- Build command: `pip install -e .`
- Start command: `PYTHONPATH=src uvicorn stanford_ai_os.main:app --host 0.0.0.0 --port $PORT`
- Python version: set via `runtime.txt` (`python-3.12.7`)

Required environment variables (names only):

- `STANFORD_AI_OS_SECRET_KEY` (at least 32 characters)
- `STANFORD_AI_OS_ADMIN_PASSWORD`
- `STANFORD_AI_OS_DATABASE_URL`
- `STANFORD_AI_OS_MODEL_PROVIDER`
- `STANFORD_AI_OS_CORS_ALLOWED_ORIGINS` (comma-separated explicit origins)

Optional:

- `STANFORD_AI_OS_ADMIN_USERNAME`
- `STANFORD_AI_OS_ACCESS_TOKEN_EXPIRE_MINUTES`
- `STANFORD_AI_OS_LOG_LEVEL`
- `STANFORD_AI_OS_LOGIN_RATE_LIMIT_ATTEMPTS`
- `STANFORD_AI_OS_LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `STANFORD_AI_OS_EXECUTION_RATE_LIMIT_ATTEMPTS`
- `STANFORD_AI_OS_EXECUTION_RATE_LIMIT_WINDOW_SECONDS`
- Provider-specific settings (Ollama/NVIDIA).

CORS is disabled unless `STANFORD_AI_OS_CORS_ALLOWED_ORIGINS` is set to explicit origins.

## Execution rate limiting

Execution requests are protected by a configurable, in-memory sliding-window rate
limiter. The limit is applied after authentication and before task execution,
provider resolution, or execution-history creation.

Configuration:

```bash
STANFORD_AI_OS_EXECUTION_RATE_LIMIT_ATTEMPTS=10
STANFORD_AI_OS_EXECUTION_RATE_LIMIT_WINDOW_SECONDS=60
```

Both values must be positive integers. When the configured threshold is exceeded,
the endpoint returns HTTP 429:

```json
{"detail": "Too many execution requests"}
```

A rejected request does not call a model provider, create or modify an
execution-history record, or change task status.

Limitations:
- The limiter is in-memory and process-local.
- Counters reset when the application restarts.
- Limits are not shared across multiple workers or application instances.
- This is a development-stage limiter, not a distributed quota-control system.

## Application logging (Phase 7)

Stanford-AI OS emits structured JSON log records using Python's standard library.

Configuration:

```bash
STANFORD_AI_OS_LOG_LEVEL=INFO
```

Valid levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Invalid values
default to `INFO`.

Each log record is a single JSON object with these required fields:

- `timestamp`: ISO-8601 UTC timestamp.
- `level`: log level.
- `event`: stable, machine-readable event name.
- `request_id`: request correlation ID when available, otherwise `null`.

Additional allowlisted fields may appear depending on the event:

- `task_id`
- `execution_id`
- `provider`
- `model`
- `duration_ms`
- `outcome`
- `error_category`
- `status_code`

Event categories include:

- Authentication: `authentication_not_configured`, `login_rate_limited`,
  `login_failed`, `login_succeeded`, `invalid_access_token`.
- Execution: `execution_started`, `execution_succeeded`, `execution_failed`,
  `execution_rate_limited`, `execution_observer_failed`.
- Execution history: `execution_history_create_failed`,
  `execution_history_metadata_not_persisted`,
  `execution_history_metadata_update_failed`,
  `execution_history_persist_failed`, `execution_history_update_failed`.
- Recovery: `execution_recovered`.

Request-ID behavior:

- Each incoming request receives a new UUID request ID.
- The ID is included in application log records emitted while processing that
  request.
- The ID is returned in the `X-Request-ID` response header, including unexpected server errors.
- Client-provided request IDs are not trusted.

Prohibited log content:

- Passwords and password hashes.
- JWTs and signing secrets.
- API keys and provider credentials.
- Authorization headers.
- Task descriptions and prompts.
- Model outputs.
- Raw exception messages.
- Full request/response bodies.
- Database URLs and connection strings.

Limitations:

- Logs are not a durable audit trail and are not retained after process exit.
- The in-memory rate limiter remains process-local and is not shared across
  workers or instances.
- Logging does not provide compliance-grade audit retention.

## Execution observability and evaluation (Phase 5)

Execution responses now include:

```json
{
  "task_id": "...",
  "output": "...",
  "provider": "...",
  "model": "...",
  "duration_ms": 12
}
```

Observability behavior:
- Each execution attempt records a privacy-safe observation.
- Observations include task ID, provider, model, duration, outcome, and error category.
- Prompts, full outputs, API keys, request headers, and raw exception messages are not logged.
- Failed observer callbacks cannot replace a successful result or conceal an original failure.
- In-memory metrics history is bounded when `ExecutionMetrics` is used.

Deterministic evaluation helper:

```python
from stanford_ai_os.schemas.task_execution import TaskExecutionResult
from stanford_ai_os.services.task_evaluation import (
    ExecutionExpectation,
    evaluate_execution,
)

result = TaskExecutionResult(
    task_id=task_id,
    output="generated text",
    provider="fake",
    model="fake-model",
    duration_ms=1,
)
expectation = ExecutionExpectation(
    required_substrings=("generated",),
    forbidden_substrings=("secret",),
    max_output_chars=100,
)
evaluation = evaluate_execution(result, expectation)
```

This helper checks output properties only. It does not call a model provider and does not measure semantic quality.

## Authentication (Phase 7)

Stanford-AI OS includes a minimal single-user authentication foundation.

### Required environment variables

```bash
STANFORD_AI_OS_SECRET_KEY=replace-with-a-strong-secret-at-least-32-characters
STANFORD_AI_OS_ADMIN_USERNAME=admin
STANFORD_AI_OS_ADMIN_PASSWORD=replace-with-a-strong-password
STANFORD_AI_OS_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

The signing secret must be at least 32 characters. The admin password is used only
to bootstrap the initial user and is stored as an Argon2 hash.

### Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "your-password"}'
```

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

### Use a protected endpoint

```bash
curl http://127.0.0.1:8000/tasks \
  -H 'Authorization: Bearer <access_token>'
```

### Current limitations

- Single-user design.
- No refresh tokens.
- No role-based authorization.
- No password reset flow.
- No rate limiting yet.
- HTTPS is required for non-local deployments.

## Authentication (Phase 7)

Stanford-AI OS includes a minimal single-user authentication foundation.

### Required environment variables

```bash
STANFORD_AI_OS_SECRET_KEY=replace-with-a-strong-secret-at-least-32-characters
STANFORD_AI_OS_ADMIN_USERNAME=admin
STANFORD_AI_OS_ADMIN_PASSWORD=replace-with-a-strong-password
STANFORD_AI_OS_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

The signing secret must be at least 32 characters. The admin password is used
only to bootstrap the initial user and is stored as an Argon2 hash.

### Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "your-password"}'
```

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

### Use a protected endpoint

```bash
curl http://127.0.0.1:8000/tasks \
  -H 'Authorization: Bearer <access_token>'
```

### Current limitations

- Single-user design.
- No refresh tokens.
- No role-based authorization.
- No password reset flow.
- No rate limiting yet.
- HTTPS is required for non-local deployments.
