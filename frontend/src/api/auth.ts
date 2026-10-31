import { fetchJson } from "./client";

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export async function login(
  credentials: LoginCredentials,
): Promise<TokenResponse> {
  return fetchJson<TokenResponse>("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });
}

export async function getCurrentUser(token: string): Promise<CurrentUser> {
  return fetchJson<CurrentUser>("/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
