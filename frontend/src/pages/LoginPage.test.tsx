import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";
vi.mock("../auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../auth/useAuth";

const mockedUseAuth = vi.mocked(useAuth);

describe("LoginPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the login form", () => {
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      status: "unauthenticated",
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /login/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls login with entered credentials", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      status: "unauthenticated",
      isAuthenticated: false,
      login,
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({ username: "admin", password: "secret" });
    });
  });

  it("shows invalid credentials feedback", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Invalid username or password."));
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      status: "unauthenticated",
      isAuthenticated: false,
      login,
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );
  });

  it("shows a generic failure for network errors", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Login failed. Please try again."));
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      status: "unauthenticated",
      isAuthenticated: false,
      login,
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Login failed. Please try again.",
    );
  });

  it("disables the submit button while authenticating", () => {
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      status: "authenticating",
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      verifySession: vi.fn(),
    });

    render(<LoginPage />);

    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
  });
});
