import { fetchJson } from "./client";

export interface TaskExecutionHistory {
  id: string;
  task_id: string;
  status: "running" | "success" | "failure";
  provider: string | null;
  model: string | null;
  duration_ms: number | null;
  error_category: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export async function getTaskExecutions(
  token: string,
  taskId: string,
  limit = 20,
  offset = 0,
): Promise<TaskExecutionHistory[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return fetchJson<TaskExecutionHistory[]>(
    `/tasks/${encodeURIComponent(taskId)}/executions?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}

export async function getExecution(
  token: string,
  executionId: string,
): Promise<TaskExecutionHistory> {
  return fetchJson<TaskExecutionHistory>(
    `/executions/${encodeURIComponent(executionId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}
