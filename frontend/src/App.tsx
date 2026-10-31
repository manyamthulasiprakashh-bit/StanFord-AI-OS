import { useState } from "react";
import { useAuth } from "./auth/useAuth";
import { ProtectedRoute } from "./components/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import HealthPage from "./pages/HealthPage";
import LoginPage from "./pages/LoginPage";

type Page = "health" | "login" | "dashboard";

export default function App() {
  const { isAuthenticated } = useAuth();
  const [page, setPage] = useState<Page>("health");

  const currentPage =
    page === "dashboard" && !isAuthenticated ? "login" : page;

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Stanford-AI OS</h1>
        <p>Backend health and authentication</p>
      </header>

      <nav className="app-nav" aria-label="Primary">
        <button
          type="button"
          className={currentPage === "health" ? "active" : ""}
          onClick={() => setPage("health")}
        >
          Health
        </button>
        <button
          type="button"
          className={currentPage === "login" ? "active" : ""}
          onClick={() => setPage("login")}
        >
          Login
        </button>
        <button
          type="button"
          className={currentPage === "dashboard" ? "active" : ""}
          onClick={() => setPage("dashboard")}
        >
          Dashboard
        </button>
      </nav>

      <main className="app-main">
        {currentPage === "health" ? (
          <HealthPage />
        ) : currentPage === "login" ? (
          <LoginPage />
        ) : (
          <ProtectedRoute fallback={<LoginPage />}>
            <DashboardPage />
          </ProtectedRoute>
        )}
      </main>
    </div>
  );
}
