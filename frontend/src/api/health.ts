import { apiUrl } from "./client";

export interface HealthResponse {
  status: string;
  app: string;
  environment: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(apiUrl("/health"));

  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}
