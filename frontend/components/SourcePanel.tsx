"use client";

import type { Source } from "@/hooks/useKairosChat";

interface SourcePanelProps {
  sources: Source[];
}

const SOURCE_STYLES: Record<
  string,
  { label: string; bg: string; text: string; icon: string }
> = {
  slack: {
    label: "Slack",
    bg: "bg-[#4a154b]",
    text: "text-[#e8b4f8]",
    icon: "#",
  },
  email: {
    label: "Email",
    bg: "bg-[#ea4335]/20",
    text: "text-[#ea4335]",
    icon: "@",
  },
  drive: {
    label: "Drive",
    bg: "bg-[#4285f4]/20",
    text: "text-[#4285f4]",
    icon: "D",
  },
  jira: {
    label: "Jira",
    bg: "bg-[#0052cc]/30",
    text: "text-[#5b8def]",
    icon: "J",
  },
  meeting: {
    label: "Meeting",
    bg: "bg-[#ff6b35]/20",
    text: "text-[#ff6b35]",
    icon: "M",
  },
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
      <span className="font-mono">{style.icon}</span>
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
      className="group block p-3 rounded-lg bg-[var(--surface)]/30 border border-[var(--border)] hover:border-indigo-500/40 hover:bg-[var(--surface-hover)]/70 transition-all duration-200 animate-[fadeIn_0.3s_ease-out]"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <SourceBadge source={source.source} />
        {source.date && (
          <span className="text-[10px] text-[var(--text-muted)] shrink-0">
            {formatDate(source.date)}
          </span>
        )}
      </div>
      <p className="text-[12px] text-[var(--text-primary)] leading-snug hover:text-[var(--accent)] transition-colors duration-200 line-clamp-3">
        {source.title}
      </p>
      {source.source_url && (
        <div className="mt-2 flex items-center gap-1 text-[10px] text-[var(--text-muted)] group-hover:text-indigo-400 transition-colors duration-200">
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
      <div className="w-12 h-12 rounded-full bg-[var(--surface-hover)] border border-[var(--border)] flex items-center justify-center">
        <svg
          className="w-5 h-5 text-[var(--text-muted)]"
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
        <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
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
    <div className="flex flex-col h-full bg-[var(--bg)] border-t border-[var(--border)]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between shrink-0 bg-[var(--surface)]">
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
          <span className="text-[11px] font-bold text-[var(--text-primary)] tracking-wider uppercase font-mono">Scanned Sources</span>
        </div>
        {sources.length > 0 && (
          <span className="text-[9px] font-mono font-bold text-[var(--text-primary)] bg-[var(--surface-hover)] border border-[var(--border)] px-1.5 py-0.5 rounded">
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
