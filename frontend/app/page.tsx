"use client";

/**
 * KAIROS — Landing page (the marketing layer in front of the dashboard).
 *
 * Lightweight 3D: a canvas decision-graph constellation in the hero, CSS
 * perspective tilt cards, gradient glows, and IntersectionObserver scroll
 * reveals — no heavy WebGL deps, so it stays fast on a judge's laptop.
 * "Enter KAIROS" routes into /dashboard, which owns sign-in.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import KairosLogo from "@/components/KairosLogo";

/* ── Scroll-reveal hook ──────────────────────────────────────────────────── */
function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? "translateY(0)" : "translateY(28px)",
        transition: `opacity .7s cubic-bezier(.16,1,.3,1) ${delay}ms, transform .7s cubic-bezier(.16,1,.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/* ── 3D tilt card ────────────────────────────────────────────────────────── */
function TiltCard({
  children,
  className = "",
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState({ rx: 0, ry: 0 });

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    setT({ rx: -py * 8, ry: px * 10 });
  };

  return (
    <div style={{ perspective: 900 }}>
      <div
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={() => setT({ rx: 0, ry: 0 })}
        className={className}
        style={{
          transform: `rotateX(${t.rx}deg) rotateY(${t.ry}deg)`,
          transformStyle: "preserve-3d",
          transition: "transform .25s cubic-bezier(.22,1,.36,1)",
          ...style,
        }}
      >
        {children}
      </div>
    </div>
  );
}

/* ── Full-page background constellation (side strips, scrolls with page) ─── */
// Colors shift as you scroll through sections: violet → purple → indigo → blue → sky
const SECTION_COLORS = [
  { r: 139, g: 92,  b: 246 }, // violet  (hero)
  { r: 168, g: 85,  b: 247 }, // purple  (problem)
  { r: 99,  g: 102, b: 241 }, // indigo  (agents)
  { r: 59,  g: 130, b: 246 }, // blue    (connectors)
  { r: 56,  g: 189, b: 248 }, // sky     (mcp / footer)
];

function lerpColor(a: typeof SECTION_COLORS[0], b: typeof SECTION_COLORS[0], t: number) {
  return {
    r: Math.round(a.r + (b.r - a.r) * t),
    g: Math.round(a.g + (b.g - a.g) * t),
    b: Math.round(a.b + (b.b - a.b) * t),
  };
}

function sectionColor(y: number, totalH: number) {
  if (!totalH) return SECTION_COLORS[0];
  const pct = Math.max(0, Math.min(1, y / totalH)) * (SECTION_COLORS.length - 1);
  const i = Math.floor(pct);
  const t = pct - i;
  const a = SECTION_COLORS[Math.min(i, SECTION_COLORS.length - 1)];
  const b = SECTION_COLORS[Math.min(i + 1, SECTION_COLORS.length - 1)];
  return lerpColor(a, b, t);
}

function SiteBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let w = 0, h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    type BgNode = { x: number; y: number; vx: number; vy: number; r: number; side: "L" | "R" };
    let nodes: BgNode[] = [];

    const resize = () => {
      w = window.innerWidth;
      // Use full document height so nodes span the whole page
      h = Math.max(document.documentElement.scrollHeight, window.innerHeight);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const strip = w * 0.17;
      const perSide = Math.min(55, Math.floor(h / 75));
      nodes = [
        ...Array.from({ length: perSide }, () => ({
          x: Math.random() * strip,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.2,
          vy: (Math.random() - 0.5) * 0.2,
          r: Math.random() * 1.6 + 0.9,
          side: "L" as const,
        })),
        ...Array.from({ length: perSide }, () => ({
          x: w - strip + Math.random() * strip,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.2,
          vy: (Math.random() - 0.5) * 0.2,
          r: Math.random() * 1.6 + 0.9,
          side: "R" as const,
        })),
      ];
    };

    const draw = () => {
      if (!w || !h) { raf = requestAnimationFrame(draw); return; }
      ctx.clearRect(0, 0, w, h);
      const strip = w * 0.17;
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.side === "L") {
          if (n.x < 0) n.vx = Math.abs(n.vx);
          if (n.x > strip) n.vx = -Math.abs(n.vx);
        } else {
          if (n.x < w - strip) n.vx = Math.abs(n.vx);
          if (n.x > w) n.vx = -Math.abs(n.vx);
        }
        if (n.y < 0 || n.y > h) n.vy *= -1;
      }
      // edges — color by midpoint Y position
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          if (a.side !== b.side) continue;
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 155) {
            const c = sectionColor((a.y + b.y) / 2, h);
            const op = (1 - d / 155) * 0.6;
            ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${op})`;
            ctx.lineWidth = 0.85;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      // nodes — brighter, color by Y
      for (const n of nodes) {
        const c = sectionColor(n.y, h);
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},0.72)`;
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };

    // Wait one frame so the DOM has rendered and scrollHeight is accurate
    requestAnimationFrame(() => { resize(); draw(); });
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{
        zIndex: 1,
        mixBlendMode: "screen",
        // Hard-clip: only side strips visible, center is always transparent
        maskImage:
          "linear-gradient(to right, black 0%, black 14%, transparent 20%, transparent 80%, black 86%, black 100%)",
        WebkitMaskImage:
          "linear-gradient(to right, black 0%, black 14%, transparent 20%, transparent 80%, black 86%, black 100%)",
      }}
    />
  );
}

/* ── Cursor glow ─────────────────────────────────────────────────────────── */
function CursorGlow() {
  const [pos, setPos] = useState({ x: -999, y: -999 });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
      if (!visible) setVisible(true);
    };
    const onLeave = () => setVisible(false);
    window.addEventListener("mousemove", onMove);
    document.documentElement.addEventListener("mouseleave", onLeave);
    return () => {
      window.removeEventListener("mousemove", onMove);
      document.documentElement.removeEventListener("mouseleave", onLeave);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="pointer-events-none fixed z-[9998]"
      style={{
        opacity: visible ? 1 : 0,
        left: pos.x - 220,
        top: pos.y - 220,
        width: 440,
        height: 440,
        background:
          "radial-gradient(circle at center, rgba(139,92,246,0.18) 0%, rgba(139,92,246,0.07) 38%, transparent 70%)",
        borderRadius: "50%",
        transition: "opacity .3s ease",
        willChange: "transform",
      }}
    />
  );
}

/* ── Hero constellation (canvas) ─────────────────────────────────────────── */
function Constellation({ scrollOpacity }: { scrollOpacity: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    type Node = { x: number; y: number; vx: number; vy: number; r: number; pulse: number };
    let nodes: Node[] = [];
    const mouse = { x: -9999, y: -9999 };

    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(70, Math.floor((w * h) / 11000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.8 + 1.0,
        pulse: Math.random() * Math.PI * 2,
      }));
    };

    let frame = 0;
    const draw = () => {
      frame++;
      ctx.clearRect(0, 0, w, h);
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        n.pulse += 0.018;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;
      }
      // edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 170) {
            const op = (1 - d / 170) * 0.6;
            ctx.strokeStyle = `rgba(139,92,246,${op})`;
            ctx.lineWidth = 0.75;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      // nodes with subtle pulse + mouse highlight
      for (const n of nodes) {
        const dm = Math.hypot(n.x - mouse.x, n.y - mouse.y);
        const near = dm < 150;
        const radius = n.r + Math.sin(n.pulse) * 0.35 + (near ? 1.2 : 0);
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = near ? "rgba(196,181,253,0.95)" : "rgba(167,139,250,0.7)";
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };

    resize();
    if (reduce) {
      draw();
      cancelAnimationFrame(raf);
    } else {
      draw();
    }

    const onMouse = (e: MouseEvent) => {
      const r = canvas.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
    };
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMouse);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouse);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full transition-opacity duration-100"
      style={{
        opacity: scrollOpacity,
        maskImage:
          "radial-gradient(ellipse at 50% 40%, black 0%, black 65%, transparent 95%)",
        WebkitMaskImage:
          "radial-gradient(ellipse at 50% 40%, black 0%, black 65%, transparent 95%)",
      }}
    />
  );
}

/* ── Brand logos (real, official marks) ──────────────────────────────────── */
const Logos = {
  slack: (
    <svg viewBox="0 0 24 24" className="w-7 h-7">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A" />
      <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0" />
      <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D" />
      <path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.315A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.522 2.523h-6.315z" fill="#ECB22E" />
    </svg>
  ),
  gmail: (
    <svg viewBox="52 42 88 66" className="w-8 h-8">
      <path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>
      <path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>
      <path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2"/>
      <path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92"/>
      <path fill="#c5221f" d="M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2"/>
    </svg>
  ),
  drive: (
    <svg viewBox="0 0 87.3 78" className="w-7 h-7">
      <path d="M6.6 66.85 10.45 73.5c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8H0c0 1.55.4 3.1 1.2 4.5z" fill="#0066da" />
      <path d="M43.65 25 29.9 1.2c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44A9.06 9.06 0 0 0 0 53h27.5z" fill="#00ac47" />
      <path d="M73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5H59.3l5.85 11.5z" fill="#ea4335" />
      <path d="M43.65 25 57.4 1.2c-1.35-.8-2.9-1.2-4.5-1.2H34.4c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d" />
      <path d="M59.8 53H27.5L13.75 76.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc" />
      <path d="M73.4 26.5 60.7 4.5c-.8-1.4-1.95-2.5-3.3-3.3L43.65 25 59.8 53h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00" />
    </svg>
  ),
  jira: (
    <svg viewBox="0 0 24 24" className="w-8 h-8">
      <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z" fill="#0052CC"/>
      <path d="M17.294 5.757H5.723a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z" fill="#0065FF"/>
      <path d="M23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0z" fill="#4C9AFF"/>
    </svg>
  ),
  zoom: (
    <svg viewBox="0 0 24 24" className="w-7 h-7" fill="#2D8CFF">
      <path d="M3 8.5C3 7.12 4.12 6 5.5 6h7C13.88 6 15 7.12 15 8.5v7c0 1.38-1.12 2.5-2.5 2.5h-7C4.12 18 3 16.88 3 15.5v-7zM16 9.8l3.7-2.66c.66-.48 1.3-.02 1.3.74v8.24c0 .76-.64 1.22-1.3.74L16 14.2V9.8z" />
    </svg>
  ),
  notion: (
    <svg viewBox="0 0 24 24" className="w-7 h-7" fill="currentColor">
      <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z" />
    </svg>
  ),
};

/* ── Static data ─────────────────────────────────────────────────────────── */
const PROBLEMS = [
  {
    badge: "$2.3M / year",
    title: "The vendor nobody remembers",
    body: "A contract signed in 2019 auto-renewed three times. The person who signed it left in 2022. Nobody knew why you were still paying.",
    accent: "#f43f5e",
    mockClip: {
      type: "email",
      sender: "Finance Alert Bot",
      subject: "Auto-Renewal Charge: $191,666.67",
      snippet: "Charge successful for Account: Enterprise DB Server. Admin Owner on record: Bob Miller (Status: INACTIVE). Contact billing support if this is an error."
    }
  },
  {
    badge: "6 months lost",
    title: "Onboarding archaeology",
    body: "A new engineer asks 'why React, not Vue?' The decision-maker is gone. The answer is buried in a 2022 Slack thread no one can find.",
    accent: "#8b5cf6",
    mockClip: {
      type: "slack",
      sender: "Sarah (Tech Lead) — 2022",
      subject: "#engineering-core",
      snippet: "Sarah: 'Switching to React because the new design system matches our requirements out-of-the-box. Let's document this so nobody re-opens the discussion in 2 years!'"
    }
  },
  {
    badge: "₹40L burned",
    title: "The mistake you repeat",
    body: "'Has anyone tried a mobile app before?' Yes — it failed in 2021 for a reason you're about to hit again. The postmortem was never read.",
    accent: "#f59e0b",
    mockClip: {
      type: "doc",
      sender: "Postmortem Doc",
      subject: "Mobile App Pilot (Archived)",
      snippet: "Status: Abandoned. Key takeaway: DO NOT attempt iOS/Android builds without dedicated native Swift/Kotlin devs. Core web team hit severe package dependency loops."
    }
  },
];

const AGENTS = {
  extraction: [
    { icon: "💬", name: "Slack Ingestion Agent", desc: "Reads every channel & thread, flags decision moments, captures participants and outcomes." },
    { icon: "✉️", name: "Email Analysis Agent", desc: "Scans Gmail for approvals, sign-offs and escalations — links threads to the decisions they made." },
    { icon: "📁", name: "Specs & Docs Agent", desc: "Parses docs, specs and proposals in Google Drive for the key choices written down inside them." },
    { icon: "🗂️", name: "Notion Extraction Agent", desc: "Walks pages and databases recursively, extracting decisions logged in specs and wikis." },
    { icon: "🎥", name: "Meeting Transcription Agent", desc: "Transcribes Zoom recordings with Whisper, then pinpoints decisions, timestamps and who was in the room." },
    { icon: "🔀", name: "Intent Router Agent", desc: "Classifies every query — search, live data, general chat, or ingest — before running downstream agents." },
    { icon: "🧠", name: "Context Synthesis Hub", desc: "Fuses every source into one unified decision graph and compiles answers with sources." },
    { icon: "🔎", name: "Research & Retrieval Agent", desc: "Hybrid semantic + keyword + graph-neighbor search, personalized to user profile and history." },
    { icon: "⚡", name: "Live Data Agent", desc: "Skips memory entirely to pull live counts, active seats, and real-time status dynamically." },
  ],
};

const CONNECTORS = [
  { key: "slack", name: "Slack", sub: "Channels & DMs" },
  { key: "gmail", name: "Gmail", sub: "Emails & approvals" },
  { key: "drive", name: "Google Drive", sub: "Docs & specs" },
  { key: "notion", name: "Notion", sub: "Pages & databases" },
  { key: "zoom", name: "Zoom", sub: "Meeting recordings" },
  { key: "jira", name: "Jira", sub: "Tickets & epics" },
] as const;

const MCP_TOOLS = [
  { name: "get_context", sig: "(query)", desc: "Claude pulls relevant company memory before it answers anything." },
  { name: "store_context", sig: "(decision, …)", desc: "Claude writes new decisions back into KAIROS the moment it learns them." },
  { name: "search_decisions", sig: "(topic, person, date)", desc: "Structured search across the decision graph with full source citations." },
  { name: "find_similar_decisions", sig: "(query)", desc: "Checks whether a new plan has real precedent — or if you're about to repeat a mistake." },
  { name: "detect_decision_patterns", sig: "(scope)", desc: "Proactively scans the whole graph for contradictions, stale spend, and bus-factor risk." },
  { name: "predict_decision_risk", sig: "(scope)", desc: "Scores every decision 0–100 for staleness, ownership gaps, and unreviewed impact." },
];

const INTELLIGENCE = [
  {
    icon: "🎯",
    tool: "find_similar_decisions",
    title: "Precedent Check",
    body: "Before your team repeats a mobile-app attempt or re-signs a vendor, KAIROS checks memory first — and gives a punchy verdict, not a hedge.",
    verdict: "“Yes — tried in 2021, failed from no mobile expertise. Don't repeat without closing that gap first.”",
  },
  {
    icon: "🕸️",
    tool: "detect_decision_patterns",
    title: "Pattern Detection",
    body: "A structural scan of the entire decision graph — contradictory outcomes on the same topic, unreviewed vendor spend, one person signing off on everything.",
    verdict: "“3 infra decisions since 2022 contradict each other — and the same person signed all of them.”",
  },
  {
    icon: "⚠️",
    tool: "predict_decision_risk",
    title: "Risk Prediction",
    body: "Every decision gets a live 0–100 risk score — stale, unowned, or high-impact — ranked so nothing important slips through again.",
    verdict: "“Risk 82/100 — vendor contract, no review in 3 years, no owner on record.”",
  },
];

const STEPS = [
  { n: "01", title: "Connect", body: "One-click OAuth into Slack, Gmail, Drive, Notion, Zoom and Jira. No admin install, no IT ticket." },
  { n: "02", title: "Extract", body: "Nine agents read continuously, catching every decision-shaped moment with sources, people, and outcomes." },
  { n: "03", title: "Graph", body: "Every decision auto-links to related ones by topic, person, and timeframe — a living, physics-simulated web." },
  { n: "04", title: "Ask", body: "Query in plain English over chat or any MCP client — cited answers in seconds, or a warning before you repeat a mistake." },
];

const MCP_TOOL_LABELS: Record<string, string> = {
  get_context: "Get Context",
  store_context: "Store Context",
  search_decisions: "Search Decisions",
  find_similar_decisions: "Precedent Check",
  detect_decision_patterns: "Pattern Detection",
  predict_decision_risk: "Risk Assessment",
};

const SIMULATION_LOGS = [
  { agent: "Intent Router", text: "Evaluating query... Target: database licensing contract and budget approvals. Activating context extraction loop." },
  { agent: "Slack Agent", text: "Scanning #billing-v2. Found thread (April 2021) between Sarah & Bob: 'Approved database budget cap increase to $15k/mo.'" },
  { agent: "Email Agent", text: "Scanned Gmail attachments. Found 'DB_Licensing_Final_Signed.pdf' signed by Sarah on 2021-05-10." },
  { agent: "Drive Agent", text: "Parsing Google Drive file 'DB Architecture Proposal v4'. Note: 'DB licenses lock us in for 5 years, auto-renewing annually unless cancelled by Q3.'" },
  { agent: "Notion Agent", text: "Reading Wiki page 'Infrastructure Costs'. Found edit log: 'Vendor contract has a 90-day auto-renew window, managed by Sarah.'" },
  { agent: "Meeting Agent", text: "Transcribed audio of Zoom meeting 'Q2 Budget Alignment'. Sarah: 'We will retain the current database licensing because transition costs are too high.'" },
  { agent: "Retrieval Agent", text: "Running hybrid semantic + graph search for 'database licensing'. Linked 5 matching historical data points." },
  { agent: "Synthesis Agent", text: "Compiling decision profile. Node created: 'Database licensing lock-in (2021)' with 5 supporting citations. Scoring decision risk..." },
  { agent: "Live Agent", text: "Querying active seat count via CRM API... Status: 45 active seats currently assigned." }
];

const SIMULATION_VERDICT = {
  verdict: "Yes, the database contract was signed by Sarah on May 10, 2021. It auto-renews annually every August. The contract has a 5-year lock-in with a budget cap of $15k/month. There are currently 45 active seats assigned.",
  citations: [
    { label: "#billing-v2 (Slack Thread)", url: "#" },
    { label: "DB_Licensing_Final_Signed.pdf (Gmail)", url: "#" },
    { label: "Infrastructure Costs (Notion Wiki)", url: "#" },
    { label: "Q2 Budget Alignment (Zoom Recording)", url: "#" }
  ]
};

/* ── Logo Container for Connectors ──────────────────────────────────────── */
function ConnectorMascot({ name, logo }: { name: string; logo: React.ReactNode }) {
  return (
    <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-violet-500/15 flex items-center justify-center group-hover:border-violet-500/35 transition-colors duration-300 shadow-[0_0_15px_rgba(139,92,246,0.05)]">
      <div className="w-7 h-7 flex items-center justify-center select-none">
        {logo}
      </div>
    </div>
  );
}

/* ── Interactive Ingestion and Thinking Simulation Demo ─────────────────── */
function AgentThinkingDemo() {
  const [isSimulating, setIsSimulating] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [logs, setLogs] = useState<{ agent: string; text: string }[]>([]);
  const [nodes, setNodes] = useState<{ id: string; label: string; x: number; y: number; edgeTo?: string }[]>([]);
  const terminalRef = useRef<HTMLDivElement>(null);

  const simulationSteps = [
    { id: "router", label: "Intent Router", x: 140, y: 100, agent: "Intent Router", text: "Evaluating query... Target: database licensing contract and budget approvals. Activating context extraction loop." },
    { id: "slack", label: "Slack Agent", x: 50, y: 50, edgeTo: "router", agent: "Slack Agent", text: "Scanning #billing-v2. Found thread (April 2021) between Sarah & Bob: 'Approved database budget cap increase to $15k/mo.'" },
    { id: "email", label: "Email Agent", x: 130, y: 30, edgeTo: "router", agent: "Email Agent", text: "Scanned Gmail attachments. Found 'DB_Licensing_Final_Signed.pdf' signed by Sarah on 2021-05-10." },
    { id: "drive", label: "Drive Agent", x: 210, y: 40, edgeTo: "router", agent: "Drive Agent", text: "Parsing Google Drive file 'DB Architecture Proposal v4'. Note: 'DB licenses lock us in for 5 years, auto-renewing annually unless cancelled by Q3.'" },
    { id: "notion", label: "Notion Agent", x: 50, y: 150, edgeTo: "router", agent: "Notion Agent", text: "Reading Wiki page 'Infrastructure Costs'. Found edit log: 'Vendor contract has a 90-day auto-renew window, managed by Sarah.'" },
    { id: "meeting", label: "Meeting Agent", x: 120, y: 170, edgeTo: "router", agent: "Meeting Agent", text: "Transcribed audio of Zoom meeting 'Q2 Budget Alignment'. Sarah: 'We will retain the current database licensing because transition costs are too high.'" },
    { id: "retrieval", label: "Retrieval Hub", x: 280, y: 100, edgeTo: "drive", agent: "Retrieval Agent", text: "Running hybrid semantic + graph search for 'database licensing'. Linked 5 matching historical data points." },
    { id: "synthesis", label: "Synthesis Engine", x: 360, y: 120, edgeTo: "retrieval", agent: "Synthesis Agent", text: "Compiling decision profile. Node created: 'Database licensing lock-in (2021)' with 5 supporting citations. Scoring decision risk..." },
    { id: "live", label: "Live API Agent", x: 430, y: 70, edgeTo: "synthesis", agent: "Live Agent", text: "Querying active seat count via CRM API... Status: 45 active seats currently assigned." }
  ];

  const startSimulation = () => {
    setIsSimulating(true);
    setCurrentStep(0);
    setLogs([
      { agent: "System", text: "Initializing multi-agent decision capture protocol..." }
    ]);
    setNodes([]);
  };

  useEffect(() => {
    if (!isSimulating || currentStep < 0) return;

    if (currentStep < simulationSteps.length) {
      const timer = setTimeout(() => {
        const stepData = simulationSteps[currentStep];
        setLogs(prev => [...prev, { agent: stepData.agent, text: stepData.text }]);
        setNodes(prev => [...prev, { id: stepData.id, label: stepData.label, x: stepData.x, y: stepData.y, edgeTo: stepData.edgeTo }]);
        setCurrentStep(prev => prev + 1);
      }, 1000);
      return () => clearTimeout(timer);
    } else {
      setIsSimulating(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSimulating, currentStep]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl border border-violet-500/20 bg-[#0d0d11]/80 backdrop-blur-md overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="px-6 py-4 border-b border-violet-500/10 flex items-center justify-between bg-violet-950/10">
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-red-500/80" />
          <span className="w-3.5 h-3.5 rounded-full bg-yellow-500/80" />
          <span className="w-3.5 h-3.5 rounded-full bg-green-500/80" />
          <span className="text-xs font-mono text-zinc-500 ml-2">multi-agent-orchestrator.sh</span>
        </div>
        <button
          onClick={startSimulation}
          disabled={isSimulating && currentStep < simulationSteps.length}
          className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 disabled:bg-violet-950/40 text-white transition-all shadow-[0_0_15px_rgba(139,92,246,0.3)]"
        >
          {isSimulating && currentStep < simulationSteps.length ? "Processing..." : "Trigger 9 Agents Simulation"}
        </button>
      </div>

      <div className="grid md:grid-cols-2 h-[420px]">
        {/* Left: Terminal logs */}
        <div ref={terminalRef} className="border-r border-violet-500/10 bg-[#09090c] p-5 font-mono text-xs overflow-y-auto flex flex-col gap-3 scrollbar-thin text-left">
          {logs.map((log, i) => (
            <div key={i} className="animate-message-in">
              <span className="text-violet-400">[{log.agent}]</span>{" "}
              <span className="text-zinc-300">{log.text}</span>
            </div>
          ))}
          {isSimulating && currentStep < simulationSteps.length && (
            <div className="flex items-center gap-1.5 text-zinc-500">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping" />
              <span>Agents processing next layer...</span>
            </div>
          )}
        </div>

        {/* Right: Live Graph Drawing */}
        <div className="relative bg-[#0d0d12] flex flex-col items-center justify-center p-4">
          {nodes.length === 0 ? (
            <div className="text-center text-zinc-600 text-xs font-mono">
              <p>Waiting to trigger simulation...</p>
              <p className="mt-2 text-[10px] text-zinc-700">Click the button top-right to watch the 9-agent extraction run live.</p>
            </div>
          ) : (
            <div className="w-full h-full relative">
              <svg className="w-full h-full min-h-[300px]" viewBox="0 0 500 240">
                {/* Draw edges */}
                {nodes.map(node => {
                  if (!node.edgeTo) return null;
                  const parent = nodes.find(n => n.id === node.edgeTo);
                  if (!parent) return null;
                  return (
                    <line
                      key={`edge-${node.id}`}
                      x1={parent.x}
                      y1={parent.y}
                      x2={node.x}
                      y2={node.y}
                      stroke="rgba(139,92,246,0.35)"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                      className="animate-[fadeIn_0.5s_ease-out]"
                    />
                  );
                })}

                {/* Draw nodes */}
                {nodes.map(node => (
                  <g key={node.id} className="animate-[popIn_0.4s_cubic-bezier(.34,1.56,.64,1)]">
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r="7"
                      fill="#a855f7"
                      className="animate-pulse"
                      style={{ animationDuration: "2s" }}
                    />
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r="12"
                      fill="none"
                      stroke="rgba(168,85,247,0.3)"
                      strokeWidth="1"
                    />
                    <text
                      x={node.x}
                      y={node.y - 14}
                      textAnchor="middle"
                      fill="#e4e4e7"
                      fontSize="9.5"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {node.label}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
          )}
        </div>
      </div>

      {/* Synthesis Output box */}
      {currentStep >= simulationSteps.length && (
        <div className="p-6 border-t border-violet-500/20 bg-violet-950/15 animate-message-in flex flex-col md:flex-row gap-5 items-start text-left">
          <div className="shrink-0 w-10 h-10 rounded-full bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-lg">
            🧠
          </div>
          <div>
            <h4 className="text-sm font-bold text-violet-300 font-mono mb-2 uppercase tracking-wide">Synthesized Verdict</h4>
            <p className="text-sm text-zinc-200 leading-relaxed font-sans italic">
              &quot;{SIMULATION_VERDICT.verdict}&quot;
            </p>
            <div className="mt-4 flex flex-wrap gap-2 items-center">
              <span className="text-[10.5px] font-mono uppercase tracking-wider text-zinc-500">Cited Sources:</span>
              {SIMULATION_VERDICT.citations.map((c, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded border border-violet-500/25 bg-violet-500/5 text-[11px] text-violet-300 hover:border-violet-500/50 hover:bg-violet-500/10 cursor-pointer font-sans"
                >
                  {c.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


/* ── Page ────────────────────────────────────────────────────────────────── */
export default function Landing() {
  const router = useRouter();
  const { user, loginWithGoogle } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 12);
      setScrollY(y);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Hero glow + constellation fade out as user scrolls away from hero
  const heroGlowOpacity = Math.max(0, 1 - scrollY / 420);

  const enter = useCallback(() => router.push("/dashboard"), [router]);
  const signIn = useCallback(async () => {
    try {
      await loginWithGoogle();
    } catch {
      /* dashboard handles auth fallback */
    }
    router.push("/dashboard");
  }, [loginWithGoogle, router]);

  return (
    <main className="relative min-h-screen w-full bg-[#080808] text-[#ededed] overflow-x-hidden font-serif">
      {/* Subtle film-grain texture for a premium, non-flat finish */}
      <div
        className="fixed inset-0 z-[1] pointer-events-none opacity-[0.035] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
      <SiteBackground />
      <CursorGlow />
      {/* ── Nav ── */}
      <nav
        className="fixed top-0 inset-x-0 z-50 transition-all duration-300"
        style={{
          background: scrolled ? "rgba(8,8,8,0.72)" : "transparent",
          backdropFilter: scrolled ? "blur(14px)" : "none",
          borderBottom: scrolled ? "1px solid rgba(139,92,246,0.12)" : "1px solid transparent",
        }}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KairosLogo size={34} showText={true} className="text-white" />
            <span className="text-zinc-400 font-sans text-xl font-light select-none inline-flex items-center justify-center h-9">×</span>
            {/* Real AMD Logo SVG */}
            <svg viewBox="0 5.5 24 13" className="w-auto fill-current text-white shrink-0" style={{ height: "36px" }} role="img" xmlns="http://www.w3.org/2000/svg">
              <path d="M18.324 9.137l1.559 1.56h2.556v2.557L24 14.814V9.137zM2 9.52l-2 4.96h1.309l.37-.982H3.9l.408.982h1.338L3.432 9.52zm4.209 0v4.955h1.238v-3.092l1.338 1.562h.188l1.338-1.556v3.091h1.238V9.52H10.47l-1.592 1.845L7.287 9.52zm6.283 0v4.96h2.057c1.979 0 2.88-1.046 2.88-2.472 0-1.36-.937-2.488-2.747-2.488zm1.237.91h.792c1.17 0 1.63.711 1.63 1.57 0 .728-.372 1.572-1.616 1.572h-.806zm-10.985.273l.791 1.932H2.008zm17.137.307l-1.604 1.603v2.25h2.246l1.604-1.607h-2.246z" />
            </svg>
          </div>
          <div className="hidden md:flex items-center gap-5 text-[10px] font-mono tracking-wide text-zinc-400">
            <a href="#problem" className="hover:text-white transition-colors">The Problem</a>
            <a href="#how" className="hover:text-white transition-colors">How It Works</a>
            <a href="#agents" className="hover:text-white transition-colors">Agents</a>
            <a href="#intelligence" className="hover:text-white transition-colors">Intelligence</a>
            <a href="#connectors" className="hover:text-white transition-colors">Connectors</a>
            <a href="#mcp" className="hover:text-white transition-colors">MCP</a>
          </div>
          <button
            onClick={enter}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 transition-colors text-white shadow-[0_0_20px_rgba(139,92,246,0.35)]"
          >
            {user ? "Open Dashboard" : "Enter KAIROS"}
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative min-h-screen flex items-center justify-center px-6 pt-16">
        <Constellation scrollOpacity={heroGlowOpacity} />
        {/* ambient glows — fade on scroll */}
        <div
          className="absolute top-1/4 left-1/4 w-[42rem] h-[42rem] rounded-full bg-violet-700/25 blur-[130px] pointer-events-none"
          style={{ opacity: heroGlowOpacity }}
        />
        <div
          className="absolute bottom-0 right-1/4 w-[36rem] h-[36rem] rounded-full bg-fuchsia-700/15 blur-[140px] pointer-events-none"
          style={{ opacity: heroGlowOpacity }}
        />
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60rem] h-[30rem] rounded-full bg-violet-900/20 blur-[160px] pointer-events-none"
          style={{ opacity: heroGlowOpacity }}
        />

        <div className="relative z-10 text-center max-w-4xl">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-7 rounded-full border border-violet-500/30 bg-violet-500/5 text-[11px] font-mono tracking-wide text-violet-300">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            Company Organizational Memory OS
          </div>

          <h1 className="text-5xl md:text-7xl font-bold leading-[1.05] tracking-tight">
            Every company forgets
            <br />
            <span className="bg-gradient-to-r from-violet-300 via-fuchsia-300 to-violet-400 bg-clip-text text-transparent">
              why it decided.
            </span>
            <br />
            KAIROS never does.
          </h1>

          <p className="mt-7 text-base md:text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed font-sans">
            Nine AI agents read your Slack, email, Drive, Notion, Jira and Zoom —
            extracting every decision into a living decision graph that proactively
            flags risk. Ask in plain English, get the answer with sources in seconds.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              onClick={enter}
              className="px-7 py-3.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 transition-all text-white shadow-[0_0_30px_rgba(139,92,246,0.45)] hover:shadow-[0_0_44px_rgba(139,92,246,0.65)] hover:-translate-y-0.5"
            >
              {user ? "Open Dashboard →" : "Enter KAIROS →"}
            </button>
            {!user && (
              <button
                onClick={signIn}
                className="px-7 py-3.5 rounded-xl text-sm font-semibold bg-white/5 border border-violet-500/20 hover:bg-white/10 hover:border-violet-500/40 transition-all text-white flex items-center gap-3"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path fill="#ea4335" d="M12.24 10.285V14.4h6.887c-.648 2.41-2.519 4.114-5.136 4.114A5.59 5.59 0 018.4 12.925a5.59 5.59 0 015.591-5.59c2.316 0 4.29 1.258 5.347 3.12l3.418-2.617A10.957 10.957 0 0013.991 3C8.196 3 3.5 7.696 3.5 13.49s4.696 10.49 10.491 10.49c6.126 0 10.285-4.305 10.285-10.49 0-.616-.056-1.22-.168-1.785H12.24z" />
                </svg>
                Sign in with Google
              </button>
            )}
          </div>

          <div className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[11px] font-mono tracking-wide text-zinc-500">
            <span><span className="text-violet-300 font-semibold">9</span> parallel agents</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">6</span> connectors</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">6</span> MCP tools</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">~4s</span> recall</span>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-zinc-600 animate-bounce">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </section>

      {/* ── Problem ── */}
      <section id="problem" className="relative py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">The Problem</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
              Knowledge doesn&apos;t leave in documents.
              <br />
              <span className="text-zinc-500">It leaves in people.</span>
            </h2>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-6">
            {PROBLEMS.map((p, i) => (
              <Reveal key={p.title} delay={i * 120}>
                <TiltCard className="h-full p-7 rounded-2xl border border-violet-500/15 bg-gradient-to-b from-violet-500/[0.02] to-transparent hover:border-violet-500/35 transition-colors flex flex-col justify-between">
                  <div>
                    <div
                      className="inline-block px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold mb-5 text-left"
                      style={{ background: `${p.accent}1a`, color: p.accent }}
                    >
                      {p.badge}
                    </div>
                    <h3 className="text-xl font-semibold mb-3 text-left">{p.title}</h3>
                    <p className="text-sm text-zinc-400 leading-relaxed font-sans mb-6 text-left">{p.body}</p>
                  </div>
                  
                  {/* Contextual mock artifact snippet */}
                  <div className="mt-auto p-4 rounded-xl bg-black/45 border border-zinc-800/60 font-sans text-left">
                    <div className="flex items-center justify-between gap-2 mb-2 text-[10px] font-mono text-zinc-500">
                      <span className="flex items-center gap-1">
                        {p.mockClip.type === "slack" && <span className="text-[#36C5F0]">💬</span>}
                        {p.mockClip.type === "email" && <span className="text-[#ea4335]">✉️</span>}
                        {p.mockClip.type === "doc" && <span className="text-[#a855f7]">📁</span>}
                        {p.mockClip.sender}
                      </span>
                      <span>{p.mockClip.subject}</span>
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-relaxed font-mono font-light select-none whitespace-pre-line border-l-2 pl-2.5" style={{ borderColor: p.accent }}>
                      {p.mockClip.snippet}
                    </p>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="how" className="relative py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Live Demonstration</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Watch KAIROS Work in Real-Time</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Watch how our parallel agent grid parses unstructured streams of company chatter, extracts the underlying context, and maps it directly to a unified decision memory graph.
            </p>
          </Reveal>

          <Reveal>
            <AgentThinkingDemo />
          </Reveal>
        </div>
      </section>

      {/* ── Agents ── */}
      <section id="agents" className="relative py-16 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">The Engine</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Nine agents, running in parallel</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Orchestrated with LangGraph — five own a source and extract decisions, four reason
              over the graph to route, retrieve, synthesize and answer live queries.
            </p>
          </Reveal>

          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Core Parallel Agents</p>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mb-14">
            {AGENTS.extraction.map((a, i) => (
              <Reveal key={a.name} delay={i * 80}>
                <div className="group h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:bg-white/[0.04] hover:border-violet-500/40 transition-all text-left">
                  <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-2xl mb-5 group-hover:scale-110 transition-transform">
                    {a.icon}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{a.name}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{a.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={200}>
            <div className="mt-8 p-6 rounded-2xl border border-violet-500/25 bg-violet-600/10 text-left">
              <p className="text-sm text-zinc-300 leading-relaxed font-sans">
                Powered by <span className="text-violet-300 font-semibold">Fireworks AI</span> on
                AMD hardware — Qwen-3 for answers, Llama-3.3 for high-volume ingestion, with
                automatic Groq + Gemini fallback so it never stalls.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Decision Intelligence ── */}
      <section id="intelligence" className="relative py-16 px-6 overflow-hidden">
        <div
          className="absolute top-0 right-0 w-[40rem] h-[40rem] rounded-full bg-fuchsia-700/10 blur-[150px] pointer-events-none"
        />
        <div className="max-w-6xl mx-auto relative">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">New — Proactive, Not Just Reactive</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
              KAIROS doesn&apos;t wait to be asked.
            </h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              A structural scan of the entire decision graph, plus one focused model call per
              finding — never invented, always grounded in what&apos;s actually in memory.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-5 mb-10">
            {INTELLIGENCE.map((f, i) => (
              <Reveal key={f.tool} delay={i * 110}>
                <TiltCard className="h-full p-6 rounded-2xl border border-violet-500/15 bg-gradient-to-b from-violet-500/[0.03] to-transparent hover:border-violet-500/40 transition-colors flex flex-col text-left">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-xl">
                      {f.icon}
                    </div>
                    <span className="font-mono text-[10.5px] text-violet-400">{MCP_TOOL_LABELS[f.tool] || f.tool}</span>
                  </div>
                  <h3 className="text-lg font-semibold mb-2.5">{f.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans mb-4">{f.body}</p>
                  <div className="mt-auto pt-4 border-t border-violet-500/10">
                    <p className="text-[12.5px] text-violet-200/90 italic leading-relaxed font-sans">{f.verdict}</p>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>

          <Reveal delay={340}>
            <div className="p-6 md:p-8 rounded-2xl border border-violet-500/20 bg-[#0b0b0d] flex flex-col md:flex-row items-center gap-8 text-left">
              <div className="relative shrink-0 w-32 h-32">
                <svg viewBox="0 0 36 36" className="w-32 h-32 -rotate-90">
                  <path d="M18 2.5 a15.5 15.5 0 0 1 0 31 a15.5 15.5 0 0 1 0 -31" fill="none" stroke="rgba(139,92,246,0.15)" strokeWidth="3" />
                  <path
                    d="M18 2.5 a15.5 15.5 0 0 1 0 31 a15.5 15.5 0 0 1 0 -31"
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="3"
                    strokeDasharray="34, 100"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center flex-col">
                  <span className="text-2xl font-black text-white">34</span>
                  <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">/ 100</span>
                </div>
              </div>
              <div className="flex-1 text-center md:text-left">
                <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-amber-400 mb-2">Decision Debt Score</p>
                <p className="text-lg text-white font-semibold mb-1.5">14 decisions with no review in 2+ years</p>
                <p className="text-sm text-zinc-400 leading-relaxed font-sans">
                  Pure SQL and graph aggregation — no model call, always live. One glance tells
                  a story your CFO will actually read.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Connectors ── */}
      <section id="connectors" className="relative py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Connectors</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">One-click OAuth. No token wrangling.</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              An admin connects each workspace tool once. KAIROS reads continuously and keeps the
              decision graph fresh.
            </p>
          </Reveal>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 items-stretch">
            {CONNECTORS.map((c, i) => (
              <Reveal key={c.key} delay={i * 80} className="h-full">
                <TiltCard className="h-full min-h-[225px] p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:border-violet-500/35 transition-colors flex flex-col items-center justify-between text-center gap-3">
                  <ConnectorMascot name={c.name} logo={Logos[c.key]} />
                  <div>
                    <div className="text-sm font-semibold">{c.name}</div>
                    <div className="text-[11px] text-zinc-500 font-mono mt-1">{c.sub}</div>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── MCP ── */}
      <section id="mcp" className="relative py-16 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Integrations</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Kairos MCP</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              KAIROS exposes a Model Context Protocol (MCP) server over streamable HTTP. Your AI assistants read from and write to the same organizational memory, keeping your team's context perfectly aligned.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-5 mb-12">
            {MCP_TOOLS.map((t, i) => (
              <Reveal key={t.name} delay={i * 110}>
                <div className="h-full p-6 rounded-2xl border border-violet-500/15 bg-[#0c0c0e] hover:border-violet-500/30 transition-all text-left">
                  <div className="font-mono text-sm mb-3">
                    <span className="text-violet-300">{MCP_TOOL_LABELS[t.name] || t.name}</span>
                  </div>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{t.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative py-32 px-6">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[36rem] h-[36rem] rounded-full bg-violet-700/15 blur-[150px]" />
        </div>
        <Reveal className="relative max-w-3xl mx-auto text-center">
          <KairosLogo size={56} showText={true} className="mx-auto mb-8 text-white" />
          <h2 className="text-4xl md:text-6xl font-bold tracking-tight">
            Stop losing the <span className="text-violet-300">why</span>.
          </h2>
          <p className="mt-5 text-zinc-400 max-w-xl mx-auto font-sans">
            Connect your workspace and ask KAIROS your first question. The memory builds itself.
          </p>
          <button
            onClick={enter}
            className="mt-10 px-9 py-4 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 transition-all text-white shadow-[0_0_36px_rgba(139,92,246,0.5)] hover:-translate-y-0.5"
          >
            {user ? "Open Dashboard →" : "Enter KAIROS →"}
          </button>
        </Reveal>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-violet-950/40 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-zinc-500 font-mono">
          <div className="flex items-center gap-2.5">
            <KairosLogo size={22} showText={true} className="text-zinc-300" />
          </div>
          <p>Built by Antigravity · MIT License · &quot;Every company forgets why. KAIROS never does.&quot;</p>
        </div>
      </footer>
    </main>
  );
}

