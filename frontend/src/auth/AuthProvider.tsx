import { flushSync } from "react-dom";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { getCurrentUser, login as loginRequest } from "../api/auth";
import { ApiError } from "../api/client";
import type { CurrentUser, LoginCredentials } from "../api/auth";
import type { AuthStatus } from "./AuthContextDefinition";
import { AuthContext } from "./AuthContextDefinition";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("unauthenticated");

  const clearSession = useCallback(() => {
    flushSync(() => {
      setToken(null);
      setUser(null);
      setStatus("unauthenticated");
    });
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setStatus("authenticating");

    let response: Awaited<ReturnType<typeof loginRequest>>;
    try {
      response = await loginRequest(credentials);
    } catch (error) {
      clearSession();

      if (error instanceof ApiError && error.status === 401) {
        throw new Error("Invalid username or password.");
      }

      throw new Error("Login failed. Please try again.");
    }

    try {
      const currentUser = await getCurrentUser(response.access_token);

      setToken(response.access_token);
      setUser(currentUser);
      setStatus("authenticated");
    } catch (error) {
      clearSession();

      if (error instanceof ApiError && error.status === 401) {
        throw new Error("Unable to verify your session.");
      }

      throw new Error("Login failed. Please try again.");
    }
  }, [clearSession]);

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const verifySession = useCallback(async () => {
    if (!token) {
      return;
    }

    try {
      const currentUser = await getCurrentUser(token);
      setUser(currentUser);
      setStatus("authenticated");
    } catch (error) {
      clearSession();

      if (error instanceof ApiError && error.status === 401) {
        throw new Error("Your session is no longer valid.");
      }

      throw new Error("Unable to verify your session.");
    }
  }, [clearSession, token]);

  const value = useMemo(
    () => ({
      token,
      user,
      status,
      isAuthenticated: token !== null && user !== null,
      login,
      logout,
      verifySession,
    }),
    [login, logout, status, token, user, verifySession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
