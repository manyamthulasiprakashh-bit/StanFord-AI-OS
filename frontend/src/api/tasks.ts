import { fetchJson } from "./client";

export type TaskStatus = "pending" | "in_progress" | "completed" | "failed";

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
}

export interface TaskCreateInput {
  title: string;
  description: string | null;
}

export async function getTasks(token: string): Promise<Task[]> {
  return fetchJson<Task[]>("/tasks", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function createTask(
  token: string,
  input: TaskCreateInput,
): Promise<Task> {
  return fetchJson<Task>("/tasks", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
}


export interface TaskExecutionResult {
  task_id: string;
  output: string;
  provider: string;
  model: string;
  duration_ms: number;
}

export async function executeTask(
  token: string,
  taskId: string,
): Promise<TaskExecutionResult> {
  return fetchJson<TaskExecutionResult>(`/tasks/${taskId}/execute`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
