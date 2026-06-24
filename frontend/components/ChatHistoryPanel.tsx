"use client";

import React, { useState } from "react";

interface Session {
  session_id: string;
  started: number;
  last_message: number;
  message_count: number;
  preview: string;
}

interface ChatHistoryPanelProps {
  sessions: Session[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

export function ChatHistoryPanel({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
}: ChatHistoryPanelProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSessions = sessions.filter((s) =>
    (s.preview || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="flex flex-col h-full bg-[var(--surface)] border-r border-[var(--border)] text-[var(--text-primary)] w-80 theme-transition">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)] flex items-center justify-between theme-transition">
        <h2 className="font-semibold text-sm tracking-wider uppercase flex items-center gap-2">
          <span>🧠</span> Conversational Memory
        </h2>
        <span className="text-[10px] bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/25 px-2.5 py-0.5 rounded-full font-mono font-medium">
          {sessions.length} sessions
        </span>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-[var(--border)]/40">
        <div className="relative">
          <input
            type="text"
            placeholder="Search past chats..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--border-focus)] transition-colors theme-transition"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="absolute right-3 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs transition-colors"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto space-y-1.5 p-2">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-8 text-[var(--text-muted)] text-sm">
            {searchTerm ? "No matching conversations" : "No past conversations"}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.session_id === activeSessionId;
            return (
              <div
                key={session.session_id}
                onClick={() => onSelectSession(session.session_id)}
                className={`group flex items-start justify-between p-3.5 rounded-xl cursor-pointer transition-all duration-200 border theme-transition ${
                  isActive
                    ? "bg-[var(--accent)]/10 border-[var(--accent)]/30 text-[var(--text-primary)] shadow-sm shadow-[var(--accent)]/5"
                    : "bg-transparent border-transparent hover:bg-[var(--surface-hover)] hover:border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                <div className="flex-1 min-w-0 pr-2">
                  <div className="flex items-center gap-1.5 justify-between mb-1.5">
                    <span className="text-[10px] text-[var(--text-muted)] font-medium font-mono">
                      {formatDate(session.last_message)}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono font-medium transition-colors theme-transition ${
                      isActive 
                        ? "bg-[var(--accent)]/20 text-[var(--accent)]" 
                        : "bg-[var(--bg)] text-[var(--text-muted)] border border-[var(--border)] group-hover:bg-[var(--surface)] group-hover:text-[var(--text-primary)]"
                    }`}>
                      {session.message_count} msg
                    </span>
                  </div>
                  <p className="text-sm font-medium truncate leading-snug">
                    {session.preview || "New Session"}
                  </p>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("Delete this conversation turn history?")) {
                      onDeleteSession(session.session_id);
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-[var(--text-muted)] hover:text-red-500 rounded transition-all duration-150 shrink-0"
                  title="Delete session"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
