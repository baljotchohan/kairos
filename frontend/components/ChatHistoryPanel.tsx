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
  onClose?: () => void;
}

export function ChatHistoryPanel({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onClose,
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
    <div className="flex flex-col h-full bg-[rgb(var(--surface))] border-r border-[rgb(var(--border))]/60 text-[rgb(var(--text-primary))] w-full theme-transition">
      {/* Header */}
      <div className="p-4 border-b border-[rgb(var(--border))]/40 flex items-center justify-between theme-transition">
        <h2 className="font-bold text-xs tracking-wider uppercase flex items-center gap-2">
          <span>🧠</span> Memory Logs
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-[10px] bg-[rgb(var(--accent))]/10 text-[rgb(var(--accent))] border border-[rgb(var(--accent))]/25 px-2.5 py-0.5 rounded-full font-mono font-bold">
            {sessions.length} turns
          </span>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--surface-hover))]/80 transition-all"
              title="Close history panel"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-[rgb(var(--border))]/30">
        <div className="relative">
          <input
            type="text"
            placeholder="Search past logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[rgb(var(--bg))] border border-[rgb(var(--border))]/80 rounded-xl px-3 py-2 text-xs text-[rgb(var(--text-primary))] placeholder-zinc-500 focus:outline-none focus:border-[rgb(var(--border-focus))] transition-colors"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="absolute right-3 top-2 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] text-xs font-bold"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto space-y-1 p-2">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-8 text-[rgb(var(--text-muted))] text-xs font-mono">
            {searchTerm ? "No matching sessions" : "No past sessions"}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.session_id === activeSessionId;
            return (
              <div
                key={session.session_id}
                onClick={() => onSelectSession(session.session_id)}
                className={`group flex items-start justify-between p-3 rounded-xl cursor-pointer transition-all duration-150 border theme-transition ${
                  isActive
                    ? "bg-[rgb(var(--accent))]/10 border-[rgb(var(--accent))]/30 text-[rgb(var(--text-primary))] shadow-sm"
                    : "bg-transparent border-transparent hover:bg-[rgb(var(--surface-hover))]/60 hover:border-[rgb(var(--border))]/80 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                }`}
              >
                <div className="flex-1 min-w-0 pr-2">
                  <div className="flex items-center gap-1.5 justify-between mb-1">
                    <span className="text-[9px] text-[rgb(var(--text-muted))] font-bold font-mono">
                      {formatDate(session.last_message)}
                    </span>
                    <span className={`text-[8.5px] px-1.5 py-0.5 rounded-md font-mono font-bold transition-colors ${
                      isActive 
                        ? "bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))]" 
                        : "bg-[rgb(var(--bg))] text-[rgb(var(--text-muted))] border border-[rgb(var(--border))]/80 group-hover:bg-[rgb(var(--surface))] group-hover:text-[rgb(var(--text-primary))]"
                    }`}>
                      {session.message_count} msg
                    </span>
                  </div>
                  <p className="text-xs font-semibold truncate leading-normal">
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
                  className="opacity-0 group-hover:opacity-100 p-1 text-[rgb(var(--text-muted))] hover:text-rose-500 rounded transition-all shrink-0"
                  title="Delete session"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="13"
                    height="13"
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
