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
};

/* ── Static data ─────────────────────────────────────────────────────────── */
const PROBLEMS = [
  {
    badge: "$2.3M / year",
    title: "The vendor nobody remembers",
    body: "A contract signed in 2019 auto-renewed three times. The person who signed it left in 2022. Nobody knew why you were still paying.",
    accent: "#f43f5e",
  },
  {
    badge: "6 months lost",
    title: "Onboarding archaeology",
    body: "A new engineer asks 'why React, not Vue?' The decision-maker is gone. The answer is buried in a 2022 Slack thread no one can find.",
    accent: "#8b5cf6",
  },
  {
    badge: "₹40L burned",
    title: "The mistake you repeat",
    body: "'Has anyone tried a mobile app before?' Yes — it failed in 2021 for a reason you're about to hit again. The postmortem was never read.",
    accent: "#f59e0b",
  },
];

const AGENTS = [
  { icon: "💬", name: "Slack Agent", desc: "Reads every channel & thread, flags decision moments, captures participants and outcomes." },
  { icon: "✉️", name: "Email Agent", desc: "Scans Gmail for approvals, sign-offs and escalations — links threads to the decisions they made." },
  { icon: "📁", name: "Drive Agent", desc: "Parses docs, specs and proposals in Google Drive for the key choices written down inside them." },
  { icon: "🎥", name: "Meeting Agent", desc: "Transcribes Zoom recordings with Whisper, then pinpoints decisions, timestamps and who was in the room." },
  { icon: "🧠", name: "Synthesis Agent", desc: "The orchestrator. Fuses every source into one decision graph and answers your questions with citations." },
];

const CONNECTORS = [
  { key: "slack", name: "Slack", sub: "Channels & DMs" },
  { key: "gmail", name: "Gmail", sub: "Emails & approvals" },
  { key: "drive", name: "Google Drive", sub: "Docs & specs" },
  { key: "jira", name: "Jira", sub: "Tickets & epics" },
  { key: "zoom", name: "Zoom", sub: "Meeting recordings" },
] as const;

const MCP_TOOLS = [
  { name: "get_context", sig: "(query)", desc: "Claude pulls relevant company memory before it answers anything." },
  { name: "store_context", sig: "(decision, …)", desc: "Claude writes new decisions back into KAIROS the moment it learns them." },
  { name: "search_decisions", sig: "(topic, person, date)", desc: "Structured search across the decision graph with full source citations." },
];

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
          <div className="flex items-center gap-2.5">
            <KairosLogo size={30} />
            <span className="text-lg font-bold tracking-[0.2em]">KAIROS</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-xs font-mono tracking-wide text-zinc-400">
            <a href="#problem" className="hover:text-white transition-colors">The Problem</a>
            <a href="#agents" className="hover:text-white transition-colors">Agents</a>
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
            Five AI agents read your Slack, email, Drive, Jira and Zoom — extracting
            every decision and its full context into a living decision graph. Ask in
            plain English, get the answer with sources in seconds.
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
            <span><span className="text-violet-300 font-semibold">5</span> parallel agents</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">5</span> connectors</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">3</span> MCP tools</span>
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
      <section id="problem" className="relative py-28 px-6">
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
                <TiltCard className="h-full p-7 rounded-2xl border border-violet-500/15 bg-gradient-to-b from-violet-500/[0.02] to-transparent hover:border-violet-500/35 transition-colors">
                  <div
                    className="inline-block px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold mb-5"
                    style={{ background: `${p.accent}1a`, color: p.accent }}
                  >
                    {p.badge}
                  </div>
                  <h3 className="text-xl font-semibold mb-3">{p.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{p.body}</p>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Agents ── */}
      <section id="agents" className="relative py-28 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">The Engine</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Five agents, running in parallel</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Orchestrated with LangGraph, each agent owns a source. Together they turn raw
              communication into a structured, queryable memory.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {AGENTS.map((a, i) => (
              <Reveal key={a.name} delay={i * 90}>
                <div className="group h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:bg-white/[0.04] hover:border-violet-500/40 transition-all">
                  <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-2xl mb-5 group-hover:scale-110 transition-transform">
                    {a.icon}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{a.name}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{a.desc}</p>
                </div>
              </Reveal>
            ))}
            <Reveal delay={AGENTS.length * 90}>
              <div className="h-full p-6 rounded-2xl border border-violet-500/25 bg-violet-600/10 flex flex-col justify-center">
                <p className="text-sm text-zinc-300 leading-relaxed font-sans">
                  Powered by <span className="text-violet-300 font-semibold">Fireworks AI</span> on
                  AMD hardware — Qwen-2.5 72B for answers, Llama-3.1 8B for high-volume ingestion,
                  with automatic provider fallback so it never stalls.
                </p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Connectors ── */}
      <section id="connectors" className="relative py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Connectors</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">One-click OAuth. No token wrangling.</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              An admin connects each workspace tool once. KAIROS reads continuously and keeps the
              decision graph fresh.
            </p>
          </Reveal>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {CONNECTORS.map((c, i) => (
              <Reveal key={c.key} delay={i * 80}>
                <TiltCard className="h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:border-violet-500/35 transition-colors flex flex-col items-center text-center gap-3">
                  <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-violet-500/15 flex items-center justify-center">
                    {Logos[c.key]}
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{c.name}</div>
                    <div className="text-[11px] text-zinc-500 font-mono mt-0.5">{c.sub}</div>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── MCP ── */}
      <section id="mcp" className="relative py-28 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">The Memory Loop</p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">A two-way brain for Claude</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              KAIROS exposes an MCP server over streamable HTTP. Claude Desktop, Cursor and Claude
              Code read from <em>and</em> write to the same organizational memory — both get smarter
              over time.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-5 mb-12">
            {MCP_TOOLS.map((t, i) => (
              <Reveal key={t.name} delay={i * 110}>
                <div className="h-full p-6 rounded-2xl border border-violet-500/15 bg-[#0c0c0e] hover:border-violet-500/30 transition-all">
                  <div className="font-mono text-sm mb-3">
                    <span className="text-violet-300">{t.name}</span>
                    <span className="text-zinc-600">{t.sig}</span>
                  </div>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{t.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal>
            <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-mono text-zinc-400">
              <span className="px-4 py-2 rounded-lg border border-violet-500/25 bg-violet-500/5 text-violet-200">KAIROS Memory</span>
              <span className="text-violet-500">⇄</span>
              <span className="px-4 py-2 rounded-lg border border-violet-500/20 bg-white/[0.03]">Claude</span>
              <span className="text-zinc-600 ml-2">context out · knowledge in</span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative py-32 px-6">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[36rem] h-[36rem] rounded-full bg-violet-700/15 blur-[150px]" />
        </div>
        <Reveal className="relative max-w-3xl mx-auto text-center">
          <KairosLogo size={56} className="mx-auto mb-8" />
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
            <KairosLogo size={22} />
            <span className="tracking-[0.2em] font-semibold text-zinc-300">KAIROS</span>
          </div>
          <p>Built by Antigravity · MIT License · &quot;Every company forgets why. KAIROS never does.&quot;</p>
        </div>
      </footer>
    </main>
  );
}
