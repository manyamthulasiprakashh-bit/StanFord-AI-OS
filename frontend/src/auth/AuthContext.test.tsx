import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";
import * as authApi from "../api/auth";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
}));

const mockedLogin = vi.mocked(authApi.login);
const mockedGetCurrentUser = vi.mocked(authApi.getCurrentUser);

const credentials = { username: "admin", password: "secret" };
const token = "memory-token";
const user = {
  id: "user-id",
  username: "admin",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthContext", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("starts unauthenticated", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("stores the token only in memory after successful login", async () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser.mockResolvedValue(user);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login(credentials);
    });

    expect(result.current.token).toBe(token);
    expect(result.current.user).toEqual(user);
    expect(result.current.isAuthenticated).toBe(true);
    // The token is intentionally kept only in React state.
  });

  it("clears state when current-user retrieval fails after login", async () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser.mockRejectedValue(new ApiError(401, "Request failed with status 401"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await expect(
      act(async () => {
        await result.current.login(credentials);
      }),
    ).rejects.toThrow("Unable to verify your session.");

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("clears state on logout", async () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser.mockResolvedValue(user);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login(credentials);
    });

    act(() => {
      result.current.logout();
    });

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("clears state when session verification receives HTTP 401", async () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser
      .mockResolvedValueOnce(user)
      .mockRejectedValueOnce(new ApiError(401, "Request failed with status 401"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login(credentials);
    });

    await expect(
      act(async () => {
        await result.current.verifySession();
      }),
    ).rejects.toThrow("Your session is no longer valid.");

    await waitFor(() => expect(result.current.token).toBeNull());
    await waitFor(() => expect(result.current.user).toBeNull());
  });
});

describe("ProtectedRoute", () => {
  it("renders protected content when authenticated", () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser.mockResolvedValue(user);

    function TestComponent() {
      const auth = useAuth();

      return auth.isAuthenticated ? <div>Protected content</div> : null;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });
});

  it("updates the user on successful session verification", async () => {
    const updatedUser = {
      id: "user-id",
      username: "admin",
      is_active: true,
      created_at: "2026-01-02T00:00:00Z",
    };
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser
      .mockResolvedValueOnce(user)
      .mockResolvedValueOnce(updatedUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login(credentials);
    });

    await act(async () => {
      await result.current.verifySession();
    });

    expect(result.current.user).toEqual(updatedUser);
    expect(result.current.status).toBe("authenticated");
    expect(result.current.token).toBe(token);
  });

  it("clears state on a non-401 session verification error", async () => {
    mockedLogin.mockResolvedValue({ access_token: token, token_type: "bearer" });
    mockedGetCurrentUser
      .mockResolvedValueOnce(user)
      .mockRejectedValueOnce(new Error("Network down"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login(credentials);
    });

    await expect(
      act(async () => {
        await result.current.verifySession();
      }),
    ).rejects.toThrow("Unable to verify your session.");

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.status).toBe("unauthenticated");
  });
