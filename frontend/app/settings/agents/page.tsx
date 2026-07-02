"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

interface Persona {
  agent_key: string;
  display_name: string;
  group: string;
  tone_preset: string;
  is_default: boolean;
}

const TONE_PREVIEWS: Record<string, string> = {
  professional: "Based on the retrieved decisions, the team adopted this approach in Q3 2022 after weighing two alternatives.",
  concise: "Decided Q3 2022. Two alternatives considered. Chosen for hiring pool size.",
  analyst: "Signal: decision made Q3 2022. Confidence: high (explicit thread). Risk noted: vendor lock-in.",
  custom: "This agent's tone has been customized by you.",
};

const GROUP_ORDER = ["Extraction Agents", "Reasoning", "Other"];

export default function AgentPersonasPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [tonePresets, setTonePresets] = useState<string[]>(["professional", "concise", "analyst", "custom"]);
  const [drafts, setDrafts] = useState<Record<string, { display_name: string; tone_preset: string }>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/dashboard");
    }
  }, [loading, user, router]);

  const fetchPersonas = useCallback(async () => {
    if (!token) {
      setIsFetching(false);
      return;
    }
    setIsFetching(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/agents", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data = await res.json();
      setPersonas(data.agents || []);
      setTonePresets(data.tone_presets || tonePresets);
      const nextDrafts: Record<string, { display_name: string; tone_preset: string }> = {};
      for (const p of data.agents || []) {
        nextDrafts[p.agent_key] = { display_name: p.display_name, tone_preset: p.tone_preset };
      }
      setDrafts(nextDrafts);
    } catch (e) {
      setError("Could not load agent personas — backend may be unreachable.");
    } finally {
      setIsFetching(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    fetchPersonas();
  }, [fetchPersonas]);

  const save = async (agentKey: string) => {
    if (!token) return;
    const draft = drafts[agentKey];
    if (!draft) return;
    setSavingKey(agentKey);
    setError(null);
    try {
      const res = await fetch(`/api/v1/agents/${agentKey}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ display_name: draft.display_name, tone_preset: draft.tone_preset }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const updated: Persona = await res.json();
      setPersonas((prev) => prev.map((p) => (p.agent_key === agentKey ? updated : p)));
    } catch (e) {
      setError(`Failed to save ${agentKey} — try again.`);
    } finally {
      setSavingKey(null);
    }
  };

  const reset = async (agentKey: string) => {
    if (!token) return;
    setSavingKey(agentKey);
    setError(null);
    try {
      const res = await fetch(`/api/v1/agents/${agentKey}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const defaults: Persona = await res.json();
      setPersonas((prev) => prev.map((p) => (p.agent_key === agentKey ? defaults : p)));
      setDrafts((prev) => ({ ...prev, [agentKey]: { display_name: defaults.display_name, tone_preset: defaults.tone_preset } }));
    } catch (e) {
      setError(`Failed to reset ${agentKey} — try again.`);
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen w-full bg-[rgb(var(--bg))] items-center justify-center font-mono text-xs text-[rgb(var(--text-muted))] theme-transition">
        <span className="animate-pulse">Loading…</span>
      </div>
    );
  }

  if (!user) return null;

  const grouped: Record<string, Persona[]> = {};
  for (const p of personas) {
    grouped[p.group] = grouped[p.group] || [];
    grouped[p.group].push(p);
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
              <h1 className="text-xl font-bold tracking-tight">Agent Personas</h1>
              <p className="text-[11px] text-[rgb(var(--text-muted))] font-mono">KAIROS · Settings</p>
            </div>
          </div>
          <p className="text-xs text-[rgb(var(--text-muted))] mt-3 leading-relaxed">
            Rename any KAIROS agent and adjust its tone. This only changes how it presents
            answers to you — extraction and classification logic never changes.
          </p>
        </div>

        {error && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[11px] font-mono">
            {error}
          </div>
        )}

        {isFetching ? (
          <p className="text-xs text-[rgb(var(--text-muted))] font-mono animate-pulse">Loading agents…</p>
        ) : (
          <div className="space-y-8">
            {GROUP_ORDER.filter((g) => grouped[g]?.length).map((group) => (
              <div key={group} className="space-y-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[rgb(var(--text-muted))]">{group}</h2>
                {grouped[group].map((p) => {
                  const draft = drafts[p.agent_key] || { display_name: p.display_name, tone_preset: p.tone_preset };
                  const dirty = draft.display_name !== p.display_name || draft.tone_preset !== p.tone_preset;
                  return (
                    <div
                      key={p.agent_key}
                      className="p-4 rounded-2xl border border-[rgb(var(--border))] bg-[rgb(var(--surface-hover))]/40 flex flex-col gap-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex-1">
                          <label className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase tracking-wider block mb-1">
                            Display name · {p.agent_key}
                          </label>
                          <input
                            type="text"
                            value={draft.display_name}
                            maxLength={80}
                            onChange={(e) =>
                              setDrafts((prev) => ({
                                ...prev,
                                [p.agent_key]: { ...draft, display_name: e.target.value },
                              }))
                            }
                            className="w-full bg-[rgb(var(--bg))] border border-[rgb(var(--border))] rounded-lg px-3 py-1.5 text-sm text-[rgb(var(--text-primary))]/90 focus:outline-none focus:border-indigo-500 transition-colors"
                          />
                        </div>
                        <div className="w-36">
                          <label className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase tracking-wider block mb-1">
                            Tone
                          </label>
                          <select
                            value={draft.tone_preset}
                            onChange={(e) =>
                              setDrafts((prev) => ({
                                ...prev,
                                [p.agent_key]: { ...draft, tone_preset: e.target.value },
                              }))
                            }
                            className="w-full bg-[rgb(var(--bg))] border border-[rgb(var(--border))] rounded-lg px-2 py-1.5 text-sm text-[rgb(var(--text-primary))]/90 focus:outline-none focus:border-indigo-500 transition-colors"
                          >
                            {tonePresets.map((t) => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Live preview */}
                      <div className="px-3 py-2 rounded-lg bg-[rgb(var(--bg))]/60 border border-[rgb(var(--border))]/70">
                        <span className="text-[9px] font-mono text-[rgb(var(--text-muted))]/80 uppercase tracking-wider block mb-1">
                          Preview — as &ldquo;{draft.display_name}&rdquo;
                        </span>
                        <p className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed italic">
                          &ldquo;{TONE_PREVIEWS[draft.tone_preset] || TONE_PREVIEWS.professional}&rdquo;
                        </p>
                      </div>

                      <div className="flex items-center gap-2 justify-end">
                        {!p.is_default && (
                          <button
                            onClick={() => reset(p.agent_key)}
                            disabled={savingKey === p.agent_key}
                            className="text-[10px] font-mono text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] px-2 py-1 transition-colors disabled:opacity-40"
                          >
                            Reset to default
                          </button>
                        )}
                        <button
                          onClick={() => save(p.agent_key)}
                          disabled={!dirty || savingKey === p.agent_key}
                          className="text-[10px] font-mono px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-[rgb(var(--surface-hover))] disabled:text-[rgb(var(--text-muted))] text-white transition-colors"
                        >
                          {savingKey === p.agent_key ? "Saving…" : "Save"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        <div className="mt-8 pt-4 border-t border-[rgb(var(--border))] text-[10px] font-mono text-[rgb(var(--text-muted))]/80 text-center">
          Signed in as {user.email || user.displayName || "Guest"} ·{" "}
          <button onClick={() => router.push("/dashboard")} className="hover:text-[rgb(var(--text-primary))] transition-colors">
            Return to dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
