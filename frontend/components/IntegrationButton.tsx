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
      <svg viewBox="0 0 48 48" className="w-7 h-7">
        <rect width="48" height="48" rx="6" fill="white"/>
        <path fill="#4caf50" d="M45 16.2l-5 2.75-5 4.75V40h7a3 3 0 003-3V16.2z"/>
        <path fill="#1e88e5" d="M3 16.2l3.7 2.75L13 23.7V40H6a3 3 0 01-3-3V16.2z"/>
        <polygon fill="#e53935" points="35,11.2 24,19.45 13,11.2 12,8 24,16.25 36,8"/>
        <path fill="#c62828" d="M3 12.298V16.2l10 7.5V11.2L9.24 9.27C8.009 8.394 6.476 8.313 5.18 8.91 3.7 9.6 3 11.25 3 12.298z"/>
        <path fill="#fbc02d" d="M45 12.298V16.2l-10 7.5V11.2l3.76-1.93c1.231-.876 2.764-.957 4.06-.36 1.48.69 2.18 2.34 2.18 3.388z"/>
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
      <svg viewBox="0 0 32 32" className="w-7 h-7">
        <defs>
          <linearGradient id="jbg-ib" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#2684FF"/>
            <stop offset="100%" stopColor="#0052CC"/>
          </linearGradient>
          <linearGradient id="jfg-ib" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.9"/>
            <stop offset="100%" stopColor="#cfe2ff"/>
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="6" fill="url(#jbg-ib)"/>
        <path d="M15.43 15.35H4.67a6.96 6.96 0 006.97 6.95h2.84V25.2a6.95 6.95 0 006.96 6.95v-15.4a1.34 1.34 0 00-1.34-1.34z" fill="url(#jfg-ib)" transform="scale(0.87) translate(1.8 -0.5)"/>
        <path d="M23.06 7.68H12.3a6.96 6.96 0 006.95 6.96h2.84v2.9a6.96 6.96 0 006.96 6.95V9.02a1.34 1.34 0 00-1.34-1.34z" fill="url(#jfg-ib)" transform="scale(0.87) translate(1.8 -0.5)" opacity="0.85"/>
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
