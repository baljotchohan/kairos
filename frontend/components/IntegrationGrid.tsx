"use client";

import React, { useState, useEffect, useCallback } from "react";
import IntegrationButton from "./IntegrationButton";

type ServiceKey = "slack" | "gmail" | "drive" | "jira" | "zoom";

interface ServiceStatus {
  connected: boolean;
  connected_at?: string;
  service_name?: string;
}

type ConnectionsMap = Record<ServiceKey, ServiceStatus>;

interface IntegrationGridProps {
  token: string | null;
}

const SERVICES: ServiceKey[] = ["slack", "gmail", "drive", "jira", "zoom"];

const DEFAULT_STATE: ConnectionsMap = {
  slack: { connected: false },
  gmail: { connected: false },
  drive: { connected: false },
  jira: { connected: false },
  zoom: { connected: false },
};

export default function IntegrationGrid({ token }: IntegrationGridProps) {
  const [connections, setConnections] = useState<ConnectionsMap>(DEFAULT_STATE);
  const [isFetching, setIsFetching] = useState(true);

  const fetchStatus = useCallback(async () => {
    setConnections(DEFAULT_STATE);
    setIsFetching(true);
    if (!token) {
      setIsFetching(false);
      return;
    }

    try {
      const res = await fetch("/api/oauth/status", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setConnections((prev) => ({ ...prev, ...data }));
      }
    } catch {
      // backend may not be running — keep default disconnected state
    } finally {
      setIsFetching(false);
    }
  }, [token]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const connectedCount = SERVICES.filter((s) => connections[s]?.connected).length;

  return (
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] uppercase tracking-wider">
          {connectedCount}/{SERVICES.length} connectors active
        </span>
        {isFetching && (
          <span className="text-[9px] font-mono text-zinc-600 animate-pulse">Checking status…</span>
        )}
      </div>

      <div className="w-full h-0.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 rounded-full transition-all duration-700"
          style={{ width: `${(connectedCount / SERVICES.length) * 100}%` }}
        />
      </div>

      {/* Buttons */}
      <div className="space-y-2 pt-1">
        {SERVICES.map((service) => (
          <IntegrationButton
            key={service}
            service={service}
            token={token}
            isConnected={connections[service]?.connected || false}
            serviceName={connections[service]?.service_name}
            connectedAt={connections[service]?.connected_at}
            onRefresh={fetchStatus}
          />
        ))}
      </div>

      {/* Info footer */}
      {!token && (
        <p className="text-[10px] text-amber-500/70 font-mono text-center mt-2">
          Sign in to connect your work apps
        </p>
      )}
    </div>
  );
}
