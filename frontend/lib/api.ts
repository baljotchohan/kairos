const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
}

export interface ConnectorStatus {
  name: string;
  connected: boolean;
  last_synced: string | null;
  total_items: number;
}

export interface AdminStatus {
  total_decisions: number;
  total_relations: number;
  connectors: ConnectorStatus[];
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

export async function getAdminStatus(): Promise<AdminStatus> {
  return apiFetch<AdminStatus>("/api/v1/admin/status");
}
