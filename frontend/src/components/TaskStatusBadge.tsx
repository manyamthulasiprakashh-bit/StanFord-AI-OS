interface TaskStatusBadgeProps {
  status: "pending" | "in_progress" | "completed" | "failed";
}

const labels: Record<TaskStatusBadgeProps["status"], string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
};

export function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  return (
    <span className={`task-status task-status-${status}`}>
      {labels[status]}
    </span>
  );
}
