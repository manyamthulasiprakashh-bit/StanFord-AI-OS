import { afterEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser, login } from "./auth";
import { ApiError } from "./client";

describe("auth API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts credentials to the login endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({ access_token: "token-123", token_type: "bearer" }),
          { status: 200 },
        ),
      );

    await expect(
      login({ username: "admin", password: "secret" }),
    ).resolves.toEqual({
      access_token: "token-123",
      token_type: "bearer",
    });

    expect(fetchSpy).toHaveBeenCalledWith("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "admin", password: "secret" }),
    });
  });

  it("sends the bearer token to /auth/me", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "user-id",
            username: "admin",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          }),
          { status: 200 },
        ),
      );

    await expect(getCurrentUser("token-123")).resolves.toMatchObject({
      username: "admin",
    });

    expect(fetchSpy).toHaveBeenCalledWith("/auth/me", {
      headers: { Authorization: "Bearer token-123" },
    });
  });

  it("throws ApiError for unsuccessful responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("unauthorized", { status: 401 }),
    );

    await expect(getCurrentUser("token-123")).rejects.toBeInstanceOf(ApiError);
  });
});
