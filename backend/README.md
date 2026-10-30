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
