"use client";

import React, { useState } from "react";

const SERVICE_CONFIG: Record<string, { name: string; icon: React.ReactNode; accentColor: string; description: string }> = {
  slack: {
    name: "Slack",
    icon: (<svg viewBox="0 0 24 24" className="w-6 h-6"><path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/><path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/><path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/><path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.315A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.522 2.523h-6.315z" fill="#ECB22E"/></svg>),
    accentColor: "#36C5F0",
    description: "Read channel messages and extract decision threads",
  },
  gmail: {
    name: "Gmail & Google Drive",
    icon: (
      <svg viewBox="52 42 88 66" className="w-6 h-6">
        <path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>
        <path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>
        <path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2L120 48"/>
        <path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92z"/>
        <path fill="#c5221f" d="M52 59l20 15V48l-20 11"/>
      </svg>
    ),
    accentColor: "#EA4335",
    description: "Read emails, approvals, and shared documents",
  },
  jira: {
    name: "Jira",
    icon: (
      <svg viewBox="0 0 24 24" className="w-6 h-6">
        <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z" fill="#0052CC"/>
        <path d="M17.294 5.757H5.723a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z" fill="#0065FF"/>
        <path d="M23.013 0H11.455a5.215 5.215 0 0 0-5.215 5.215h2.129v2.057a5.215 5.215 0 0 0 5.215 5.215V1.001A1.001 1.001 0 0 0 12.636 0z" fill="#4C9AFF"/>
      </svg>
    ),
    accentColor: "#0052CC",
    description: "Read tickets, epics, and project decisions",
  },
  zoom: {
    name: "Zoom",
    icon: (
      <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none">
        <rect width="24" height="24" rx="6" fill="#2D8CFF"/>
        <path d="M4 9.333C4 8.597 4.597 8 5.333 8H13.334C14.07 8 14.667 8.597 14.667 9.333v5.334C14.667 15.403 14.07 16 13.334 16H5.333C4.597 16 4 15.403 4 14.667V9.333z" fill="white"/>
        <path d="M15.667 10.4L19.333 8.267A.5.5 0 0 1 20 8.7v6.6a.5.5 0 0 1-.667.433L15.667 13.6V10.4z" fill="white"/>
      </svg>
    ),
    accentColor: "#2D8CFF",
    description: "Transcribe meeting recordings with Whisper",
  },
};

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

      const data = await res.json();

      // S2S or server-side connect (e.g. Zoom with server credentials) — no popup needed
      if (data.connected === true) {
        onRefresh();
        setIsLoading(false);
        return;
      }

      const { url } = data;

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
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
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
