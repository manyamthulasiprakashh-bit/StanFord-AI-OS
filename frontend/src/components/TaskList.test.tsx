import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TaskList } from "./TaskList";

describe("TaskList", () => {
  it("shows a loading state", () => {
    render(
      <TaskList tasks={null} isLoading errorMessage={null} onRetry={vi.fn()} />,
    );

    expect(screen.getByText(/loading tasks/i)).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(
      <TaskList tasks={[]} isLoading={false} errorMessage={null} onRetry={vi.fn()} />,
    );

    expect(screen.getByText(/no tasks found/i)).toBeInTheDocument();
  });

  it("shows an error state and retries", () => {
    const onRetry = vi.fn();
    render(
      <TaskList
        tasks={null}
        isLoading={false}
        errorMessage="Network down"
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText(/unable to load tasks: network down/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry task list/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders all task status labels", () => {
    render(
      <TaskList
        tasks={[
          {
            id: "1",
            title: "Pending task",
            description: null,
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "2",
            title: "In progress task",
            description: "Working",
            status: "in_progress",
            created_at: "2026-01-02T00:00:00Z",
            updated_at: "2026-01-02T00:00:00Z",
          },
          {
            id: "3",
            title: "Completed task",
            description: "Done",
            status: "completed",
            created_at: "2026-01-03T00:00:00Z",
            updated_at: "2026-01-03T00:00:00Z",
          },
          {
            id: "4",
            title: "Failed task",
            description: "Failed details",
            status: "failed",
            created_at: "2026-01-04T00:00:00Z",
            updated_at: "2026-01-04T00:00:00Z",
          },
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("No description")).toBeInTheDocument();
  });

  it("shows and hides task history", () => {
    const onViewHistory = vi.fn();
    render(
      <TaskList
        tasks={[
          {
            id: "task-1",
            title: "History task",
            description: "Details",
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        openHistoryTaskId="task-1"
        historyStates={{
          "task-1": {
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
          },
        }}
        onViewHistory={onViewHistory}
        onRetryHistory={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /hide history/i })).toBeInTheDocument();
    expect(screen.getByText(/execution history/i)).toBeInTheDocument();
    expect(screen.getByText(/provider: nvidia/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /hide history/i }));
    expect(onViewHistory).toHaveBeenCalledWith("task-1");
  });
});

  it("disables execution while a task is pending", () => {
    const onExecute = vi.fn();
    render(
      <TaskList
        tasks={[
          {
            id: "task-1",
            title: "Pending task",
            description: "Details",
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        executionStates={{
          "task-1": { status: "pending" },
        }}
        onExecute={onExecute}
      />,
    );

    const button = screen.getByRole("button", { name: /executing/i });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onExecute).not.toHaveBeenCalled();
  });

  it("keeps unrelated tasks executable", () => {
    const onExecute = vi.fn();
    render(
      <TaskList
        tasks={[
          {
            id: "task-1",
            title: "Pending task",
            description: "Details",
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "task-2",
            title: "Ready task",
            description: "Details",
            status: "pending",
            created_at: "2026-01-02T00:00:00Z",
            updated_at: "2026-01-02T00:00:00Z",
          },
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        executionStates={{
          "task-1": { status: "pending" },
        }}
        onExecute={onExecute}
      />,
    );

    const readyButton = screen.getByRole("button", { name: /execute task/i });
    expect(readyButton).not.toBeDisabled();
    fireEvent.click(readyButton);
    expect(onExecute).toHaveBeenCalledWith("task-2");
  });

  it("renders model output as text", () => {
    render(
      <TaskList
        tasks={[
          {
            id: "task-1",
            title: "Output task",
            description: "Details",
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        executionStates={{
          "task-1": {
            status: "success",
            result: {
              task_id: "task-1",
              output: "<script>alert('xss')</script>",
              provider: "nvidia",
              model: "meta/llama-3.3-70b-instruct",
              duration_ms: 1,
            },
          },
        }}
      />,
    );

    expect(screen.getByText("Result: <script>alert('xss')</script>")).toBeInTheDocument();
  });
