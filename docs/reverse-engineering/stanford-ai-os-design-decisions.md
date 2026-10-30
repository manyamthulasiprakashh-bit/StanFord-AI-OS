# Stanford-AI OS Design Decisions (Phase 1)

## Verified observations about oc8 (source: `oc8/`)

- oc8 is a microkernel-style platform: a domain-neutral core plus a **capa** plugin system (`capas/`). Verified in `oc8/ARCHITECTURE.md` and `capas/README.md`.
- The core has no vendor-specific logic; connectors, skills, tool packs, runtimes, and channels are plugins. Verified in architecture docs and `backend/src/oc8/capas/`.
- Task execution is durable: `backend/src/oc8/runtime/intake.py::enqueue_run` commits an `AgentRun` row before publishing to Redis (`commit-before-enqueue`). Verified by code and `tests/runtime/test_intake.py`.
- Isolation uses PostgreSQL row-level security keyed on a transaction-local `app.tenant_id` GUC set by `tenant_session()`. Verified in `ARCHITECTURE.md` and `backend/src/oc8/db/session.py` (referenced).
- Tool calls go through a single MCP gateway, are authorized by a PDP, and can park runs for human approval. Verified in `ARCHITECTURE.md` and `backend/src/oc8/agent/engine.py`.
- Runtime execution is pluggable: in-process (`Oc8AgentRuntime`) or isolated Docker containers, selected via `runtime/registry.py::resolve_runtime`, with capability checks. Verified in `backend/src/oc8/runtime/registry.py` and `tests/runtime/test_registry.py`.
- Model routing is provider-neutral with fallback and classification guards. Verified in `backend/src/oc8/modelrouter/router.py` and `tests/modelrouter/`.
- oc8 core and frontend are licensed LGPL-3.0-or-later. Verified in `oc8/LICENSE` and `oc8/backend/pyproject.toml`.

## Stanford-AI OS design decisions

1. **Independent implementation.** Stanford-AI OS is being built as a new project. We study oc8's architecture and tests, but do not copy its source code. This respects the LGPL-3.0-or-later license and keeps Stanford-AI OS's own design and licensing under our control.

2. **Minimal first version.** Phase 1 implements only a FastAPI backend skeleton with a health endpoint, minimal settings, tests, and linting. This validates the toolchain and project layout before adding complexity.

3. **Agent engine deferred.** The agent execution loop (model calls, tool authorization, approvals) is deliberately not implemented in Phase 1. oc8's `agent/engine.py::run_agent` is large and depends on model routing, MCP tooling, memory, budgets, and approvals. We will implement a small equivalent only after the foundation and tests are stable.

4. **Durable queue deferred.** Redis Streams and consumer groups are powerful but add operational complexity. Stanford-AI OS will start with an in-process task service and define a queue interface so Redis (or another broker) can be added later without rewriting callers.

5. **Database integration deferred.** Phase 1 avoids PostgreSQL and migrations. We will introduce persistence (likely SQLite for local development, PostgreSQL for production) behind a repository interface in a later phase.

6. **Evolution path.** The foundation is structured so later phases can add:
   - Runtime adapters (in-process first, isolated containers later), inspired by oc8's `runtime/registry.py`.
   - Provider-neutral model routing, inspired by oc8's `modelrouter/`.
   - A small registry of explicitly permitted tools with authorization checks, inspired by oc8's PDP and MCP gateway.
   - Approval workflows with a single decision service, inspired by oc8's `approvals/service.py`.
   - Task history and status tracking, inspired by oc8's `AgentRun`/`Task` lifecycle and intake ordering.

7. **Business requirements are not yet verified.** Stanford.au's actual systems, workflows, and integration needs are unknown. This document records design intent only; no claim is made that Stanford.au's requirements have been verified. We will validate assumptions with stakeholders before implementing integrations.

## Open questions

- Which model providers Stanford.au will use (local vs. cloud) and under what data-classification constraints.
- Which business systems must be integrated first.
- Required approval thresholds and autonomy boundaries.
- Expected deployment environment and operational constraints.
- Whether Stanford-AI OS must be open-source or proprietary.

## Phase 2 task persistence decisions

### Verified observations about oc8

- oc8 tracks work through durable `AgentRun` and `Task` records. `runtime/intake.py::enqueue_run` commits the run before queueing, and the executor transitions run/task state. Verified in `oc8/backend/src/oc8/runtime/intake.py` and `oc8/backend/src/oc8/runtime/executor.py`.
- oc8 uses PostgreSQL with row-level security and Alembic migrations. Verified in `oc8/ARCHITECTURE.md` and `oc8/backend/migrations/`.
- oc8 separates API, runtime, and persistence concerns across modules. Verified in `oc8/ARCHITECTURE.md` (repo layout).

### Stanford-AI OS decisions

- A task represents a unit of requested work with a title, optional description, status, and timestamps. This is a simplified precursor to oc8's more complex run/task lifecycle.
- Task persistence is necessary so tasks survive process restarts and can be queried independently of the request that created them.
- SQLite is suitable for Phase 2 because it requires no external service, is transactional, and is easy to test with temporary files. It is a local-development choice, not a production commitment.
- The API, service, and database layers are separated: routes validate and serialize, services implement operations, and SQLAlchemy models/session helpers manage persistence.
- The design can later support PostgreSQL by changing `STANFORD_AI_OS_DATABASE_URL` and adjusting engine creation. The service and schema layers are intended to remain unchanged.
- UUIDs are stored as strings for SQLite compatibility. This is an implementation convenience that can be revisited for PostgreSQL-specific types later.
- Tests use temporary SQLite files, so they do not depend on a developer database.

## Phase 3 model provider decisions

### Verified observations about oc8

- oc8 routes model calls through a provider-neutral model router (`oc8/backend/src/oc8/modelrouter/router.py`) with provider adapters and shared request/response types (`oc8/backend/src/oc8/modelrouter/types.py`).
- oc8's router applies guards such as strict BYOK and classification checks before dispatch. Verified in `oc8/backend/src/oc8/modelrouter/router.py`.
- oc8's Ollama adapter uses `/api/chat` and supports tool calling. Verified in `oc8/backend/src/oc8/modelrouter/adapters/ollama.py`.

### Stanford-AI OS decisions

- A provider abstraction was introduced so model access has one consistent contract (`generate(request) -> response`) before any agent behavior is added.
- Ollama is the first implementation because it is local, requires no API key, and matches the available development environment.
- The implementation uses Ollama's simpler `/api/generate` endpoint with `prompt` and optional `system`, rather than oc8's `/api/chat` tool-calling flow. This keeps Phase 3 small and avoids tool-calling complexity.
- The provider layer is synchronous, using `httpx.Client` with an explicit timeout. This matches the current synchronous task persistence layer and avoids introducing async database changes.
- Configuration is validated with Pydantic Settings and protected namespaces are disabled to allow `model_*` field names.
- Errors are provider-neutral (`ProviderConnectionError`, `ProviderTimeoutError`, `ProviderResponseError`, `UnsupportedProviderError`) and do not expose prompts or secrets.
- No model-generation HTTP endpoint was added. Phase 3 focuses on the provider contract and tests; API integration can come later.
- No NVIDIA provider was implemented because no verified NVIDIA configuration or credential is present. The `ModelProvider` contract is designed so a future NVIDIA implementation can be added without changing Ollama.
- The provider does not access tasks or storage and does not execute generated text.

## Phase 3B NVIDIA provider decisions

### Verified observations about oc8

- oc8 uses provider-neutral model adapters and shared request/response types. Verified in `oc8/backend/src/oc8/modelrouter/router.py` and `oc8/backend/src/oc8/modelrouter/types.py`.
- oc8's Ollama adapter uses `/api/chat` and supports tool calling. Verified in `oc8/backend/src/oc8/modelrouter/adapters/ollama.py`.

### Stanford-AI OS decisions

- NVIDIA support was added as another implementation of the existing `ModelProvider` contract, without changing the Ollama provider.
- The NVIDIA provider uses the hosted OpenAI-compatible chat completions interface at `{base_url}/chat/completions`, with `Authorization: Bearer <api-key>`.
- The default base URL is `https://integrate.api.nvidia.com/v1` and the default model is `meta/llama-3.3-70b-instruct`. The model may need to be changed to one available to a specific account.
- The API key is stored as a Pydantic `SecretStr` and is never logged or included in error messages.
- Missing configuration fails during provider construction with `ProviderConfigurationError`; there is no silent fallback.
- HTTP authentication, rate-limit, timeout, connection, JSON, and response-shape errors are mapped to provider-neutral exceptions.
- No live NVIDIA request was verified in this environment because no API key or network access was available.

## Phase 4 task execution decisions

### Verified observations about oc8

- oc8 executes work through a durable run lifecycle, including queueing, runtime adapters, tool authorization, approvals, and task state transitions. Verified in `oc8/backend/src/oc8/runtime/executor.py` and `oc8/backend/src/oc8/agent/engine.py`.
- oc8's agent loop can call tools and suspend for human approval. Verified in `oc8/backend/src/oc8/agent/engine.py`.

### Stanford-AI OS decisions

- Phase 4 implements only a single-pass task execution service. It retrieves an existing task, sends its title and description to the configured model provider, and returns the generated result.
- Task status is intentionally not changed. Status changes and execution lifecycle management are deferred to a later phase.
- Execution results are not persisted. Persistence of runs and results is deferred until the execution model is better understood.
- Task content is treated as untrusted data. The system instruction explicitly tells the model not to follow instructions embedded in task content.
- Provider failures are translated into `TaskExecutionError` and returned as generic HTTP 502 responses. Internal details are not exposed.
- The service supports provider injection for deterministic tests while using the configured provider by default.
- No tools, shell execution, filesystem access, background workers, queues, retries, fallback, or multi-step loops were added.

## Phase 5 observability and evaluation decisions

### Verified observations about oc8

- oc8 includes metering, audit events, activity recording, and observability-related modules. Verified in `oc8/ARCHITECTURE.md` and repository layout (`backend/src/oc8/metering`, `backend/src/oc8/audit`, `backend/src/oc8/observability`).
- oc8 records tool calls and run outcomes as part of agent execution. Verified in `oc8/backend/src/oc8/agent/engine.py`.

### Stanford-AI OS decisions

- Phase 5 adds minimal observability without database tables or external monitoring services.
- Execution duration is measured with `time.perf_counter()` and returned in `TaskExecutionResult`.
- Observations are privacy-safe and contain only task ID, provider, model, duration, outcome, and error category.
- Prompts, full outputs, API keys, request headers, and raw exception messages are not logged.
- Provider failures are categorized by exception type, not by inspecting exception messages.
- An injected observer makes execution observability deterministic in tests.
- Observer callback failures are contained and cannot replace a successful result or conceal an original failure.
- `ExecutionMetrics` maintains bounded in-memory history for simple local observability.
- `evaluate_execution` provides deterministic checks for required substrings, forbidden substrings, and maximum output length.
- Evaluation is intentionally not a measurement of semantic model quality.
- No task status changes, tool execution, background workers, queues, or persistence were added.
