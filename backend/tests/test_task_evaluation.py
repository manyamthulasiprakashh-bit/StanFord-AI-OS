"""Tests for deterministic task execution evaluation."""

import pytest

from stanford_ai_os.schemas.task_execution import TaskExecutionResult
from stanford_ai_os.services.task_evaluation import (
    EvaluationResult,
    ExecutionExpectation,
    evaluate_execution,
)


def _result(output: str) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=__import__("uuid").uuid4(),
        output=output,
        provider="fake",
        model="fake-model",
        duration_ms=1,
    )


def test_required_substrings_present() -> None:
    result = _result("alpha beta")
    expectation = ExecutionExpectation(required_substrings=("alpha", "beta"))

    evaluation = evaluate_execution(result, expectation)

    assert evaluation.passed is True
    assert evaluation.failures == ()


def test_required_substring_missing() -> None:
    result = _result("alpha")
    expectation = ExecutionExpectation(required_substrings=("beta",))

    evaluation = evaluate_execution(result, expectation)

    assert evaluation.passed is False
    assert evaluation.failures == ("Missing required substring: 'beta'",)


def test_forbidden_substring_present() -> None:
    result = _result("alpha secret")
    expectation = ExecutionExpectation(forbidden_substrings=("secret",))

    evaluation = evaluate_execution(result, expectation)

    assert evaluation.passed is False
    assert evaluation.failures == ("Forbidden substring present: 'secret'",)


def test_maximum_output_length_satisfied() -> None:
    result = _result("short")
    expectation = ExecutionExpectation(max_output_chars=10)

    evaluation = evaluate_execution(result, expectation)

    assert evaluation.passed is True


def test_maximum_output_length_exceeded() -> None:
    result = _result("this is too long")
    expectation = ExecutionExpectation(max_output_chars=5)

    evaluation = evaluate_execution(result, expectation)

    assert evaluation.passed is False
    assert evaluation.failures == ("Output exceeds maximum length of 5 characters",)


def test_empty_expectations_pass() -> None:
    result = _result("anything")

    evaluation = evaluate_execution(result, ExecutionExpectation())

    assert evaluation.passed is True
    assert evaluation.failures == ()


def test_invalid_expectation_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutionExpectation(max_output_chars=-1)


def test_evaluation_requires_no_network_or_provider() -> None:
    result = _result("deterministic")
    expectation = ExecutionExpectation(required_substrings=("deterministic",))

    evaluation = evaluate_execution(result, expectation)

    assert isinstance(evaluation, EvaluationResult)
    assert evaluation.passed is True
