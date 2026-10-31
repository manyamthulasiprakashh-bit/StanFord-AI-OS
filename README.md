# Stanford-AI OS

**A personal AI operating system built with Python, FastAPI, and configurable LLM providers.**

Stanford-AI OS is an ongoing project exploring how to build a reliable, modular AI
system that can manage tasks, interact with language models, and track execution
results. The project emphasizes clean backend architecture, persistence,
observability, testing, and reliable failure handling.

> **Project status:** Active development. The repository currently focuses on the
> backend foundation and core execution workflows.

## Key Features

- **REST API:** A FastAPI backend for interacting with the system.
- **Task management:** Create, retrieve, and manage tasks through API endpoints.
- **Persistent storage:** SQLAlchemy-based data persistence using SQLite.
- **Configurable model providers:** Provider abstraction supporting Ollama and
  NVIDIA integrations.
- **Task execution:** Execute tasks through the configured model provider.
- **Execution history:** Persist execution records and retrieve task-specific
  history and execution details.
- **Observability:** Capture execution status, timing, failure categories, and
  recovery state.
- **Deterministic evaluation:** Evaluate execution results using
  application-defined checks.
- **Failure recovery:** Handle interrupted executions and protect terminal
  execution states from unintended overwrites.
- **Automated testing:** Backend tests covering API behavior, persistence,
  provider integrations, execution workflows, and recovery logic.

## Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.12+ |
| API framework | FastAPI |
| Data validation and settings | Pydantic |
| Database | SQLite |
| ORM | SQLAlchemy |
| Language model integration | Ollama and NVIDIA API |
| Testing | pytest |
| Code quality | Ruff |
| API documentation | FastAPI / OpenAPI |

## Architecture Overview

The backend is organized around a few core responsibilities:

1. **API layer** — receives HTTP requests and returns responses.
2. **Task management** — handles task-related operations.
3. **Persistence layer** — stores tasks and execution records.
4. **Provider layer** — abstracts communication with supported language model
   providers.
5. **Execution layer** — coordinates single-pass task execution and records
   outcomes.
6. **Evaluation and recovery** — supports deterministic checks and handling of
   interrupted or failed executions.
7. **Test suite** — verifies important behaviors and helps prevent regressions.

This structure is intended to make the system easier to understand, test, and
extend as development continues.

## Repository Layout

```text
Stanford-AI OS/
├── backend/        # FastAPI application, services, database, and tests
├── docs/           # Project and reverse-engineering documentation
├── oc8/            # Local read-only reference repository (not version-controlled)
└── README.md
```

The `oc8/` directory is used only for architectural study. It is excluded from
version control and is not part of the Stanford-AI OS implementation.

## Getting Started

### Prerequisites

- Python 3.12 or a compatible Python version supported by the project
  dependencies.
- Git.
- An API client such as `curl`, Postman, or the interactive FastAPI
  documentation.
- For model execution, a configured and available supported provider.

### 1. Clone the repository

```bash
git clone https://github.com/manyamthulasiprakashh-bit/StanFord-AI-OS.git
cd StanFord-AI-OS
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install backend dependencies

```bash
cd backend
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The backend uses `pyproject.toml` for project metadata and development
dependencies.

### 4. Configure environment variables

Create a local `.env` file from `.env.example` if that example file is present:

```bash
cp .env.example .env
```

Configure the appropriate settings for the selected provider.

Typical settings include:

- Application environment and database URL.
- Model provider selection.
- Provider-specific model name and endpoint.
- Model request timeout.
- API credentials when required by the selected provider.

**Security:** Keep credentials in your local environment. Never commit `.env`
files, API keys, or other secrets to Git.

For Ollama, make sure the Ollama service is running and the configured model is
available. For NVIDIA-hosted models, configure a valid NVIDIA API key locally.
Live NVIDIA verification requires valid credentials and network access.

### 5. Start the backend

From the `backend` directory, run:

```bash
PYTHONPATH=src uvicorn stanford_ai_os.main:app --reload
```

Then open:

- **Health endpoint:** `http://127.0.0.1:8000/health`
- **Interactive API documentation:** `http://127.0.0.1:8000/docs`
- **Alternative API documentation:** `http://127.0.0.1:8000/redoc`

## Running Tests

Run tests from the backend directory with the project source on the Python path:

```bash
cd backend
PYTHONPATH=src pytest
```

Run the linter:

```bash
cd backend
ruff check .
```

These checks help verify backend behavior and maintain consistent code quality.

## Configuration and Providers

The provider abstraction separates application execution logic from
provider-specific communication.

The repository includes integrations for:

- **Ollama** — local model inference when a compatible local service and model
  are configured.
- **NVIDIA** — inference through a configured NVIDIA API endpoint and supported
  model.

Provider selection and credentials should be configured through environment
variables rather than hard-coded in the application.

External model calls require the relevant provider to be available and correctly
configured. The NVIDIA provider has been implemented, but live verification
requires a locally configured replacement API key.

## Reliability and Observability

Reliable execution is an important part of this project.

Current backend work includes:

- Persisting execution records.
- Tracking execution status and completion information.
- Recording execution duration and failure categories.
- Recovering interrupted executions without repeating the model request.
- Guarding execution state transitions to reduce the risk of overwriting
  completed results.
- Testing database integrity and important failure scenarios.

These mechanisms are intended to make execution behavior easier to inspect,
debug, and improve.

## Current Scope and Limitations

Stanford-AI OS is being developed incrementally.

The current focus is the backend foundation, task workflows, model-provider
integration, execution history, evaluation, and reliability.

The following should **not** be assumed to be complete unless implemented and
documented in a later version:

- A finished user-facing dashboard or frontend.
- A fully autonomous multi-agent system.
- Production deployment and production-grade operational infrastructure.
- Multi-user authorization and public-service authentication hardening beyond the initial single-user foundation.
- Retrieval-augmented generation or a complete long-term knowledge system.

The project roadmap may expand as these foundations mature.

## Development Roadmap

Future work will be guided by testing, usability, and architectural needs.
Potential areas for development include:

- Continuous integration with GitHub Actions.
- Expanded API and integration test coverage.
- Further improvements to execution reliability and evaluation.
- Additional AI capabilities as the backend foundation evolves.
- A user-facing interface when the backend workflows are ready.

Roadmap items are planned areas of work, not claims that the functionality is
already available.

## Contributing

This is a personal learning and engineering project. Suggestions, bug reports,
and technical feedback are welcome.

When proposing changes, focus on clear interfaces, reproducible tests, secure
configuration, and maintainable code.

## License

No license is specified here. Until a license is added to the repository, do not
assume that the project is available for unrestricted reuse or redistribution.
