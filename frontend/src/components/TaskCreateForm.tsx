import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { createTask, type Task, type TaskCreateInput } from "../api/tasks";

interface TaskCreateFormProps {
  token: string;
  onTaskCreated: (task: Task) => void;
  onUnauthorized?: () => void;
}

export function TaskCreateForm({
  token,
  onTaskCreated,
  onUnauthorized,
}: TaskCreateFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setErrorMessage("Title is required.");
      return;
    }

    if (trimmedTitle.length > 200) {
      setErrorMessage("Title must be 200 characters or fewer.");
      return;
    }

    setIsSubmitting(true);

    const input: TaskCreateInput = {
      title: trimmedTitle,
      description: description.trim() === "" ? null : description.trim(),
    };

    try {
      const task = await createTask(token, input);
      onTaskCreated(task);
      setTitle("");
      setDescription("");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onUnauthorized?.();
        setErrorMessage("Your session is no longer valid.");
      } else if (error instanceof ApiError && error.status === 422) {
        setErrorMessage("Please enter a valid task title.");
      } else if (error instanceof ApiError && error.status === 429) {
        setErrorMessage("Too many requests. Please wait a little while before trying again.");
      } else if (error instanceof ApiError && error.detail) {
        setErrorMessage(error.detail);
      } else {
        setErrorMessage("Unable to create task. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-labelledby="create-task-heading">
      <h3 id="create-task-heading">Create task</h3>

      <label>
        Title
        <input
          type="text"
          name="title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
          required
          disabled={isSubmitting}
        />
      </label>

      <label>
        Description
        <textarea
          name="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          disabled={isSubmitting}
        />
      </label>

      {errorMessage ? <p role="alert">{errorMessage}</p> : null}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating..." : "Create task"}
      </button>
    </form>
  );
}
