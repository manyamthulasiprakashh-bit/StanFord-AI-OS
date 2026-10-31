import { flushSync } from "react-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../api/client";
import { getHealth, type HealthResponse } from "../api/health";
import { getTasks, type Task, type TaskExecutionResult } from "../api/tasks";
import { executeTask } from "../api/tasks";
import { getTaskExecutions } from "../api/executionHistory";
import type { TaskHistoryState } from "../components/ExecutionHistory";
import { TaskCreateForm } from "../components/TaskCreateForm";
import { HealthStatus } from "../components/HealthStatus";
import { TaskList } from "../components/TaskList";

type HealthState =
  | { kind: "loading" }
  | { kind: "healthy"; health: HealthResponse }
  | { kind: "unavailable"; message: string };

type TaskState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; tasks: Task[] }
  | { kind: "error"; message: string };

type TaskExecutionState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "success"; result: TaskExecutionResult }
  | { status: "error"; message: string };

export default function DashboardPage() {
  const { user, token, logout } = useAuth();
  const [healthState, setHealthState] = useState<HealthState>({
    kind: "loading",
  });
  const [healthRetryCount, setHealthRetryCount] = useState(0);
  const [taskState, setTaskState] = useState<TaskState>({ kind: "idle" });
  const [taskRetryCount, setTaskRetryCount] = useState(0);
  const [executionStates, setExecutionStates] = useState<
    Record<string, TaskExecutionState>
  >({});
  const [historyStates, setHistoryStates] = useState<
    Record<string, TaskHistoryState>
  >({});
  const [openHistoryTaskId, setOpenHistoryTaskId] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    getHealth()
      .then((health) => {
        if (isActive) {
          setHealthState({ kind: "healthy", health });
        }
      })
      .catch((error: unknown) => {
        if (isActive) {
          const message =
            error instanceof Error ? error.message : "Backend is unavailable";
          setHealthState({ kind: "unavailable", message });
        }
      });

    return () => {
      isActive = false;
    };
  }, [healthRetryCount]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let isActive = true;

    getTasks(token)
      .then((tasks) => {
        if (isActive) {
          setTaskState({ kind: "loaded", tasks });
        }
      })
      .catch((error: unknown) => {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && error.status === 401) {
          logout();
          return;
        }

        const message =
          error instanceof Error ? error.message : "Unable to load tasks.";
        setTaskState({ kind: "error", message });
      });

    return () => {
      isActive = false;
    };
  }, [token, taskRetryCount, logout]);


  function retryHealthCheck() {
    setHealthState({ kind: "loading" });
    setHealthRetryCount((count) => count + 1);
  }

  function retryTaskList() {
    setTaskState({ kind: "loading" });
    setTaskRetryCount((count) => count + 1);
  }

  async function handleExecuteTask(taskId: string) {
    if (!token) {
      return;
    }

    setExecutionStates((state) => ({
      ...state,
      [taskId]: { status: "pending" },
    }));

    try {
      const result = await executeTask(token, taskId);
      setExecutionStates((state) => ({
        ...state,
        [taskId]: { status: "success", result },
      }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
        return;
      }

      let message = "Unable to execute task. Please try again.";
      if (error instanceof ApiError && error.status === 429) {
        message = "Too many requests. Please wait a little while before trying again.";
      } else if (error instanceof ApiError && error.status === 502) {
        message = "Unable to execute task. Please try again.";
      } else if (error instanceof ApiError && error.status === 500) {
        message = "Execution history could not be recorded.";
      } else if (error instanceof ApiError && error.detail) {
        message = error.detail;
      } else if (error instanceof Error) {
        message = error.message;
      }
      setExecutionStates((state) => ({
        ...state,
        [taskId]: { status: "error", message },
      }));
    }
  }

  function handleTaskCreated(task: Task) {
    setTaskState((state) => {
      if (state.kind === "loaded") {
        return { kind: "loaded", tasks: [task, ...state.tasks] };
      }
      return { kind: "loaded", tasks: [task] };
    });
  }

  function handleTaskCreationUnauthorized() {
    logout();
  }

  async function loadTaskHistory(taskId: string, force = false) {
    if (!token) {
      return;
    }

    const current = historyStates[taskId];
    if (!force && (current?.kind === "loading" || current?.kind === "loaded")) {
      return;
    }

    flushSync(() => {
      setHistoryStates((state) => ({
        ...state,
        [taskId]: { kind: "loading" },
      }));
    });

    try {
      const records = await getTaskExecutions(token, taskId);
      flushSync(() => {
        setHistoryStates((state) => ({
          ...state,
          [taskId]: { kind: "loaded", records },
        }));
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
        flushSync(() => {
          setHistoryStates((state) => ({
            ...state,
            [taskId]: { kind: "error", message: "Your session is no longer valid." },
          }));
        });
        return;
      }

      const message =
        error instanceof Error ? error.message : "Unable to load execution history.";
      flushSync(() => {
        setHistoryStates((state) => ({
          ...state,
          [taskId]: { kind: "error", message },
        }));
      });
    }
  }

  function handleViewHistory(taskId: string) {
    setOpenHistoryTaskId((current) => (current === taskId ? null : taskId));

    const current = historyStates[taskId];
    if (!current || current.kind === "idle" || current.kind === "error") {
      void loadTaskHistory(taskId);
    }
  }

  function retryTaskHistory(taskId: string) {
    setHistoryStates((state) => ({
      ...state,
      [taskId]: { kind: "loading" },
    }));
    void loadTaskHistory(taskId, true);
  }

  const tasks =
    taskState.kind === "loaded" ? taskState.tasks : null;
  const tasksLoading =
    taskState.kind === "loading" ||
    (token !== null && taskState.kind === "idle");
  const tasksError =
    taskState.kind === "error" ? taskState.message : null;

  return (
    <section className="card">
      <div className="dashboard-header">
        <h2>Dashboard</h2>
        <button type="button" onClick={logout}>
          Log out
        </button>
      </div>

      <h3>Current user</h3>
      <dl>
        <dt>Username</dt>
        <dd>{user?.username ?? "Unknown"}</dd>
        <dt>Account status</dt>
        <dd>{user?.is_active ? "Active" : "Inactive"}</dd>
      </dl>

      <h3>Backend health</h3>
      {healthState.kind === "loading" ? (
        <p>Checking backend health...</p>
      ) : null}

      {healthState.kind === "healthy" ? (
        <HealthStatus health={healthState.health} />
      ) : null}

      {healthState.kind === "unavailable" ? (
        <div>
          <p className="status-unavailable" role="alert">
            Backend unavailable: {healthState.message}
          </p>
          <button type="button" onClick={retryHealthCheck}>
            Retry health check
          </button>
        </div>
      ) : null}

      <h3>Tasks</h3>
      {token ? (
        <TaskCreateForm
          token={token}
          onTaskCreated={handleTaskCreated}
          onUnauthorized={handleTaskCreationUnauthorized}
        />
      ) : null}
      <TaskList
        tasks={tasks}
        isLoading={tasksLoading}
        errorMessage={tasksError}
        onRetry={retryTaskList}
        executionStates={executionStates}
        onExecute={handleExecuteTask}
        historyStates={historyStates}
        openHistoryTaskId={openHistoryTaskId}
        onViewHistory={handleViewHistory}
        onRetryHistory={retryTaskHistory}
      />
    </section>
  );
}
