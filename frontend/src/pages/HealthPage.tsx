import { useEffect, useState } from "react";
import { HealthStatus } from "../components/HealthStatus";
import { getHealth, type HealthResponse } from "../api/health";

type HealthState =
  | { kind: "loading" }
  | { kind: "healthy"; health: HealthResponse }
  | { kind: "unavailable"; message: string };

export default function HealthPage() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let isActive = true;

    getHealth()
      .then((health) => {
        if (isActive) {
          setState({ kind: "healthy", health });
        }
      })
      .catch((error: unknown) => {
        if (isActive) {
          const message =
            error instanceof Error ? error.message : "Backend is unavailable";
          setState({ kind: "unavailable", message });
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  if (state.kind === "loading") {
    return <p>Checking backend health...</p>;
  }

  if (state.kind === "healthy") {
    return <HealthStatus health={state.health} />;
  }

  return <p className="status-unavailable" role="alert">Backend unavailable: {state.message}</p>;
}
