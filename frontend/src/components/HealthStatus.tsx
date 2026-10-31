import type { HealthResponse } from "../api/health";

interface HealthStatusProps {
  health: HealthResponse;
}

export function HealthStatus({ health }: HealthStatusProps) {
  return (
    <div>
      <p className="status-healthy">Backend is healthy</p>
      <dl>
        <dt>Status</dt>
        <dd>{health.status}</dd>
        <dt>Application</dt>
        <dd>{health.app}</dd>
        <dt>Environment</dt>
        <dd>{health.environment}</dd>
      </dl>
    </div>
  );
}
