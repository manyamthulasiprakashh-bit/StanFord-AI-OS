import { createContext } from "react";
import type { CurrentUser } from "../api/auth";

export type AuthStatus = "unauthenticated" | "authenticating" | "authenticated";

export interface AuthContextValue {
  token: string | null;
  user: CurrentUser | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  login: (credentials: { username: string; password: string }) => Promise<void>;
  logout: () => void;
  verifySession: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
