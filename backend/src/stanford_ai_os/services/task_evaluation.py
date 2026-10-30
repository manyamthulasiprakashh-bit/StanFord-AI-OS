"""Deterministic evaluation helpers for task execution results."""

from pydantic import BaseModel, ConfigDict, model_validator

from stanford_ai_os.schemas.task_execution import TaskExecutionResult


class ExecutionExpectation(BaseModel):
    """Deterministic properties expected from an execution result."""

    model_config = ConfigDict(frozen=True)

    required_substrings: tuple[str, ...] = ()
    forbidden_substrings: tuple[str, ...] = ()
    max_output_chars: int | None = None

    @model_validator(mode="after")
    def validate_max_output_chars(self) -> "ExecutionExpectation":
        if self.max_output_chars is not None and self.max_output_chars < 0:
            raise ValueError("max_output_chars must be non-negative")
        return self


class EvaluationResult(BaseModel):
    """Result of a deterministic execution evaluation."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    failures: tuple[str, ...] = ()


def evaluate_execution(
    result: TaskExecutionResult, expectation: ExecutionExpectation
) -> EvaluationResult:
    """Evaluate deterministic properties of an execution result.

    This helper checks output properties only. It does not call a model provider
    and does not measure semantic quality.
    """

    failures: list[str] = []

    for substring in expectation.required_substrings:
        if substring not in result.output:
            failures.append(f"Missing required substring: {substring!r}")

    for substring in expectation.forbidden_substrings:
        if substring in result.output:
            failures.append(f"Forbidden substring present: {substring!r}")

    if (
        expectation.max_output_chars is not None
        and len(result.output) > expectation.max_output_chars
    ):
        failures.append(
            f"Output exceeds maximum length of {expectation.max_output_chars} characters"
        )

    return EvaluationResult(passed=not failures, failures=tuple(failures))
