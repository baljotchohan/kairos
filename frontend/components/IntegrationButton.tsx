"use client";

import React, { useState } from "react";

interface ServiceConfig {
  name: string;
  icon: React.ReactNode;
  accentColor: string;
  description: string;
  manualKeyConnect?: boolean;
  keyPlaceholder?: string;
  keyHelpUrl?: string;
  keyHelpLabel?: string;
  /** Shows a secondary button (alongside Disconnect) once connected, that
   * re-runs the same OAuth popup flow — for services where access is
   * granted incrementally (e.g. Notion's page picker) rather than all at
   * once, so a user can grant access to more content without disconnecting. */
  manageAccessLabel?: string;
  /** Short explainer shown under the connected state, for services where
   * "connected" doesn't mean "sees everything" — sets expectations about
   * how to grant more access (via manageAccessLabel here, or directly in
   * the source app for services we can't re-trigger, like Slack channels). */
  manageAccessHint?: string;
}

const SERVICE_CONFIG: Record<string, ServiceConfig> = {
  github: {
    name: "GitHub",
    icon: (
      <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#ffffff" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
      </svg>
    ),
    accentColor: "#181717",
    description: "Read pull requests, issues, and review discussions",
  },
  notion: {
    name: "Notion",
    icon: (
      <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#ffffff" xmlns="http://www.w3.org/2000/svg">
        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z"/>
      </svg>
    ),
    accentColor: "#37352f",
    description: "Read Notion pages and databases, extract decisions",
    manageAccessLabel: "Add pages",
    manageAccessHint: "Only pages you've explicitly shared are visible to KAIROS. Click \"Add pages\" anytime to share more from Notion's picker — nothing already shared is affected.",
  },
  slack: {
    name: "Slack",
    icon: (<svg viewBox="0 0 24 24" className="w-6 h-6"><path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/><path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/><path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/><path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.315A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.522 2.523h-6.315z" fill="#ECB22E"/></svg>),
    accentColor: "#36C5F0",
    description: "Read channel messages and extract decision threads",
    manageAccessHint: "Public channels are already visible. For private channels, invite @KAIROS to them directly in Slack — there's no picker here since Slack manages private-channel access from inside the workspace, not via OAuth.",
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
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const cfg = SERVICE_CONFIG[service];

  // ── Notion: manual key submit ──────────────────────────────────────────────
  const handleNotionSubmit = async () => {
    if (!apiKey.trim()) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/oauth/notion/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Connection failed");

      setShowKeyInput(false);
      setApiKey("");
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setIsLoading(false);
    }
  };

  // ── Standard OAuth connect ─────────────────────────────────────────────────
  const handleConnect = async () => {
    if (cfg.manualKeyConnect) {
      setShowKeyInput(true);
      setError(null);
      return;
    }

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

      const timer = setInterval(() => {
        if (popup.closed) {
          clearInterval(timer);
          setTimeout(() => { onRefresh(); setIsLoading(false); }, 800);
        }
      }, 500);

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
      className="rounded-xl border transition-all theme-transition"
      style={{
        borderColor: isConnected ? "rgba(34,197,94,0.4)" : showKeyInput ? `${cfg.accentColor}50` : "rgb(var(--border))",
        background: isConnected ? "rgba(34,197,94,0.04)" : "rgb(var(--surface))",
      }}
    >
      {/* Main row */}
      <div className="flex items-center justify-between p-5">
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
                <span className="text-[rgb(var(--text-muted))]">as</span>{" "}
                <span className="font-semibold text-[rgb(var(--text-primary))]">{serviceName}</span>
                {formattedDate && (
                  <span className="text-[rgb(var(--text-muted))]/80 ml-2">· {formattedDate}</span>
                )}
              </p>
            )}
            {isConnected && cfg.manageAccessHint && (
              <p className="text-[10px] text-[rgb(var(--text-muted))]/70 mt-1 leading-relaxed">
                {cfg.manageAccessHint}
              </p>
            )}
            {error && (
              <p className="text-[10px] text-rose-400 mt-1">⚠ {error}</p>
            )}
          </div>
        </div>

        {/* Right: action button(s) */}
        <div className="shrink-0 ml-4">
          {isConnected ? (
            <div className="flex items-center gap-2">
              {cfg.manageAccessLabel && (
                <button
                  onClick={handleConnect}
                  disabled={isLoading}
                  className="px-3 py-1.5 rounded-lg border border-[rgb(var(--border))] text-[rgb(var(--text-primary))]/80 hover:bg-[rgb(var(--surface-hover))] text-[11px] font-semibold disabled:opacity-40 transition-all whitespace-nowrap"
                >
                  {isLoading ? "…" : cfg.manageAccessLabel}
                </button>
              )}
              <button
                onClick={handleDisconnect}
                disabled={isLoading}
                className="px-3 py-1.5 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 text-[11px] font-semibold disabled:opacity-40 transition-all whitespace-nowrap"
              >
                {isLoading ? "…" : "Disconnect"}
              </button>
            </div>
          ) : showKeyInput ? (
            <button
              onClick={() => { setShowKeyInput(false); setApiKey(""); setError(null); }}
              className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] text-[11px] transition-colors"
            >
              Cancel
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

      {/* Notion inline key input — shown when user clicks Connect */}
      {showKeyInput && cfg.manualKeyConnect && (
        <div className="px-5 pb-5 pt-0">
          <div className="border-t border-[rgb(var(--border))] pt-4 space-y-3">
            <p className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">
              Create an integration at{" "}
              <a
                href={cfg.keyHelpUrl}
                target="_blank"
                rel="noreferrer"
                className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2"
              >
                {cfg.keyHelpLabel}
              </a>
              , copy the <span className="text-[rgb(var(--text-primary))]/90 font-mono">Internal Integration Secret</span>, then paste it below.
              Share your Notion pages with the integration via the page&apos;s{" "}
              <span className="text-[rgb(var(--text-primary))]/90">… → Connections</span> menu.
            </p>

            <div className="flex gap-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleNotionSubmit()}
                placeholder={cfg.keyPlaceholder}
                autoFocus
                className="flex-1 bg-[rgb(var(--surface-hover))] border border-[rgb(var(--border))] rounded-lg px-3 py-2 text-[11px] font-mono text-[rgb(var(--text-primary))]/90 placeholder-zinc-500 focus:outline-none focus:border-[rgb(var(--border-focus))] transition-colors"
              />
              <button
                onClick={handleNotionSubmit}
                disabled={isLoading || !apiKey.trim()}
                className="px-4 py-2 rounded-lg text-white text-[11px] font-semibold disabled:opacity-40 transition-all hover:opacity-90"
                style={{ background: cfg.accentColor }}
              >
                {isLoading ? "…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
