"use client";

import type { Source } from "@/hooks/useKairosChat";
import React from "react";

interface SourcePanelProps {
  sources: Source[];
}

const GMAIL_ICON = (
  <svg viewBox="52 42 88 66" className="w-3 h-3">
    <path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>
    <path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>
    <path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2"/>
    <path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92"/>
    <path fill="#c5221f" d="M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2"/>
  </svg>
);

const SOURCE_STYLES: Record<
  string,
  { label: string; bg: string; text: string; icon: React.ReactNode }
> = {
  slack: {
    label: "Slack",
    bg: "bg-[#4a154b]",
    text: "text-[#e8b4f8]",
    icon: (<svg viewBox="0 0 24 24" className="w-3 h-3"><path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/><path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/><path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/><path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.315A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.522 2.523h-6.315z" fill="#ECB22E"/></svg>),
  },
  email: { label: "Email", bg: "bg-[#ea4335]/20", text: "text-[#ea4335]", icon: GMAIL_ICON },
  gmail: { label: "Gmail", bg: "bg-[#ea4335]/20", text: "text-[#ea4335]", icon: GMAIL_ICON },
  drive: {
    label: "Drive",
    bg: "bg-[#4285f4]/20",
    text: "text-[#4285f4]",
    icon: (<svg viewBox="0 0 24 24" className="w-3 h-3"><path d="M7.71 0l7.065 12.25H24L16.93 0z" fill="#0066DA"/><path d="M16.29 0H7.71l-7.065 12.25 4.36 7.56L12.07 7.56z" fill="#00AC47"/><path d="M1.005 19.81L5.005 12.25H14.775L18.995 19.81z" fill="#EA4335"/><path d="M12 16.64l-4.29 7.44h8.58z" fill="#00832D"/><path d="M16.93 0L24 12.25l-4.36 7.56L12.07 7.56z" fill="#2684FC"/><path d="M14.775 12.25H5.005l-4 7.56h9.77z" fill="#FFBA00"/></svg>),
  },
  jira: {
    label: "Jira",
    bg: "bg-[#0052cc]/30",
    text: "text-[#5b8def]",
    icon: (
      <svg viewBox="0 0 24 24" className="w-3 h-3">
        <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z" fill="#0052CC"/>
        <path d="M17.294 5.757H5.723a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z" fill="#0065FF"/>
        <path d="M23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0z" fill="#4C9AFF"/>
      </svg>
    ),
  },
  meeting: {
    label: "Meeting",
    bg: "bg-[#2D8CFF]/20",
    text: "text-[#2D8CFF]",
    icon: (
      <svg viewBox="0 0 24 24" className="w-3 h-3">
        <rect x="0" y="0" width="24" height="24" rx="5" fill="#2D8CFF"/>
        <path d="M6 8a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8zm12 1.5a.5.5 0 0 0-.8.4v4.2a.5.5 0 0 0 .8.4l3.5 2.5a.5.5 0 0 0 .7-.4V7.8a.5.5 0 0 0-.7-.4l-3.5 2.5z" fill="#ffffff"/>
      </svg>
    ),
  },
  zoom: {
    label: "Zoom",
    bg: "bg-[#2D8CFF]/20",
    text: "text-[#2D8CFF]",
    icon: (
      <svg viewBox="0 0 24 24" className="w-3 h-3" fill="#2D8CFF">
        <path d="M3 8.5C3 7.12 4.12 6 5.5 6h7C13.88 6 15 7.12 15 8.5v7c0 1.38-1.12 2.5-2.5 2.5h-7C4.12 18 3 16.88 3 15.5v-7zM16 9.8l3.7-2.66c.66-.48 1.3-.02 1.3.74v8.24c0 .76-.64 1.22-1.3.74L16 14.2V9.8z"/>
      </svg>
    ),
  },
  github: {
    label: "GitHub",
    bg: "bg-[#181717]/60",
    text: "text-[#e8e8e6]",
    icon: (
      <svg viewBox="0 0 24 24" className="w-3 h-3" fill="#e8e8e6">
        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
      </svg>
    ),
  },
  notion: {
    label: "Notion",
    bg: "bg-[#37352f]/60",
    text: "text-[#e8e8e6]",
    icon: (
      <svg viewBox="0 0 24 24" className="w-3 h-3" fill="#e8e8e6">
        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z"/>
      </svg>
    ),
  },
  notion_page: { label: "Notion", bg: "bg-[#37352f]/60", text: "text-[#e8e8e6]", icon: (<svg viewBox="0 0 24 24" className="w-3 h-3" fill="#e8e8e6"><path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z"/></svg>) },
  notion_db: { label: "Notion DB", bg: "bg-[#37352f]/60", text: "text-[#e8e8e6]", icon: (<svg viewBox="0 0 24 24" className="w-3 h-3" fill="#e8e8e6"><path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z"/></svg>) },
};

function formatDate(raw: string): string {
  if (!raw) return "";
  try {
    const d = new Date(raw);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return raw;
  }
}

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source.toLowerCase()] ?? {
    label: source,
    bg: "bg-[#2a2a2a]",
    text: "text-[#9ca3af]",
    icon: "?",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${style.bg} ${style.text}`}
    >
      {style.icon}
      {style.label}
    </span>
  );
}

function SourceCard({ source }: { source: Source }) {
  return (
    <a
      href={source.source_url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="group block p-3 rounded-lg bg-[rgb(var(--surface))]/30 border border-[rgb(var(--border))] hover:border-indigo-500/40 hover:bg-[rgb(var(--surface-hover))]/70 transition-all duration-200 animate-[fadeIn_0.3s_ease-out] theme-transition"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <SourceBadge source={source.source} />
        {source.date && (
          <span className="text-[10px] text-[rgb(var(--text-muted))] shrink-0">
            {formatDate(source.date)}
          </span>
        )}
      </div>
      <p className="text-[12px] text-[rgb(var(--text-primary))] leading-snug hover:text-[rgb(var(--accent))] transition-colors duration-200 line-clamp-3">
        {source.title}
      </p>
      {source.source_url && (
        <div className="mt-2 flex items-center gap-1 text-[10px] text-[rgb(var(--text-muted))] group-hover:text-indigo-400 transition-colors duration-200">
          <svg
            className="w-3 h-3 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          <span className="truncate">Open source</span>
        </div>
      )}
    </a>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-6 text-center">
      <div className="w-12 h-12 rounded-full bg-[rgb(var(--surface-hover))] border border-[rgb(var(--border))] flex items-center justify-center">
        <svg
          className="w-5 h-5 text-[rgb(var(--text-muted))]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
      </div>
      <div>
        <p className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">
          Ask a question to see
          <br />
          decision sources here
        </p>
      </div>
    </div>
  );
}

export default function SourcePanel({ sources = [] }: SourcePanelProps) {
  return (
    <div className="flex flex-col h-full bg-[rgb(var(--bg))] border-t border-[rgb(var(--border))] theme-transition">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[rgb(var(--border))] flex items-center justify-between shrink-0 bg-[rgb(var(--surface))] theme-transition">
        <div className="flex items-center gap-2">
          <svg
            className="w-3.5 h-3.5 text-indigo-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"
            />
          </svg>
          <span className="text-[11px] font-bold text-[rgb(var(--text-primary))] tracking-wider uppercase font-mono">Scanned Sources</span>
        </div>
        {sources.length > 0 && (
          <span className="text-[9px] font-mono font-bold text-[rgb(var(--text-primary))] bg-[rgb(var(--surface-hover))] border border-[rgb(var(--border))] px-1.5 py-0.5 rounded">
            {sources.length}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {sources.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="p-3 flex flex-col gap-2">
            {sources.map((source) => (
              <SourceCard key={source.id} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
