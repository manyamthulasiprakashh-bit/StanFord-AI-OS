export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL;
  if (typeof raw !== "string") {
    return "";
  }

  return raw.trim().replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  const base = getApiBaseUrl();
  if (!base) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

export async function fetchJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), options);

  if (!response.ok) {
    let detail: string | undefined;

    try {
      const body = await response.json();
      if (
        body !== null &&
        typeof body === "object" &&
        "detail" in body &&
        typeof (body as { detail: unknown }).detail === "string"
      ) {
        const parsedDetail = (body as { detail: string }).detail.trim();
        if (parsedDetail.length > 0) {
          detail = parsedDetail;
        }
      }
    } catch {
      // Ignore malformed or non-JSON error bodies.
    }

    throw new ApiError(
      response.status,
      `Request failed with status ${response.status}`,
      detail,
    );
  }

  return response.json() as Promise<T>;
}
