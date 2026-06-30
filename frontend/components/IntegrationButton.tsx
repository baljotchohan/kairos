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
    name: "Gmail",
    icon: (
      <svg viewBox="52 42 88 66" className="w-7 h-7">
        <path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>
        <path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>
        <path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2"/>
        <path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92"/>
        <path fill="#c5221f" d="M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2"/>
      </svg>
    ),
    accentColor: "#EA4335",
    description: "Read emails, approvals, and decision threads",
  },
  drive: {
    name: "Google Drive",
    icon: (
      <svg viewBox="0 0 87.3 78" className="w-6 h-6">
        <path d="M6.6 66.85 10.45 73.5c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8H0c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
        <path d="M43.65 25 29.9 1.2c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44A9.06 9.06 0 0 0 0 53h27.5z" fill="#00ac47"/>
        <path d="M73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5H59.3l5.85 11.5z" fill="#ea4335"/>
        <path d="M43.65 25 57.4 1.2c-1.35-.8-2.9-1.2-4.5-1.2H34.4c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
        <path d="M59.8 53H27.5L13.75 76.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
        <path d="M73.4 26.5 60.7 4.5c-.8-1.4-1.95-2.5-3.3-3.3L43.65 25 59.8 53h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
      </svg>
    ),
    accentColor: "#1FA463",
    description: "Read Drive files, docs, specs, and proposals",
  },
  jira: {
    name: "Jira",
    icon: (
      <svg viewBox="0 0 24 24" className="w-7 h-7">
        <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z" fill="#0052CC"/>
        <path d="M17.294 5.757H5.723a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z" fill="#0065FF"/>
        <path d="M23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0z" fill="#4C9AFF"/>
      </svg>
    ),
    accentColor: "#0052CC",
    description: "Read tickets, epics, and project decisions",
  },
  zoom: {
    name: "Zoom",
    icon: (
      <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#2D8CFF">
        <path d="M3 8.5C3 7.12 4.12 6 5.5 6h7C13.88 6 15 7.12 15 8.5v7c0 1.38-1.12 2.5-2.5 2.5h-7C4.12 18 3 16.88 3 15.5v-7zM16 9.8l3.7-2.66c.66-.48 1.3-.02 1.3.74v8.24c0 .76-.64 1.22-1.3.74L16 14.2V9.8z"/>
      </svg>
    ),
    accentColor: "#2D8CFF",
    description: "Transcribe meeting recordings & extract decisions",
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
