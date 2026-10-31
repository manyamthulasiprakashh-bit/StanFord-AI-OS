import { useContext } from "react";
import { AuthContext } from "./AuthContextDefinition";
import type { AuthContextValue } from "./AuthContextDefinition";

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);

  if (value === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return value;
}
