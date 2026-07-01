"use client";

import React from "react";

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  hasWarning?: boolean;
  className?: string;
}

// ── Inline formatter ──────────────────────────────────────────────────────────
// Handles: **bold**, *italic*, `code`, [text](url)
function renderInline(text: string, keyPrefix: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /\*\*([^*]+)\*\*|\*([^*\n]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let k = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={`${keyPrefix}-t${k++}`}>{text.slice(lastIndex, match.index)}</span>);
    }
    if (match[1] !== undefined) {
      parts.push(
        <strong key={`${keyPrefix}-b${k++}`} className="font-semibold text-white">
          {match[1]}
        </strong>
      );
    } else if (match[2] !== undefined) {
      parts.push(
        <em key={`${keyPrefix}-i${k++}`} className="italic text-zinc-300">
          {match[2]}
        </em>
      );
    } else if (match[3] !== undefined) {
      parts.push(
        <code
          key={`${keyPrefix}-c${k++}`}
          className="font-mono text-[0.82em] bg-zinc-800/80 text-indigo-300 border border-zinc-700/60 px-1.5 py-0.5 rounded-md"
        >
          {match[3]}
        </code>
      );
    } else if (match[4] !== undefined && match[5] !== undefined) {
      parts.push(
        <a
          key={`${keyPrefix}-l${k++}`}
          href={match[5]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 decoration-indigo-500/40 hover:decoration-indigo-400 transition-colors break-all"
        >
          {match[4]}
        </a>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(<span key={`${keyPrefix}-t${k++}`}>{text.slice(lastIndex)}</span>);
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

// ── Block parser ──────────────────────────────────────────────────────────────
function parseBlocks(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const trimmed = raw.trim();

    // ── H2: ## heading ──────────────────────────────────────────────────────
    if (trimmed.startsWith("## ")) {
      elements.push(
        <div key={key++} className="flex items-center gap-3 mt-6 mb-2 first:mt-1">
          <h2 className="text-[14.5px] font-bold text-white tracking-tight shrink-0">
            {renderInline(trimmed.slice(3), `h2-${key}`)}
          </h2>
          <div className="flex-1 h-px bg-zinc-700/50" />
        </div>
      );
      i++;
      continue;
    }

    // ── H3: ### heading ─────────────────────────────────────────────────────
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={key++} className="text-[13px] font-semibold text-zinc-200 mt-4 mb-1.5 tracking-tight">
          {renderInline(trimmed.slice(4), `h3-${key}`)}
        </h3>
      );
      i++;
      continue;
    }

    // ── Bullet list: - item or * item or • item ──────────────────────────────
    if (trimmed.match(/^[-*•]\s+/)) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length && lines[i].trim().match(/^[-*•]\s+/)) {
        const content = lines[i].trim().replace(/^[-*•]\s+/, "");
        listItems.push(
          <li key={i} className="flex items-start gap-2.5">
            <span className="mt-[6px] w-1.5 h-1.5 rounded-full bg-indigo-500/80 shrink-0" />
            <span className="text-zinc-200 leading-[1.7]">
              {renderInline(content, `li-${key}-${i}`)}
            </span>
          </li>
        );
        i++;
      }
      elements.push(
        <ul key={key++} className="space-y-1.5 my-2.5 list-none">
          {listItems}
        </ul>
      );
      continue;
    }

    // ── Numbered list: 1. item ───────────────────────────────────────────────
    if (trimmed.match(/^\d+\.\s+/)) {
      const listItems: React.ReactNode[] = [];
      let num = 1;
      while (i < lines.length && lines[i].trim().match(/^\d+\.\s+/)) {
        const content = lines[i].trim().replace(/^\d+\.\s+/, "");
        listItems.push(
          <li key={i} className="flex items-start gap-3">
            <span className="text-[11px] font-bold text-indigo-400 mt-[5px] w-4 shrink-0 text-right">
              {num++}.
            </span>
            <span className="text-zinc-200 leading-[1.7]">
              {renderInline(content, `ol-${key}-${i}`)}
            </span>
          </li>
        );
        i++;
      }
      elements.push(
        <ol key={key++} className="space-y-1.5 my-2.5 list-none">
          {listItems}
        </ol>
      );
      continue;
    }

    // ── Blockquote: > text ───────────────────────────────────────────────────
    if (trimmed.startsWith("> ")) {
      const content = trimmed.slice(2);
      elements.push(
        <blockquote
          key={key++}
          className="border-l-2 border-indigo-500/60 pl-3.5 py-0.5 my-2 text-zinc-400 italic text-[13.5px]"
        >
          {renderInline(content, `bq-${key}`)}
        </blockquote>
      );
      i++;
      continue;
    }

    // ── Horizontal rule ──────────────────────────────────────────────────────
    if (trimmed === "---" || trimmed === "___" || trimmed === "***") {
      elements.push(
        <hr key={key++} className="border-zinc-700/50 my-4" />
      );
      i++;
      continue;
    }

    // ── Empty line → thin spacer ─────────────────────────────────────────────
    if (trimmed === "") {
      elements.push(<div key={key++} className="h-1.5" />);
      i++;
      continue;
    }

    // ── Regular paragraph ────────────────────────────────────────────────────
    elements.push(
      <p key={key++} className="text-[14px] text-zinc-200 leading-[1.75]">
        {renderInline(trimmed, `p-${key}`)}
      </p>
    );
    i++;
  }

  return elements;
}

// ── Main component ────────────────────────────────────────────────────────────
export default function StreamingText({
  text,
  isStreaming,
  hasWarning = false,
  className = "",
}: StreamingTextProps) {
  if (hasWarning) {
    return (
      <p className={`text-rose-400 font-medium leading-relaxed text-[14px] ${className}`}>
        {text}
        {isStreaming && <span className="stream-cursor" aria-hidden="true" />}
      </p>
    );
  }

  const blocks = parseBlocks(text);

  return (
    <div className={`kairos-md ${className}`}>
      {blocks}
      {isStreaming && (
        <span className="stream-cursor ml-0.5" aria-hidden="true" />
      )}
    </div>
  );
}

// ── Claude-style Thinking Indicator ──────────────────────────────────────────
export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 px-0.5 py-1">
      {/* Pulsing orb */}
      <div className="relative w-4 h-4 shrink-0">
        <span className="absolute inset-0 rounded-full bg-indigo-500/25 animate-ping" />
        <span className="absolute inset-[3px] rounded-full bg-indigo-400" />
      </div>

      {/* Label */}
      <span className="text-[12.5px] text-indigo-400 font-medium tracking-wide">
        Thinking
      </span>

      {/* Three bouncing dots */}
      <div className="flex items-center gap-[3px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="thinking-dot w-[5px] h-[5px] rounded-full bg-indigo-400/60 inline-block"
            style={{ animationDelay: `${i * 180}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
