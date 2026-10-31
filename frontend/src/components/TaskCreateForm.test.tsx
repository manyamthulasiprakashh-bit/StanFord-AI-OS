import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { TaskCreateForm } from "./TaskCreateForm";
import * as tasksApi from "../api/tasks";

vi.mock("../api/tasks", () => ({
  createTask: vi.fn(),
}));

const mockedCreateTask = vi.mocked(tasksApi.createTask);

describe("TaskCreateForm", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a whitespace-only title without calling the API", async () => {
    const onTaskCreated = vi.fn();
    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Title is required.");
    expect(mockedCreateTask).not.toHaveBeenCalled();
    expect(onTaskCreated).not.toHaveBeenCalled();
  });

  it("rejects a title longer than 200 characters without calling the API", async () => {
    const onTaskCreated = vi.fn();
    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "a".repeat(201) },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Title must be 200 characters or fewer.");
    expect(mockedCreateTask).not.toHaveBeenCalled();
  });

  it("submits a trimmed title and null description", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockResolvedValue({
      id: "task-1",
      title: "Trimmed title",
      description: null,
      status: "pending",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "  Trimmed title  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    await waitFor(() => {
      expect(mockedCreateTask).toHaveBeenCalledWith("token", {
        title: "Trimmed title",
        description: null,
      });
    });
    expect(onTaskCreated).toHaveBeenCalled();
  });

  it("shows a validation message for HTTP 422", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockRejectedValue(new ApiError(422, "bad request"));

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Please enter a valid task title.");
    expect(onTaskCreated).not.toHaveBeenCalled();
  });

  it("shows a generic error for other failures", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockRejectedValue(new ApiError(500, "server error"));

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Unable to create task. Please try again.");
  });

  it("calls onUnauthorized for HTTP 401", async () => {
    const onTaskCreated = vi.fn();
    const onUnauthorized = vi.fn();
    mockedCreateTask.mockRejectedValue(new ApiError(401, "unauthorized"));

    render(
      <TaskCreateForm
        token="token"
        onTaskCreated={onTaskCreated}
        onUnauthorized={onUnauthorized}
      />,
    );

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalled());
    expect(onTaskCreated).not.toHaveBeenCalled();
  });
  it("shows a rate-limit message for HTTP 429", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockRejectedValue(new ApiError(429, "too many"));

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Too many requests. Please wait a little while before trying again.");
    expect(onTaskCreated).not.toHaveBeenCalled();
  });

  it("shows a backend detail for a generic creation error", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockRejectedValue(
      new ApiError(500, "Request failed with status 500", "Backend detail message"),
    );

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Backend detail message");
    expect(onTaskCreated).not.toHaveBeenCalled();
  });

  it("falls back to the generic message when no detail is available", async () => {
    const onTaskCreated = vi.fn();
    mockedCreateTask.mockRejectedValue(new ApiError(500, "server error"));

    render(<TaskCreateForm token="token" onTaskCreated={onTaskCreated} />);

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Valid title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create task/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to create task. Please try again.",
    );
    expect(onTaskCreated).not.toHaveBeenCalled();
  });

});
