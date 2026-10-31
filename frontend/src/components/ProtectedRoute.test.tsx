import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "./ProtectedRoute";

vi.mock("../auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../auth/useAuth";

describe("ProtectedRoute", () => {
  it("shows the unauthenticated fallback", () => {
    vi.mocked(useAuth).mockReturnValue({
      token: null,
      user: null,
      status: "unauthenticated",
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(
      <ProtectedRoute fallback={<p>Please log in to continue.</p>}>
        <div>Protected content</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Please log in to continue.")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders protected content for an authenticated user", () => {
    vi.mocked(useAuth).mockReturnValue({
      token: "token",
      user: {
        id: "user-id",
        username: "admin",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      status: "authenticated",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div>Protected content</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
