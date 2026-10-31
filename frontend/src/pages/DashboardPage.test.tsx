import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../auth/useAuth";
import DashboardPage from "./DashboardPage";
import { getHealth } from "../api/health";
import { ApiError } from "../api/client";
import { getTasks, createTask, executeTask } from "../api/tasks";
import { getTaskExecutions } from "../api/executionHistory";

vi.mock("../auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/health", () => ({
  getHealth: vi.fn(),
}));

vi.mock("../api/tasks", () => ({
  getTasks: vi.fn(),
  createTask: vi.fn(),
  executeTask: vi.fn(),
}));

vi.mock("../api/executionHistory", () => ({
  getTaskExecutions: vi.fn(),
}));

vi.mock("../api/executionHistory", () => ({
  getTaskExecutions: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedGetHealth = vi.mocked(getHealth);
const mockedGetTasks = vi.mocked(getTasks);
const mockedCreateTask = vi.mocked(createTask);
const mockedExecuteTask = vi.mocked(executeTask);
const mockedGetTaskExecutions = vi.mocked(getTaskExecutions);

const authenticatedUser = {
  id: "user-id",
  username: "admin",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("DashboardPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  beforeEach(() => {
    mockedGetTaskExecutions.mockResolvedValue([]);
  });

  it("shows the authenticated user", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows the health loading state", () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockReturnValue(new Promise(() => {}));
    mockedGetTasks.mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);

    expect(screen.getByText(/checking backend health/i)).toBeInTheDocument();
    expect(screen.getByText(/loading tasks/i)).toBeInTheDocument();
  });

  it("shows the healthy state", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(await screen.findByText(/backend is healthy/i)).toBeInTheDocument();
    expect(screen.getByText("Stanford-AI OS")).toBeInTheDocument();
  });

  it("shows an unavailable health state and retries", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth
      .mockRejectedValueOnce(new Error("Network down"))
      .mockResolvedValueOnce({
        status: "healthy",
        app: "Stanford-AI OS",
        environment: "development",
      });
    mockedGetTasks.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(
      await screen.findByText(/backend unavailable: network down/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry health check/i }));

    expect(await screen.findByText(/backend is healthy/i)).toBeInTheDocument();
    expect(mockedGetHealth).toHaveBeenCalledTimes(2);
  });

  it("shows a populated task list", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Review task history",
        description: "Check recent records",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("Review task history")).toBeInTheDocument();
    expect(screen.getByText("Check recent records")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows an empty task list", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(await screen.findByText(/no tasks found/i)).toBeInTheDocument();
  });

  it("shows a task error and retries", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks
      .mockRejectedValueOnce(new Error("Network down"))
      .mockResolvedValueOnce([]);

    render(<DashboardPage />);

    expect(
      await screen.findByText(/unable to load tasks: network down/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry task list/i }));

    expect(await screen.findByText(/no tasks found/i)).toBeInTheDocument();
    expect(mockedGetTasks).toHaveBeenCalledTimes(2);
  });

  it("clears authentication on a 401 task response", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockRejectedValue(new ApiError(401, "Request failed with status 401"));

    render(<DashboardPage />);

    await waitFor(() => expect(logout).toHaveBeenCalled());
  });

  it("does not clear authentication on a non-401 task error", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockRejectedValue(new Error("Network down"));

    render(<DashboardPage />);

    expect(
      await screen.findByText(/unable to load tasks: network down/i),
    ).toBeInTheDocument();
    expect(logout).not.toHaveBeenCalled();
  });

  it("creates a task and prepends it to the list", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);
    mockedCreateTask.mockResolvedValue({
      id: "new-task",
      title: "New task",
      description: "New description",
      status: "pending",
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    });

    render(<DashboardPage />);

    await screen.findByText(/no tasks found/i);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "  New task  " },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "New description" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(await screen.findByText("New task")).toBeInTheDocument();
    expect(screen.getByText("New description")).toBeInTheDocument();
    expect(mockedCreateTask).toHaveBeenCalledWith("token", {
      title: "New task",
      description: "New description",
    });
  });

  it("shows a validation message for HTTP 422 task creation", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);
    mockedCreateTask.mockRejectedValue(new ApiError(422, "bad request"));

    render(<DashboardPage />);

    await screen.findByText(/no tasks found/i);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByText(/please enter a valid task title/i),
    ).toBeInTheDocument();
  });

  it("shows a generic message for other task creation errors", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);
    mockedCreateTask.mockRejectedValue(new ApiError(500, "server error"));

    render(<DashboardPage />);

    await screen.findByText(/no tasks found/i);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByText(/unable to create task. please try again/i),
    ).toBeInTheDocument();
  });

  it("clears authentication on a 401 task creation response", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTasks.mockResolvedValue([]);
    mockedCreateTask.mockRejectedValue(new ApiError(401, "unauthorized"));

    render(<DashboardPage />);

    await screen.findByText(/no tasks found/i);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
  });


  it("executes a task and displays the result", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Execute me",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions.mockResolvedValue([
      {
        id: "execution-1",
        task_id: "task-1",
        status: "success",
        provider: "nvidia",
        model: "meta/llama-3.3-70b-instruct",
        duration_ms: 12,
        error_category: null,
        created_at: "2026-01-01T00:00:00Z",
        started_at: "2026-01-01T00:00:01Z",
        completed_at: "2026-01-01T00:00:02Z",
      },
    ]);
    mockedExecuteTask.mockResolvedValue({
      task_id: "task-1",
      output: "Generated execution result",
      provider: "nvidia",
      model: "meta/llama-3.3-70b-instruct",
      duration_ms: 42,
    });

    render(<DashboardPage />);

    expect(await screen.findByText("Execute me")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /execute task/i }));

    expect(await screen.findByText(/generated execution result/i)).toBeInTheDocument();
    expect(screen.getByText(/provider: nvidia/i)).toBeInTheDocument();
    expect(screen.getByText(/model: meta\/llama-3.3-70b-instruct/i)).toBeInTheDocument();
    expect(screen.getByText(/duration: 42 ms/i)).toBeInTheDocument();
    expect(mockedExecuteTask).toHaveBeenCalledWith("token", "task-1");
  });

  it("shows a provider failure without changing task status", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Execute me",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedExecuteTask.mockRejectedValue(new ApiError(502, "provider failed"));

    render(<DashboardPage />);

    expect(await screen.findByText("Execute me")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /execute task/i }));

    expect(
      await screen.findByText(/unable to execute task/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });
  it("shows a rate-limit message for HTTP 429 during execution", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Execute me",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedExecuteTask.mockRejectedValue(new ApiError(429, "too many"));

    render(<DashboardPage />);

    expect(await screen.findByText("Execute me")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /execute task/i }));

    expect(
      await screen.findByText(/too many requests/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });


  it("clears authentication on a 401 execution response", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "Execute me",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedExecuteTask.mockRejectedValue(new ApiError(401, "unauthorized"));

    render(<DashboardPage />);

    expect(await screen.findByText("Execute me")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /execute task/i }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
  });

  it("loads execution history only after View history is clicked", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "History task",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("History task")).toBeInTheDocument();
    expect(mockedGetTaskExecutions).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /view history/i }));

    await waitFor(() => {
      expect(screen.getByText(/execution history/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/execution history/i)).toBeInTheDocument();
    expect(screen.getByText(/provider: nvidia/i)).toBeInTheDocument();
    expect(screen.getByText(/duration: 42 ms/i)).toBeInTheDocument();
    expect(mockedGetTaskExecutions).toHaveBeenCalledWith("token", "task-1");
  });

  it("does not refetch history when reopening it", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "History task",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(await screen.findByText("History task")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view history/i }));
    await screen.findByText(/no execution history found/i);

    fireEvent.click(screen.getByRole("button", { name: /hide history/i }));
    fireEvent.click(screen.getByRole("button", { name: /view history/i }));

    expect(mockedGetTaskExecutions).toHaveBeenCalledTimes(1);
  });

  it("retries execution history after an error", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "History task",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions
      .mockRejectedValueOnce(new Error("Network down"))
      .mockResolvedValueOnce([]);

    render(<DashboardPage />);

    expect(await screen.findByText("History task")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view history/i }));

    expect(
      await screen.findByText(/unable to load execution history: network down/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry history/i }));

    expect(await screen.findByText(/no execution history found/i)).toBeInTheDocument();
    expect(mockedGetTaskExecutions).toHaveBeenCalledTimes(2);
  });

  it("clears authentication on a 401 history response", async () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "History task",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions.mockRejectedValue(new ApiError(401, "unauthorized"));

    render(<DashboardPage />);

    expect(await screen.findByText("History task")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view history/i }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
  });

  it("keeps the current execution result separate from persisted history", async () => {
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });
    mockedGetTaskExecutions.mockResolvedValue([
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
    ]);
    mockedGetTasks.mockResolvedValue([
      {
        id: "task-1",
        title: "History task",
        description: "Details",
        status: "pending",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockedGetTaskExecutions.mockResolvedValue([
      {
        id: "execution-1",
        task_id: "task-1",
        status: "success",
        provider: "nvidia",
        model: "meta/llama-3.3-70b-instruct",
        duration_ms: 12,
        error_category: null,
        created_at: "2026-01-01T00:00:00Z",
        started_at: "2026-01-01T00:00:01Z",
        completed_at: "2026-01-01T00:00:02Z",
      },
    ]);
    mockedExecuteTask.mockResolvedValue({
      task_id: "task-1",
      output: "Current result",
      provider: "nvidia",
      model: "meta/llama-3.3-70b-instruct",
      duration_ms: 12,
    });
    mockedGetTaskExecutions.mockResolvedValue([
      {
        id: "execution-1",
        task_id: "task-1",
        status: "success",
        provider: "nvidia",
        model: "meta/llama-3.3-70b-instruct",
        duration_ms: 12,
        error_category: null,
        created_at: "2026-01-01T00:00:00Z",
        started_at: "2026-01-01T00:00:01Z",
        completed_at: "2026-01-01T00:00:02Z",
      },
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("History task")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /execute task/i }));
    expect(await screen.findByText(/current result/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view history/i }));

    await waitFor(() => {
      expect(screen.getByText(/execution history/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/execution history/i)).toBeInTheDocument();
    expect(screen.getByText(/result: current result/i)).toBeInTheDocument();
  });
  it("calls logout when the logout button is clicked", () => {
    const logout = vi.fn();
    mockedUseAuth.mockReturnValue({
      token: "token",
      user: authenticatedUser,
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      verifySession: vi.fn(),
    });
    mockedGetHealth.mockReturnValue(new Promise(() => {}));
    mockedGetTasks.mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);

    fireEvent.click(screen.getByRole("button", { name: /log out/i }));

    expect(logout).toHaveBeenCalledOnce();
  });
});
