"use client";

import React, { useState } from "react";

const SERVICE_CONFIG = {
  slack: {
    name: "Slack",
    icon: "💬",
    accentColor: "#36C5F0",
    description: "Read channel messages and extract decision threads",
  },
  gmail: {
    name: "Gmail & Google Drive",
    icon: "📧",
    accentColor: "#EA4335",
    description: "Read emails, approvals, and shared documents",
  },
  jira: {
    name: "Jira",
    icon: "🎯",
    accentColor: "#0052CC",
    description: "Read tickets, epics, and project decisions",
  },
  zoom: {
    name: "Zoom",
    icon: "📹",
    accentColor: "#0B5CFF",
    description: "Transcribe meeting recordings with Whisper",
  },
} as const;

type ServiceKey = keyof typeof SERVICE_CONFIG;

interface IntegrationButtonProps {
  service: ServiceKey;
  token: string | null;
  isConnected: boolean;
  serviceName?: string;
  connectedAt?: string;
  onRefresh: () => void;
}

export default function IntegrationButton({
  service,
  token,
  isConnected,
  serviceName,
  connectedAt,
  onRefresh,
}: IntegrationButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cfg = SERVICE_CONFIG[service];

  const handleConnect = async () => {
    setIsLoading(true);
    setError(null);

    if (!token) {
      setError("Not authenticated — please sign in first.");
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch(`/api/oauth/${service}/start`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to start OAuth" }));
        throw new Error(err.detail || "Failed to start OAuth");
      }

      const { url } = await res.json();

      const popup = window.open(url, "kairos_oauth", "width=600,height=700,left=200,top=100");
      if (!popup) {
        setError("Popup blocked — please allow popups for this site and try again.");
        setIsLoading(false);
        return;
      }

      // Poll until popup closes, then refresh status
      const timer = setInterval(() => {
        if (popup.closed) {
          clearInterval(timer);
          // Small delay to ensure backend has stored the token
          setTimeout(() => {
            onRefresh();
            setIsLoading(false);
          }, 800);
        }
      }, 500);

      // Safety timeout: 10 minutes
      setTimeout(() => {
        clearInterval(timer);
        if (!popup.closed) popup.close();
        setIsLoading(false);
      }, 10 * 60 * 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
      setIsLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect ${cfg.name}? KAIROS will stop ingesting data from this source.`)) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/oauth/disconnect/${service}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Disconnect failed" }));
        throw new Error(err.detail || "Disconnect failed");
      }

      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setIsLoading(false);
    }
  };

  const formattedDate = connectedAt
    ? new Date(connectedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : null;

  return (
    <div
      className="flex items-center justify-between p-5 rounded-xl border transition-all theme-transition"
      style={{
        borderColor: isConnected ? "rgba(34,197,94,0.4)" : "rgb(var(--border))",
        background: isConnected ? "rgba(34,197,94,0.04)" : "rgb(var(--surface))",
      }}
    >
      {/* Left: icon + info */}
      <div className="flex items-start gap-4 flex-1 min-w-0">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
          style={{ background: `${cfg.accentColor}18` }}
        >
          {cfg.icon}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-[rgb(var(--text-primary))]">{cfg.name}</span>
            {isConnected && (
              <span className="text-[9px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                CONNECTED
              </span>
            )}
          </div>
          <p className="text-[11px] text-[rgb(var(--text-muted))] mt-0.5">{cfg.description}</p>
          {isConnected && serviceName && (
            <p className="text-[10px] text-[rgb(var(--text-muted))] mt-0.5">
              <span className="text-zinc-500">as</span>{" "}
              <span className="font-semibold text-[rgb(var(--text-primary))]">{serviceName}</span>
              {formattedDate && (
                <span className="text-zinc-600 ml-2">· {formattedDate}</span>
              )}
            </p>
          )}
          {error && (
            <p className="text-[10px] text-rose-400 mt-1">⚠ {error}</p>
          )}
        </div>
      </div>

      {/* Right: action button */}
      <div className="shrink-0 ml-4">
        {isConnected ? (
          <button
            onClick={handleDisconnect}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 text-[11px] font-semibold disabled:opacity-40 transition-all"
          >
            {isLoading ? "…" : "Disconnect"}
          </button>
        ) : (
          <button
            onClick={handleConnect}
            disabled={isLoading}
            className="px-4 py-1.5 rounded-lg text-white text-[11px] font-semibold disabled:opacity-40 transition-all hover:opacity-90"
            style={{ background: isLoading ? "#3f3f46" : cfg.accentColor }}
          >
            {isLoading ? "Connecting…" : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}
