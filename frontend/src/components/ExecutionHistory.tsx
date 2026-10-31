import type { TaskExecutionHistory } from "../api/executionHistory";

export type TaskHistoryState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; records: TaskExecutionHistory[] }
  | { kind: "error"; message: string };

interface ExecutionHistoryProps {
  state?: TaskHistoryState;
  history?: TaskExecutionHistory[] | null;
  records?: TaskExecutionHistory[] | null;
  isLoading?: boolean;
  errorMessage?: string | null;
  error?: string | null;
  onRetry: () => void;
}

function normalizeState(props: ExecutionHistoryProps): TaskHistoryState {
  if (props.state) {
    return props.state;
  }

  if (props.isLoading) {
    return { kind: "loading" };
  }

  const message = props.errorMessage ?? props.error;
  if (message) {
    return { kind: "error", message };
  }

  const records = props.records ?? props.history;
  if (records === undefined) {
    return { kind: "idle" };
  }

  return { kind: "loaded", records: records ?? [] };
}

function formatTimestamp(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDuration(value: number | null): string {
  return value === null ? "Not available" : `${value} ms`;
}

function formatNullable(value: string | null): string {
  return value ?? "Not available";
}

function statusLabel(status: TaskExecutionHistory["status"]): string {
  if (status === "running") {
    return "Running";
  }
  if (status === "success") {
    return "Success";
  }
  return "Failure";
}

export function ExecutionHistory(props: ExecutionHistoryProps) {
  const { onRetry } = props;
  const state = normalizeState(props);

  if (state.kind === "loading") {
    return <p>Loading execution history...</p>;
  }

  if (state.kind === "error") {
    return (
      <div>
        <p className="status-unavailable" role="alert">
          Unable to load execution history: {state.message}
        </p>
        <button type="button" onClick={onRetry}>
          Retry history
        </button>
      </div>
    );
  }

  if (state.kind === "loaded" && state.records.length === 0) {
    return <p>No execution history found.</p>;
  }

  if (state.kind !== "loaded") {
    return null;
  }

  return (
    <div className="execution-history">
      <p>Execution history (attempt metadata only). Generated output is not persisted.</p>
      <ul className="execution-history-list">
        {state.records.map((record) => (
          <li key={record.id} className="execution-history-item">
            <p>Status: {statusLabel(record.status)}</p>
            <p>Provider: {formatNullable(record.provider)}</p>
            <p>Model: {formatNullable(record.model)}</p>
            <p>Duration: {formatDuration(record.duration_ms)}</p>
            <p>Created: {formatTimestamp(record.created_at)}</p>
            <p>Started: {formatTimestamp(record.started_at)}</p>
            <p>Completed: {formatTimestamp(record.completed_at)}</p>
            <p>Error category: {formatNullable(record.error_category)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
