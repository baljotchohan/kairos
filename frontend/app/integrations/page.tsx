"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import IntegrationGrid from "@/components/IntegrationGrid";

export default function IntegrationsPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/dashboard");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex h-screen w-full bg-[rgb(var(--bg))] items-center justify-center font-mono text-xs text-[rgb(var(--text-muted))] theme-transition">
        <span className="animate-pulse">Loading…</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] text-[rgb(var(--text-primary))] p-8 theme-transition">
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-1.5 text-[10px] font-mono text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] mb-6 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to KAIROS
          </button>

          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="font-bold text-white text-sm">K</span>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Connect Your Apps</h1>
              <p className="text-[11px] text-[rgb(var(--text-muted))] font-mono">KAIROS · Integrations</p>
            </div>
          </div>
          <p className="text-xs text-[rgb(var(--text-muted))] mt-3 leading-relaxed">
            Authorize KAIROS to read from your work tools. One-click OAuth — no manual token setup.
            Tokens are stored securely and tied to your account.
          </p>
        </div>

        {/* Integration grid */}
        <IntegrationGrid token={token} />

        {/* Signed in as */}
        <div className="mt-8 pt-4 border-t border-[rgb(var(--border))] text-[10px] font-mono text-[rgb(var(--text-muted))]/80 text-center">
          Signed in as {user.email || user.displayName || "Guest"} · {" "}
          <button onClick={() => router.push("/dashboard")} className="hover:text-[rgb(var(--text-primary))] transition-colors">
            Return to dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
