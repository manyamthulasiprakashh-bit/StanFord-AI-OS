import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function ProtectedRoute({ children, fallback }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <>{fallback ?? <p>Please log in to continue.</p>}</>;
  }

  return <>{children}</>;
}
