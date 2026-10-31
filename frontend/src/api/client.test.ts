import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchJson } from "./client";

describe("fetchJson", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON for successful responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await expect(fetchJson<{ ok: boolean }>("/example")).resolves.toEqual({
      ok: true,
    });
  });

  it("throws ApiError for unsuccessful responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not found", { status: 404 }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
    });
  });

  it("passes request options to fetch", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await fetchJson("/example", {
      headers: { Authorization: "Bearer token" },
    });

    expect(fetchSpy).toHaveBeenCalledWith("/example", {
      headers: { Authorization: "Bearer token" },
    });
  });
});

describe("fetchJson error details", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses a string detail from a JSON error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Backend detail message" }), {
        status: 400,
      }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      detail: "Backend detail message",
    });
  });

  it("ignores a non-string detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: ["invalid field"] }), {
        status: 422,
      }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: undefined,
    });
  });

  it("handles malformed JSON error bodies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 500 }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
      detail: undefined,
    });
  });

  it("handles missing detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "something" }), { status: 403 }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      detail: undefined,
    });
  });

  it("ignores an empty detail string", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "   " }), { status: 400 }),
    );

    await expect(fetchJson("/example")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      detail: undefined,
    });
  });
});

import { apiUrl, getApiBaseUrl } from "./client";

describe("API base URL handling", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns an empty base URL when VITE_API_BASE_URL is unset", () => {
    expect(getApiBaseUrl()).toBe("");
  });

  it("strips trailing slashes from the base URL", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/");
    expect(getApiBaseUrl()).toBe("https://api.example.com");
  });

  it("trims whitespace from the base URL", () => {
    vi.stubEnv("VITE_API_BASE_URL", "  https://api.example.com  ");
    expect(getApiBaseUrl()).toBe("https://api.example.com");
  });

  it("joins a relative path with an absolute base URL", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    expect(apiUrl("/tasks")).toBe("https://api.example.com/tasks");
  });

  it("avoids double slashes when joining", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/");
    expect(apiUrl("/tasks")).toBe("https://api.example.com/tasks");
  });

  it("preserves query parameters", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    expect(apiUrl("/tasks/123/executions?limit=20&offset=0")).toBe(
      "https://api.example.com/tasks/123/executions?limit=20&offset=0",
    );
  });

  it("returns the original path when no base URL is configured", () => {
    expect(apiUrl("/tasks")).toBe("/tasks");
  });

  it("prefixes fetch requests when a base URL is configured", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await fetchJson<{ ok: boolean }>("/example");

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.example.com/example",
      undefined,
    );
  });

  it("uses relative paths when no base URL is configured", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await fetchJson<{ ok: boolean }>("/example");

    expect(fetchSpy).toHaveBeenCalledWith("/example", undefined);
  });
});
