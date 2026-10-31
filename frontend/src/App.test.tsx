import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import App from "./App";
import * as authApi from "./api/auth";

vi.mock("./pages/HealthPage", () => ({
  default: () => <div>Health page</div>,
}));

vi.mock("./pages/DashboardPage", () => ({
  default: () => <div>Dashboard page</div>,
}));

vi.mock("./api/auth", () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
}));

const mockedLogin = vi.mocked(authApi.login);
const mockedGetCurrentUser = vi.mocked(authApi.getCurrentUser);

const user = {
  id: "user-id",
  username: "admin",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("App", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the application shell", () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    expect(
      screen.getByRole("heading", { name: /stanford-ai os/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Health page")).toBeInTheDocument();
  });

  it("does not render the dashboard for an unauthenticated user", () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /dashboard/i }));

    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByText("Dashboard page")).not.toBeInTheDocument();
  });

  it("renders the dashboard after successful login", async () => {
    mockedLogin.mockResolvedValue({
      access_token: "memory-token",
      token_type: "bearer",
    });
    mockedGetCurrentUser.mockResolvedValue(user);

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /dashboard/i }));

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  });
});
