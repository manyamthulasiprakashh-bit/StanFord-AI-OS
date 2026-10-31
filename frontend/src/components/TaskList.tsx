import type { Task, TaskExecutionResult } from "../api/tasks";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { ExecutionHistory, type TaskHistoryState } from "./ExecutionHistory";

export type TaskExecutionState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "success"; result: TaskExecutionResult }
  | { status: "error"; message: string };

interface TaskListProps {
  tasks: Task[] | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRetry: () => void;
  executionStates?: Record<string, TaskExecutionState>;
  onExecute?: (taskId: string) => void;
  historyStates?: Record<string, TaskHistoryState>;
  openHistoryTaskId?: string | null;
  onViewHistory?: (taskId: string) => void;
  onRetryHistory?: (taskId: string) => void;
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function TaskList({
  tasks,
  isLoading,
  errorMessage,
  onRetry,
  executionStates = {},
  onExecute,
  historyStates = {},
  openHistoryTaskId = null,
  onViewHistory,
  onRetryHistory,
}: TaskListProps) {
  if (isLoading) {
    return <p>Loading tasks...</p>;
  }

  if (errorMessage) {
    return (
      <div>
        <p className="status-unavailable" role="alert">Unable to load tasks: {errorMessage}</p>
        <button type="button" onClick={onRetry}>
          Retry task list
        </button>
      </div>
    );
  }

  if (tasks === null || tasks.length === 0) {
    return <p>No tasks found.</p>;
  }

  return (
    <ul className="task-list">
      {tasks.map((task) => {
        const executionState = executionStates[task.id] ?? { status: "idle" };
        const isHistoryOpen = openHistoryTaskId === task.id;

        return (
          <li key={task.id} className="task-list-item">
            <div className="task-list-header">
              <h4>{task.title}</h4>
              <TaskStatusBadge status={task.status} />
            </div>
            <p>{task.description ?? "No description"}</p>
            <p>Created: {formatTimestamp(task.created_at)}</p>

            <div className="task-actions">
              <button
                type="button"
                disabled={executionState.status === "pending"}
                onClick={() => onExecute?.(task.id)}
              >
                {executionState.status === "pending"
                  ? "Executing..."
                  : "Execute task"}
              </button>

              <button
                type="button"
                onClick={() => onViewHistory?.(task.id)}
              >
                {isHistoryOpen ? "Hide history" : "View history"}
              </button>
            </div>

            {executionState.status === "success" ? (
              <div className="task-execution-result">
                <p>Result: {executionState.result.output}</p>
                <p>
                  Provider: {executionState.result.provider} | Model:{" "}
                  {executionState.result.model} | Duration:{" "}
                  {executionState.result.duration_ms} ms
                </p>
              </div>
            ) : null}

            {executionState.status === "error" ? (
              <p className="status-unavailable" role="alert">
                {executionState.message}
              </p>
            ) : null}

            {isHistoryOpen ? (
              <ExecutionHistory
                state={historyStates[task.id]}
                onRetry={() => onRetryHistory?.(task.id)}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
