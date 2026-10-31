import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExecutionHistory } from "./ExecutionHistory";

describe("ExecutionHistory", () => {
  it("shows a loading state", () => {
    render(<ExecutionHistory state={{ kind: "loading" }} onRetry={vi.fn()} />);

    expect(screen.getByText(/loading execution history/i)).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(
      <ExecutionHistory
        state={{ kind: "loaded", records: [] }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/no execution history found/i)).toBeInTheDocument();
  });

  it("renders persisted metadata", () => {
    render(
      <ExecutionHistory
        state={{
          kind: "loaded",
          records: [
            {
              id: "execution-1",
              task_id: "task-1",
              status: "success",
              provider: "nvidia",
              model: "meta/llama-3.3-70b-instruct",
              duration_ms: 42,
              error_category: null,
              created_at: "2026-01-01T00:00:00Z",
              started_at: "2026-01-01T00:00:01Z",
              completed_at: "2026-01-01T00:00:02Z",
            },
          ],
        }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/status: success/i)).toBeInTheDocument();
    expect(screen.getByText(/provider: nvidia/i)).toBeInTheDocument();
    expect(screen.getByText(/model: meta\/llama-3.3-70b-instruct/i)).toBeInTheDocument();
    expect(screen.getByText(/duration: 42 ms/i)).toBeInTheDocument();
    expect(screen.getByText(/error category: not available/i)).toBeInTheDocument();
  });

  it("renders null values safely", () => {
    render(
      <ExecutionHistory
        state={{
          kind: "loaded",
          records: [
            {
              id: "execution-2",
              task_id: "task-1",
              status: "running",
              provider: null,
              model: null,
              duration_ms: null,
              error_category: null,
              created_at: "2026-01-01T00:00:00Z",
              started_at: null,
              completed_at: null,
            },
          ],
        }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByText(/not available/i).length).toBeGreaterThan(0);
  });

  it("renders a safe error category", () => {
    render(
      <ExecutionHistory
        state={{
          kind: "loaded",
          records: [
            {
              id: "execution-3",
              task_id: "task-1",
              status: "failure",
              provider: "nvidia",
              model: "meta/llama-3.3-70b-instruct",
              duration_ms: 7,
              error_category: "timeout",
              created_at: "2026-01-01T00:00:00Z",
              started_at: "2026-01-01T00:00:01Z",
              completed_at: "2026-01-01T00:00:02Z",
            },
          ],
        }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/error category: timeout/i)).toBeInTheDocument();
  });

  it("shows an error state and retries", () => {
    const onRetry = vi.fn();
    render(
      <ExecutionHistory
        state={{ kind: "error", message: "Network down" }}
        onRetry={onRetry}
      />,
    );

    expect(
      screen.getByText(/unable to load execution history: network down/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry history/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("supports individual loading props", () => {
    render(<ExecutionHistory isLoading onRetry={vi.fn()} />);

    expect(screen.getByText(/loading execution history/i)).toBeInTheDocument();
  });
});
