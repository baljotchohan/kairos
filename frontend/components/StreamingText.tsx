"use client";

import React from "react";

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  hasWarning?: boolean;
  className?: string;
}

/**
 * Renders text with markdown-style bold (**text**), inline code (`code`),
 * and a blinking cursor while streaming.
 */
function parseSegments(
  text: string
): { type: "text" | "bold" | "code"; content: string }[] {
  const segments: { type: "text" | "bold" | "code"; content: string }[] = [];
  // Match **bold** and `code`
  const regex = /\*\*([^*]+)\*\*|`([^`]+)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: "text",
        content: text.slice(lastIndex, match.index),
      });
    }
    if (match[1] !== undefined) {
      segments.push({ type: "bold", content: match[1] });
    } else if (match[2] !== undefined) {
      segments.push({ type: "code", content: match[2] });
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({ type: "text", content: text.slice(lastIndex) });
  }

  return segments;
}

export default function StreamingText({
  text,
  isStreaming,
  hasWarning = false,
  className = "",
}: StreamingTextProps) {
  const segments = parseSegments(text);

  return (
    <span
      className={`kairos-prose leading-relaxed whitespace-pre-wrap break-words ${
        hasWarning ? "text-rose-500 font-medium" : "text-[rgb(var(--text-primary))]"
      } ${className}`}
    >
      {segments.map((seg, i) => {
        if (seg.type === "bold") {
          return (
            <strong key={i} className="font-semibold text-[rgb(var(--text-primary))]">
              {seg.content}
            </strong>
          );
        }
        if (seg.type === "code") {
          return (
            <code
              key={i}
              className="font-mono text-[0.85em] bg-[rgb(var(--surface-hover))] text-[rgb(var(--accent))] border border-[rgb(var(--border))]/80 px-1.5 py-0.5 rounded"
            >
              {seg.content}
            </code>
          );
        }
        return <span key={i}>{seg.content}</span>;
      })}
      {isStreaming && <span className="stream-cursor" aria-hidden="true" />}
    </span>
  );
}

/**
 * Thinking indicator — shown before any tokens arrive.
 */
export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <span className="text-slate-500 text-xs font-semibold uppercase tracking-wider mr-1.5">Analyzing Memory</span>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="thinking-dot w-1 h-1 rounded-full bg-indigo-500 inline-block"
          style={{ animationDelay: `${i * 200}ms` }}
        />
      ))}
    </div>
  );
}
