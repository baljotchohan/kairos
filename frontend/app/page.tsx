"use client";

/**
 * KAIROS — Landing page (the marketing layer in front of the dashboard).
 *
 * Lightweight 3D: a canvas decision-graph constellation in the hero, CSS
 * perspective tilt cards, gradient glows, and IntersectionObserver scroll
 * reveals — no heavy WebGL deps, so it stays fast on a judge's laptop.
 * "Enter KAIROS" routes into /dashboard, which owns sign-in.
 */

import React, { useEffect, useRef, useState, useCallback, useId } from "react";
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
    <div style={{ perspective: 900, height: "100%" }}>
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
// Zero React in the hot path: no useState, no re-render — every pointermove
// writes straight to the DOM node's style, so there is nothing between the
// event and the pixel moving except the browser's own paint cycle.
function CursorGlow() {
  const elRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;

    const onMove = (e: PointerEvent) => {
      el.style.transform = `translate3d(${e.clientX - 220}px, ${e.clientY - 220}px, 0)`;
      el.style.opacity = "1";
    };
    const onLeave = () => {
      el.style.opacity = "0";
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return (
    <div
      ref={elRef}
      className="pointer-events-none fixed top-0 left-0 z-[9998]"
      style={{
        opacity: 0,
        width: 440,
        height: 440,
        background:
          "radial-gradient(circle at center, rgba(139,92,246,0.18) 0%, rgba(139,92,246,0.07) 38%, transparent 70%)",
        borderRadius: "50%",
        transition: "opacity .15s linear",
        willChange: "transform",
      }}
    />
  );
}

/* ── Magnetic button wrapper ─────────────────────────────────────────────── */
// Nudges its child toward the cursor within a small radius, springs back on
// leave — the "premium CTA" idiom (Linear, Stripe, Vercel all use this).
function Magnetic({
  children,
  strength = 0.35,
  className = "",
}: {
  children: React.ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState({ x: 0, y: 0 });

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left - r.width / 2) * strength;
    const y = (e.clientY - r.top - r.height / 2) * strength;
    setT({ x, y });
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={() => setT({ x: 0, y: 0 })}
      className={className}
      style={{
        transform: `translate3d(${t.x}px, ${t.y}px, 0)`,
        transition: t.x === 0 && t.y === 0 ? "transform .45s var(--ease-spring)" : "transform .12s ease-out",
        display: "inline-block",
      }}
    >
      {children}
    </div>
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

/* ── AMD logo (real, official mark) — hackathon hardware partner ──────────── */
function AMDLogo({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 800 190.803" className={className} fill="currentColor">
      <path d="M187.888 178.122H143.52l-13.573-32.738H56.003l-12.366 32.738H0L66.667 12.776h47.761zM91.155 52.286L66.912 116.53h50.913zm257.901-39.51h35.88v165.346h-41.219V74.842l-44.608 51.877h-6.301l-44.605-51.877V178.12h-41.219V12.776h35.88l53.092 61.336zm140.319 0c60.364 0 91.391 37.573 91.391 82.909 0 47.517-30.058 82.437-96 82.437h-68.369V12.776zm-31.762 135.041h26.906c41.457 0 53.823-28.129 53.823-52.377 0-28.368-15.276-52.363-54.308-52.363h-26.422v104.74zm205.156-95.836L610.797 0H800v189.21l-51.972-51.975V51.981zm-.061 10.416L609.2 115.903v74.899h74.889l53.505-53.506h-74.886z" />
    </svg>
  );
}

/* ── Gemma logo (real, official mark) — Google DeepMind co-sponsor model line ── */
function GemmaLogo({ className = "" }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <svg viewBox="0 0 24 24" className="h-[1.5em] w-[1.5em]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id={`gemma-grad-${uid}`} x1="24.419%" x2="75.194%" y1="75.581%" y2="25.194%">
            <stop offset="0%" stopColor="#446EFF" />
            <stop offset="36.661%" stopColor="#2E96FF" />
            <stop offset="83.221%" stopColor="#B1C5FF" />
          </linearGradient>
        </defs>
        <path
          fillRule="evenodd"
          fill={`url(#gemma-grad-${uid})`}
          d="M12.34 5.953a8.233 8.233 0 01-.247-1.125V3.72a8.25 8.25 0 015.562 2.232H12.34zm-.69 0c.113-.373.199-.755.257-1.145V3.72a8.25 8.25 0 00-5.562 2.232h5.304zm-5.433.187h5.373a7.98 7.98 0 01-.267.696 8.41 8.41 0 01-1.76 2.65L6.216 6.14zm-.264-.187H2.977v.187h2.915a8.436 8.436 0 00-2.357 5.767H0v.186h3.535a8.436 8.436 0 002.357 5.767H2.977v.186h2.976v2.977h.187v-2.915a8.436 8.436 0 005.767 2.357V24h.186v-3.535a8.436 8.436 0 005.767-2.357v2.915h.186v-2.977h2.977v-.186h-2.915a8.436 8.436 0 002.357-5.767H24v-.186h-3.535a8.436 8.436 0 00-2.357-5.767h2.915v-.187h-2.977V2.977h-.186v2.915a8.436 8.436 0 00-5.767-2.357V0h-.186v3.535A8.436 8.436 0 006.14 5.892V2.977h-.187v2.976zm6.14 14.326a8.25 8.25 0 005.562-2.233H12.34c-.108.367-.19.743-.247 1.126v1.107zm-.186-1.087a8.015 8.015 0 00-.258-1.146H6.345a8.25 8.25 0 005.562 2.233v-1.087zm-8.186-7.285h1.107a8.23 8.23 0 001.125-.247V6.345a8.25 8.25 0 00-2.232 5.562zm1.087.186H3.72a8.25 8.25 0 002.232 5.562v-5.304a8.012 8.012 0 00-1.145-.258zm15.47-.186a8.25 8.25 0 00-2.232-5.562v5.315c.367.108.743.19 1.126.247h1.107zm-1.086.186c-.39.058-.772.144-1.146.258v5.304a8.25 8.25 0 002.233-5.562h-1.087zm-1.332 5.69V12.41a7.97 7.97 0 00-.696.267 8.409 8.409 0 00-2.65 1.76l3.346 3.346zm0-6.18v-5.45l-.012-.013h-5.451c.076.235.162.468.26.696a8.698 8.698 0 001.819 2.688 8.698 8.698 0 002.688 1.82c.228.097.46.183.696.259zM6.14 17.848V12.41c.235.078.468.167.696.267a8.403 8.403 0 012.688 1.799 8.404 8.404 0 011.799 2.688c.1.228.19.46.267.696H6.152l-.012-.012zm0-6.245V6.326l3.29 3.29a8.716 8.716 0 01-2.594 1.728 8.14 8.14 0 01-.696.259zm6.257 6.257h5.277l-3.29-3.29a8.716 8.716 0 00-1.728 2.594 8.135 8.135 0 00-.259.696zm-2.347-7.81a9.435 9.435 0 01-2.88 1.96 9.14 9.14 0 012.88 1.94 9.14 9.14 0 011.94 2.88 9.435 9.435 0 011.96-2.88 9.14 9.14 0 012.88-1.94 9.435 9.435 0 01-2.88-1.96 9.434 9.434 0 01-1.96-2.88 9.14 9.14 0 01-1.94 2.88z"
        />
      </svg>
      <span
        className="font-sans font-bold tracking-tight"
        style={{
          backgroundImage: "linear-gradient(135deg, #446EFF 0%, #2E96FF 40%, #B1C5FF 100%)",
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
        }}
      >
        Gemma
      </span>
    </span>
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
    <svg viewBox="0 0 24 24" className="w-7 h-7">
      <rect width="24" height="24" rx="5.5" fill="#000000" />
      <path
        transform="translate(2.7, 3) scale(0.72)"
        fill="#fff"
        d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.19v6.96l1.468.327s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.1 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.284V9.107l-1.215-.14c-.093-.514.28-.887.747-.933z"
      />
    </svg>
  ),
  github: (
    <svg viewBox="0 0 24 24" className="w-7 h-7">
      <rect width="24" height="24" rx="5.5" fill="#181717" />
      <path fill="#fff" transform="translate(3.5 3.5) scale(0.7)" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  ),
};

/* ── Agent mascots ───────────────────────────────────────────────────────────
   One consistent glossy 3D robot head (built from an SVG gooey-blob filter so
   the cat-ear bumps fuse seamlessly into the head, no visible seams) for every
   extraction agent — the head color matches that service's real brand color,
   and each gets its own expression for personality. */
function Mascot({ id, light, dark, face }: { id: string; light: string; dark: string; face: React.ReactNode }) {
  return (
    <svg viewBox="0 0 200 210" className="w-16 h-16">
      <defs>
        <filter id={`goo-${id}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
          <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 24 -12" result="goo" />
        </filter>
        <radialGradient id={`bodygrad-${id}`} cx="32%" cy="26%" r="85%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="42%" stopColor={light} />
          <stop offset="100%" stopColor={dark} />
        </radialGradient>
        <radialGradient id={`screengrad-${id}`} cx="35%" cy="18%" r="95%">
          <stop offset="0%" stopColor="#38383e" />
          <stop offset="40%" stopColor="#101013" />
          <stop offset="100%" stopColor="#000000" />
        </radialGradient>
        <radialGradient id={`highlight-${id}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
        </radialGradient>
      </defs>

      <ellipse cx="100" cy="192" rx="52" ry="9" fill="rgba(0,0,0,0.25)" />

      <g filter={`url(#goo-${id})`}>
        <circle cx="60" cy="40" r="16" fill={`url(#bodygrad-${id})`} />
        <circle cx="140" cy="40" r="16" fill={`url(#bodygrad-${id})`} />
        <rect x="38" y="36" width="124" height="120" rx="45" fill={`url(#bodygrad-${id})`} />
      </g>

      <ellipse cx="72" cy="62" rx="28" ry="16" fill={`url(#highlight-${id})`} opacity={0.6} />

      <rect x="53" y="68" width="94" height="74" rx="22" fill={`url(#screengrad-${id})`} />
      <rect x="53" y="68" width="94" height="28" rx="22" fill="#ffffff" opacity={0.06} />

      <g opacity={0.97}>{face}</g>

      <rect x="38" y="36" width="124" height="120" rx="45" fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="1.5" opacity={0.5} />
    </svg>
  );
}

const MASCOTS = {
  // Slack — laughing, wide open grin (chatty, always in the channel)
  slack: (
    <Mascot id="slack" light="#8b5f96" dark="#2d0d33" face={
      <>
        <circle cx="81.5" cy="102" r="6.5" fill="#fff" />
        <circle cx="118.5" cy="102" r="6.5" fill="#fff" />
        <path d="M 78 118 Q 100 140 122 118 Q 100 132 78 118 Z" fill="#fff" />
      </>
    } />
  ),
  // Gmail — calm, content smile (steady and attentive)
  gmail: (
    <Mascot id="gmail" light="#f08b7f" dark="#8f130a" face={
      <>
        <rect x="76" y="94" width="11" height="18" rx="5.5" fill="#fff" />
        <rect x="113" y="94" width="11" height="18" rx="5.5" fill="#fff" />
        <path d="M 82 120 Q 100 134 118 120" stroke="#fff" strokeWidth="6" strokeLinecap="round" fill="none" />
      </>
    } />
  ),
  // Drive — curious, one eye raised, slight smirk (digging through docs)
  drive: (
    <Mascot id="drive" light="#7fd39a" dark="#0f5c28" face={
      <>
        <rect x="75" y="90" width="12" height="20" rx="6" fill="#fff" />
        <rect x="113" y="97" width="12" height="12" rx="6" fill="#fff" />
        <path d="M 82 121 Q 100 130 122 116" stroke="#fff" strokeWidth="6" strokeLinecap="round" fill="none" />
      </>
    } />
  ),
  // Notion — closed happy eyes, quiet smile (organizing, at peace)
  notion: (
    <Mascot id="notion" light="#f0d3ab" dark="#8a5f2e" face={
      <>
        <path d="M 74 100 Q 81.5 92 89 100" stroke="#fff" strokeWidth="5.5" strokeLinecap="round" fill="none" />
        <path d="M 111 100 Q 118.5 92 126 100" stroke="#fff" strokeWidth="5.5" strokeLinecap="round" fill="none" />
        <path d="M 90 122 Q 100 128 110 122" stroke="#fff" strokeWidth="5.5" strokeLinecap="round" fill="none" />
      </>
    } />
  ),
  // GitHub — a wink and a smirk (clever, in on the joke)
  github: (
    <Mascot id="github" light="#a5a8f7" dark="#312e81" face={
      <>
        <rect x="76" y="94" width="11" height="18" rx="5.5" fill="#fff" />
        <path d="M 113 103 Q 118.5 99 124 103" stroke="#fff" strokeWidth="5" strokeLinecap="round" fill="none" />
        <path d="M 82 118 Q 104 132 124 114" stroke="#fff" strokeWidth="6" strokeLinecap="round" fill="none" />
      </>
    } />
  ),
  // Zoom — big excited grin, wide eyes (greeting you on camera)
  zoom: (
    <Mascot id="zoom" light="#8ec0ff" dark="#0c4aa0" face={
      <>
        <circle cx="81.5" cy="101" r="7.5" fill="#fff" />
        <circle cx="118.5" cy="101" r="7.5" fill="#fff" />
        <path d="M 76 117 Q 100 142 124 117 Q 100 128 76 117 Z" fill="#fff" />
      </>
    } />
  ),
};

/* ── Reasoning-layer icons ────────────────────────────────────────────────────
   These four are internal KAIROS components, not brands, so they get a
   different treatment from the agent mascots — a chip/brain/lens/bolt set,
   each in its own accent color. */
function ReasoningIcon({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 40 40" className="w-8 h-8">
      <rect x="4" y="4" width="32" height="32" rx="10" fill={color} fillOpacity={0.14} stroke={color} strokeOpacity={0.35} />
      <g stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" fill="none" transform="translate(20,20)">
        {children}
      </g>
    </svg>
  );
}

const REASONING_ICONS = {
  // Synthesis Engine — a brain
  synthesis: (
    <ReasoningIcon color="#7c3aed">
      <path d="M-5 -1 Q-6.5 -6.5 0 -7 Q6.5 -6.5 5 -1 Q7 3 3 6 Q1.5 7.4 0 6.2 Q-1.5 7.4 -3 6 Q-7 3 -5 -1 Z" />
      <path d="M0 -7 V6.2 M-5 -1 Q-2 -2 0 0 Q2 -2 5 -1" />
    </ReasoningIcon>
  ),
  // Router — a circuit/chip
  router: (
    <ReasoningIcon color="#6366f1">
      <rect x="-4.5" y="-4.5" width="9" height="9" rx="1.5" />
      <path d="M-4.5 -2 H-7.5 M-4.5 2 H-7.5 M4.5 -2 H7.5 M4.5 2 H7.5 M-2 -4.5 V-7.5 M2 -4.5 V-7.5 M-2 4.5 V7.5 M2 4.5 V7.5" />
    </ReasoningIcon>
  ),
  // Retrieval Engine — a magnifying lens
  retrieval: (
    <ReasoningIcon color="#d946ef">
      <circle cx="-1.3" cy="-1.3" r="4.6" />
      <line x1="1.9" y1="1.9" x2="6.3" y2="6.3" />
    </ReasoningIcon>
  ),
  // Live Agent — a lightbulb (instant, on-demand)
  live: (
    <ReasoningIcon color="#f59e0b">
      <path d="M0 -6.5 A5 5 0 0 1 3 3 L2 5.5 H-2 L-3 3 A5 5 0 0 1 0 -6.5 Z" />
      <path d="M-1.8 7.5 H1.8" />
    </ReasoningIcon>
  ),
} as const;

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

const AGENTS = {
  extraction: [
    { icon: MASCOTS.slack, name: "Slack Agent", desc: "Reads every channel & thread, flags decision moments, captures participants and outcomes." },
    { icon: MASCOTS.gmail, name: "Email Agent", desc: "Scans Gmail for approvals, sign-offs and escalations — links threads to the decisions they made." },
    { icon: MASCOTS.drive, name: "Drive Agent", desc: "Parses docs, specs and proposals in Google Drive for the key choices written down inside them." },
    { icon: MASCOTS.notion, name: "Notion Agent", desc: "Walks pages and databases recursively, extracting decisions logged in specs and wikis." },
    { icon: MASCOTS.github, name: "GitHub Agent", desc: "Reads pull requests and issues — with review comments and discussion — across your most active repos." },
    { icon: MASCOTS.zoom, name: "Meeting Agent", desc: "Transcribes Zoom recordings with Whisper, then pinpoints decisions, timestamps and who was in the room." },
  ],
  reasoning: [
    { icon: REASONING_ICONS.synthesis, name: "Synthesis Engine", desc: "Fuses every source into one decision graph and answers your questions with citations." },
    { icon: REASONING_ICONS.router, name: "Router", desc: "Classifies every query — search, live data, general chat, or ingest — before anything else runs." },
    { icon: REASONING_ICONS.retrieval, name: "Retrieval Engine", desc: "Hybrid semantic + keyword + graph-neighbor search, personalized to your profile and history." },
    { icon: REASONING_ICONS.live, name: "Live Agent", desc: "Skips memory entirely for on-demand questions — \"how many unread emails do I have?\" — answered live." },
  ],
};

const CONNECTORS = [
  { key: "slack", name: "Slack", sub: "Channels & DMs" },
  { key: "gmail", name: "Gmail", sub: "Emails & approvals" },
  { key: "drive", name: "Google Drive", sub: "Docs & specs" },
  { key: "notion", name: "Notion", sub: "Pages & databases" },
  { key: "zoom", name: "Zoom", sub: "Meeting recordings" },
  { key: "jira", name: "Jira", sub: "Tickets & epics" },
  { key: "github", name: "GitHub", sub: "PRs & issues" },
] as const;

const MCP_TOOLS = [
  { title: "Remembers before it answers", desc: "Claude pulls relevant company memory before it answers anything." },
  { title: "Saves what it learns", desc: "Claude writes new decisions back into KAIROS the moment it learns them." },
  { title: "Searches by topic, person, or date", desc: "Structured search across the decision graph with full source citations." },
  { title: "Checks for precedent", desc: "Checks whether a new plan has real precedent — or if you're about to repeat a mistake." },
  { title: "Finds contradictions", desc: "Proactively scans the whole graph for contradictions, stale spend, and bus-factor risk." },
  { title: "Scores decision risk", desc: "Scores every decision 0–100 for staleness, ownership gaps, and unreviewed impact." },
  { title: "Answers live, not just from memory", desc: "Runs the same chat pipeline as the KAIROS UI and returns a sourced answer, right from Claude." },
  { title: "Syncs your sources on demand", desc: "Kicks off a fresh ingestion pass instead of waiting for the automatic 12-minute cycle." },
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
  { n: "01", title: "Connect", body: "One-click OAuth into Slack, Gmail, Drive, Notion, Zoom, GitHub and Jira. No admin install, no IT ticket." },
  { n: "02", title: "Extract", body: "Ten agents read continuously, catching every decision-shaped moment with sources, people, and outcomes." },
  { n: "03", title: "Graph", body: "Every decision auto-links to related ones by topic, person, and timeframe — a living, physics-simulated web." },
  { n: "04", title: "Ask", body: "Query in plain English over chat or any MCP client — cited answers in seconds, or a warning before you repeat a mistake." },
];

/* ── Live-answer demo data (drives the animated showcase) ─────────────────── */
type DemoSource = { label: string; kind: "slack" | "gmail" | "drive" | "notion" | "zoom" | "jira" };
type DemoScenario = {
  q: string;
  answer: { text: string; bold?: boolean }[];
  sources: DemoSource[];
  meta: string;
  risk?: number;
};

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    q: "Why are we paying Vertex Logistics $191K every month?",
    answer: [
      { text: "Contract signed " },
      { text: "November 2019", bold: true },
      { text: " by John Smith, who left in 2022. It has " },
      { text: "auto-renewed three times", bold: true },
      { text: " and was never reviewed. Original rationale: sole-source fulfillment during the Series A ramp. No owner is on record today." },
    ],
    sources: [
      { label: "Email · Nov 2019", kind: "gmail" },
      { label: "#ops-vendors", kind: "slack" },
      { label: "Vertex_MSA.pdf", kind: "drive" },
    ],
    meta: "3 sources · resolved in 3.9s",
    risk: 82,
  },
  {
    q: "Why did we choose React over Vue for the web app?",
    answer: [
      { text: "The frontend team voted " },
      { text: "4–2 for React", bold: true },
      { text: " in a March 2022 thread. Deciding factor: a larger hiring pool in the region. The Vue advocate, " },
      { text: "Priya, is still on the team", bold: true },
      { text: " — worth looping in before any reversal." },
    ],
    sources: [
      { label: "#frontend-arch", kind: "slack" },
      { label: "Stack Decision", kind: "notion" },
    ],
    meta: "2 sources · resolved in 3.2s",
  },
  {
    q: "Has anyone tried to build a mobile app before?",
    answer: [
      { text: "Yes — attempted in " },
      { text: "2021", bold: true },
      { text: ", shut down at the March board meeting. Root cause: no in-house mobile expertise. Cost: " },
      { text: "₹40 lakh", bold: true },
      { text: ". The postmortem is in memory — read it before you repeat it." },
    ],
    sources: [
      { label: "Board Call · Mar 2021", kind: "zoom" },
      { label: "Mobile_Postmortem", kind: "drive" },
    ],
    meta: "2 sources · resolved in 4.1s",
  },
];

const COMPARE = [
  {
    them: "Confluence · Notion · SharePoint",
    themDesc: "Store the documents you deliberately sit down and write.",
    us: "Understands the decisions you actually make",
    usDesc: "Mines Slack threads, email approvals, and meeting calls — where real choices live, unwritten.",
  },
  {
    them: "Full-text search",
    themDesc: "Returns ten blue links and leaves the reasoning to you.",
    us: "Returns the answer, with its sources",
    usDesc: "Who decided, when, why, what was rejected — synthesized and cited in one reply.",
  },
  {
    them: "A passive archive",
    themDesc: "Waits, silent, until someone thinks to search it.",
    us: "A proactive watchdog",
    usDesc: "Scores decision debt, flags contradictions, and warns you before a mistake repeats.",
  },
];

/* ── AMD hardware — real, sourced silicon specs (AMD datasheets + product briefs) ── */
const AMD_GPU_SPECS = [
  { label: "Architecture", mi300x: "CDNA 3", mi350x: "CDNA 4", mi355x: "CDNA 4" },
  { label: "Process node", mi300x: "5nm compute + 6nm I/O (chiplet)", mi350x: "3nm (N3P) + 6nm I/O", mi355x: "3nm (N3P) + 6nm I/O" },
  { label: "Transistors", mi300x: "153B", mi350x: "185B", mi355x: "185B" },
  { label: "Compute units", mi300x: "304", mi350x: "256 (8 XCDs × 32)", mi355x: "256 (8 XCDs × 32)" },
  { label: "Matrix cores", mi300x: "1,216", mi350x: "1,024", mi355x: "1,024" },
  { label: "Peak clock", mi300x: "2,100 MHz", mi350x: "2,200 MHz", mi355x: "2,400 MHz" },
  { label: "Memory", mi300x: "192GB HBM3", mi350x: "288GB HBM3E", mi355x: "288GB HBM3E" },
  { label: "Memory bandwidth", mi300x: "5.3 TB/s", mi350x: "8 TB/s", mi355x: "8 TB/s" },
  { label: "Peak FP16/BF16 (matrix)", mi300x: "1,307 TFLOPS", mi350x: "≈2.3 PFLOPS dense", mi355x: "2.5 PFLOPS dense · 5.0 PFLOPS (2:4 sparse)" },
  { label: "Peak FP8/INT8 (matrix)", mi300x: "2,615 TFLOPS", mi350x: "≈4.6 PFLOPS dense", mi355x: "5.0 PFLOPS dense · 10.1 PFLOPS (2:4 sparse)" },
  { label: "Native FP6 / FP4", mi300x: "Not supported", mi350x: "MXFP6 · MXFP4", mi355x: "MXFP6 · MXFP4, 10.1 PFLOPS" },
  { label: "Interconnect", mi300x: "Infinity Fabric 3.0, ~896 GB/s", mi350x: "7× Infinity Fabric links", mi355x: "7× Infinity Fabric links @ 153 GB/s each" },
  { label: "TDP", mi300x: "750W", mi350x: "1,000W (air-cooled)", mi355x: "1,400W (liquid-cooled)" },
] as const;

/* ── Gemma 4 model family (Google DeepMind — hackathon co-sponsor) ─────────── */
const GEMMA_MODELS = [
  { name: "E2B", params: "2.3B effective", ctx: "128K", modalities: "Text · Image · Audio", note: "On-device — phones, laptops" },
  { name: "E4B", params: "4.5B effective (8B total)", ctx: "128K", modalities: "Text · Image · Audio", note: "Balanced on-device tier" },
  { name: "12B", params: "12B, encoder-free", ctx: "256K", modalities: "Text · Image · Audio · Video", note: "Direct linear projections replace vision/audio encoders" },
  { name: "26B-A4B", params: "26B total / 3.8B active (MoE)", ctx: "256K", modalities: "Text · Image", note: "Powers KAIROS's Intent Agent — dense-4B cost, MoE reasoning" },
  { name: "31B", params: "31B dense (32.2B)", ctx: "256K", modalities: "Text · Image · Video", note: "Server-grade — the top of the family" },
] as const;

const GEMMA_MODEL_SIZES = ["E2B", "E4B", "12B", "26B-A4B", "31B"] as const;

// Official Gemma 4 model-card benchmarks (ai.google.dev/gemma/docs/core/model_card_4),
// one axis (0-100 score) across all five model sizes — Codeforces ELO is a different
// scale and is deliberately left off this chart rather than mixed onto a second axis.
const GEMMA_BENCHMARK_SERIES = [
  { key: "aime", label: "AIME 2026 (math)", color: "#3987e5", values: [37.5, 42.5, 77.5, 88.3, 89.2] },
  { key: "gpqa", label: "GPQA Diamond (science)", color: "#199e70", values: [43.4, 58.6, 78.8, 82.3, 84.3] },
  { key: "mmlu", label: "MMLU-Pro (knowledge)", color: "#c98500", values: [60.0, 69.4, 77.2, 82.6, 85.2] },
  { key: "bbeh", label: "BigBench Extra Hard (reasoning)", color: "#008300", values: [21.9, 33.1, 53.0, 64.8, 74.4] },
  { key: "lcb", label: "LiveCodeBench v6 (code)", color: "#9085e9", values: [44.0, 52.0, 72.0, 77.1, 80.0] },
] as const;

/* ── Gemma 4 benchmark chart (hand-written SVG, no charting library) ───────
   Multi-series line chart: one axis (0-100 score), 5 official model-card
   benchmarks across the 5 Gemma 4 sizes. Legend + direct endpoint value
   labels carry series identity (categorical hues alone sit in the CVD
   floor band per the palette's own validator); a crosshair + one shared
   tooltip read every series at the hovered model size; the legend itself
   is interactive (hover to isolate, click to toggle a series); and a
   table view is always one click away so nothing here is color-only. */
function GemmaBenchmarkChart() {
  const W = 760;
  const H = 380;
  const padL = 34;
  const padR = 54;
  const padT = 16;
  const padB = 34;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const n = GEMMA_MODEL_SIZES.length;

  const xAt = (i: number) => padL + (i / (n - 1)) * plotW;
  const yAt = (v: number) => padT + plotH - (v / 100) * plotH;

  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set());
  const [showTable, setShowTable] = useState(false);

  const visibleSeries = GEMMA_BENCHMARK_SERIES.filter((s) => !hiddenKeys.has(s.key));

  const toggleKey = (key: string) => {
    setHiddenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let closest = 0;
    let closestDist = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(xAt(i) - px);
      if (d < closestDist) {
        closestDist = d;
        closest = i;
      }
    }
    setHover(closest);
  };

  // Stack the endpoint value labels (final category) with a minimum gap so
  // near-identical scores (e.g. GPQA 84.3 vs MMLU-Pro 85.2) don't overlap —
  // nudged labels get a short leader line back to their true data point.
  // Only visible (non-hidden) series participate, so toggling a line off
  // lets its neighbors re-settle into the freed vertical space.
  const LABEL_GAP = 14;
  const endpoints = visibleSeries
    .map((s) => ({ key: s.key, color: s.color, trueY: yAt(s.values[n - 1]), labelY: yAt(s.values[n - 1]) }))
    .sort((a, b) => a.trueY - b.trueY);
  for (let i = 1; i < endpoints.length; i++) {
    if (endpoints[i].labelY - endpoints[i - 1].labelY < LABEL_GAP) {
      endpoints[i].labelY = endpoints[i - 1].labelY + LABEL_GAP;
    }
  }
  if (endpoints.length) {
    const overflow = endpoints[endpoints.length - 1].labelY - (padT + plotH);
    if (overflow > 0) endpoints.forEach((e) => (e.labelY -= overflow));
  }
  const labelYByKey = Object.fromEntries(endpoints.map((e) => [e.key, e.labelY]));

  const yTicks = [0, 20, 40, 60, 80, 100];

  return (
    <div className="w-full">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-6">
        {GEMMA_BENCHMARK_SERIES.map((s) => {
          const isHidden = hiddenKeys.has(s.key);
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => toggleKey(s.key)}
              onMouseEnter={() => setFocusKey(s.key)}
              onMouseLeave={() => setFocusKey(null)}
              className="flex items-center gap-2 text-[11.5px] font-mono transition-opacity"
              style={{ opacity: isHidden ? 0.4 : 1 }}
            >
              <span
                className="inline-block w-3 h-[3px] rounded-full transition-opacity"
                style={{ background: s.color, opacity: isHidden ? 0.35 : 1 }}
              />
              <span className={`text-zinc-400 ${isHidden ? "line-through decoration-zinc-600" : ""}`}>{s.label}</span>
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="ml-auto text-[11px] font-mono text-violet-400 hover:text-violet-300 transition-colors underline decoration-violet-500/40 underline-offset-2"
        >
          {showTable ? "View as chart" : "View as table"}
        </button>
      </div>

      {showTable ? (
        <div className="overflow-x-auto rounded-xl border border-violet-500/15">
          <table className="w-full text-sm border-collapse min-w-[560px]">
            <thead>
              <tr className="bg-white/[0.03] text-left text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                <th className="px-4 py-3 font-medium">Benchmark</th>
                {GEMMA_MODEL_SIZES.map((c) => (
                  <th key={c} className="px-4 py-3 font-medium text-right">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-violet-500/10">
              {GEMMA_BENCHMARK_SERIES.map((s) => (
                <tr key={s.key}>
                  <td className="px-4 py-3 font-mono text-zinc-300 whitespace-nowrap">
                    <span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: s.color }} />
                    {s.label}
                  </td>
                  {s.values.map((v, i) => (
                    <td key={i} className="px-4 py-3 text-right font-mono text-zinc-300">{v.toFixed(1)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto select-none"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={padL + plotW} y1={yAt(t)} y2={yAt(t)} stroke="#2c2c2a" strokeWidth={1} />
              <text x={padL - 8} y={yAt(t)} textAnchor="end" dominantBaseline="middle" fill="#898781" fontSize={10.5} fontFamily="monospace">
                {t}
              </text>
            </g>
          ))}

          {GEMMA_MODEL_SIZES.map((c, i) => (
            <text key={c} x={xAt(i)} y={H - padB + 20} textAnchor="middle" fill="#898781" fontSize={11} fontFamily="monospace">
              {c}
            </text>
          ))}

          {hover !== null && (
            <line x1={xAt(hover)} x2={xAt(hover)} y1={padT} y2={padT + plotH} stroke="#52514e" strokeWidth={1} />
          )}

          {visibleSeries.map((s) => {
            const d = s.values.map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(2)},${yAt(v).toFixed(2)}`).join(" ");
            const trueEndY = yAt(s.values[n - 1]);
            const labelY = labelYByKey[s.key];
            const dimmed = focusKey !== null && focusKey !== s.key;
            const emphasized = focusKey === s.key;
            return (
              <g key={s.key} style={{ transition: "opacity 150ms" }} opacity={dimmed ? 0.2 : 1}>
                <path
                  d={d}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={emphasized ? 3 : 2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ transition: "stroke-width 150ms" }}
                />
                {s.values.map((v, i) => (
                  <circle
                    key={i}
                    cx={xAt(i)}
                    cy={yAt(v)}
                    r={hover === i ? 5.5 : 4}
                    fill={s.color}
                    stroke="#0b0b0d"
                    strokeWidth={2}
                    style={{ transition: "r 120ms" }}
                  />
                ))}
                {Math.abs(labelY - trueEndY) > 1 && (
                  <line x1={xAt(n - 1) + 3} y1={trueEndY} x2={xAt(n - 1) + 9} y2={labelY} stroke={s.color} strokeWidth={1} opacity={0.55} />
                )}
                <text x={xAt(n - 1) + 11} y={labelY} dominantBaseline="middle" fill="#d4d4d8" fontSize={10.5} fontFamily="monospace">
                  {s.values[n - 1].toFixed(1)}
                </text>
              </g>
            );
          })}

          {hover !== null && visibleSeries.length > 0 && (() => {
            const tipW = 208;
            const tipH = 26 + visibleSeries.length * 16 + 6;
            const tx = xAt(hover);
            const tipX = tx + 16 + tipW > W - 4 ? tx - 16 - tipW : tx + 16;
            const tipY = padT + 4;
            return (
              <g pointerEvents="none">
                <rect x={tipX} y={tipY} width={tipW} height={tipH} rx={9} fill="#101012" stroke="#2c2c2a" strokeWidth={1} />
                <text x={tipX + 12} y={tipY + 19} fill="#ffffff" fontSize={11.5} fontWeight={700} fontFamily="monospace">
                  Gemma 4 {GEMMA_MODEL_SIZES[hover]}
                </text>
                {visibleSeries.map((s, i) => {
                  const rowY = tipY + 38 + i * 16;
                  return (
                    <g key={s.key}>
                      <line x1={tipX + 12} x2={tipX + 25} y1={rowY - 4} y2={rowY - 4} stroke={s.color} strokeWidth={2.5} />
                      <text x={tipX + 31} y={rowY} fill="#a1a1aa" fontSize={10} fontFamily="monospace">
                        {s.label.split(" (")[0]}
                      </text>
                      <text x={tipX + tipW - 12} y={rowY} textAnchor="end" fill="#ffffff" fontSize={10.5} fontWeight={700} fontFamily="monospace">
                        {s.values[hover].toFixed(1)}%
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })()}
        </svg>
      )}
      <p className="mt-3 text-[11px] text-zinc-600 font-mono">
        Source: Gemma 4 model card — ai.google.dev/gemma/docs/core/model_card_4
      </p>
    </div>
  );
}

/* ── Live-answer demo showcase ───────────────────────────────────────────── */
const SOURCE_TINT: Record<DemoSource["kind"], string> = {
  slack: "#E01E5A",
  gmail: "#ea4335",
  drive: "#00ac47",
  notion: "#e5e5e5",
  zoom: "#2D8CFF",
  jira: "#0065FF",
};

function DemoShowcase() {
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [phase, setPhase] = useState<"typing" | "thinking" | "answer">("typing");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const scenario = DEMO_SCENARIOS[idx];
    const q = scenario.q;
    let cancelled = false;
    const push = (fn: () => void, ms: number) => {
      const t = setTimeout(() => {
        if (!cancelled) fn();
      }, ms);
      timers.current.push(t);
    };

    setTyped("");
    setPhase("typing");

    // Typewriter for the question
    let i = 0;
    const typeNext = () => {
      if (cancelled) return;
      i += 1;
      setTyped(q.slice(0, i));
      if (i < q.length) {
        push(typeNext, 26 + Math.random() * 26);
      } else {
        push(() => setPhase("thinking"), 420);
        push(() => setPhase("answer"), 420 + 1150);
        // Hold the answer, then advance to the next scenario
        push(() => setIdx((p) => (p + 1) % DEMO_SCENARIOS.length), 420 + 1150 + 5200);
      }
    };
    push(typeNext, 340);

    return () => {
      cancelled = true;
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [idx]);

  const scenario = DEMO_SCENARIOS[idx];

  return (
    <div className="relative rounded-2xl border border-violet-500/20 bg-[#0a0a0c]/90 backdrop-blur-xl shadow-[0_30px_80px_-30px_rgba(139,92,246,0.5)] overflow-hidden">
      {/* window chrome */}
      <div className="flex items-center gap-2 px-4 h-11 border-b border-white/5 bg-white/[0.02]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-[11px] font-mono text-zinc-500">kairos · ask anything</span>
        <span className="ml-auto flex items-center gap-1.5 text-[10px] font-mono text-emerald-400/80">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> live
        </span>
      </div>

      <div className="p-5 sm:p-7 min-h-[340px] flex flex-col">
        {/* user question */}
        <div className="flex justify-end mb-5">
          <div className="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-br-md bg-violet-600/90 text-white text-sm sm:text-[15px] leading-relaxed font-sans">
            {typed}
            {phase === "typing" && <span className="inline-block w-[2px] h-[1.05em] align-middle ml-0.5 bg-white/80 animate-pulse" />}
          </div>
        </div>

        {/* assistant */}
        <div className="flex items-start gap-3">
          <div className="shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-xs font-black text-white shadow-[0_0_18px_rgba(139,92,246,0.5)]">
            K
          </div>
          <div className="flex-1 min-w-0">
            {phase === "thinking" && (
              <div className="flex items-center gap-1.5 h-8" aria-label="KAIROS is thinking">
                {[0, 1, 2].map((d) => (
                  <span
                    key={d}
                    className="w-1.5 h-1.5 rounded-full bg-violet-400"
                    style={{ animation: `demoWave 1s ease-in-out ${d * 0.15}s infinite` }}
                  />
                ))}
                <span className="ml-2 text-xs font-mono text-zinc-500">checking your company&apos;s memory…</span>
              </div>
            )}

            {phase === "answer" && (
              <div style={{ animation: "demoFade .5s cubic-bezier(.16,1,.3,1)" }}>
                <p className="text-sm sm:text-[15px] text-zinc-200 leading-relaxed font-sans">
                  {scenario.answer.map((seg, k) =>
                    seg.bold ? (
                      <strong key={k} className="text-white font-semibold">{seg.text}</strong>
                    ) : (
                      <span key={k}>{seg.text}</span>
                    )
                  )}
                </p>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {scenario.sources.map((s) => (
                    <span
                      key={s.label}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono text-zinc-300"
                      style={{ borderColor: `${SOURCE_TINT[s.kind]}44`, background: `${SOURCE_TINT[s.kind]}12` }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: SOURCE_TINT[s.kind] }} />
                      {s.label}
                    </span>
                  ))}
                </div>

                <div className="mt-4 flex items-center gap-3 text-[11px] font-mono text-zinc-500">
                  <span>{scenario.meta}</span>
                  {scenario.risk != null && (
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/25 text-amber-300">
                      ⚠ risk {scenario.risk}/100
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* scenario dots */}
        <div className="mt-auto pt-6 flex items-center justify-center gap-2">
          {DEMO_SCENARIOS.map((_, k) => (
            <button
              key={k}
              onClick={() => setIdx(k)}
              aria-label={`Show example ${k + 1}`}
              className="h-1.5 rounded-full transition-all"
              style={{
                width: k === idx ? 22 : 6,
                background: k === idx ? "rgb(167,139,250)" : "rgba(255,255,255,0.18)",
              }}
            />
          ))}
        </div>
      </div>
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

  // Fade to the shared background color before navigating, instead of a hard
  // jump cut — /dashboard opens on the same dark bg so it reads as one continuous transition.
  const [isLeaving, setIsLeaving] = useState(false);
  const enter = useCallback(() => {
    setIsLeaving(true);
    setTimeout(() => router.push("/dashboard"), 220);
  }, [router]);
  const [signInError, setSignInError] = useState<string | null>(null);
  const signIn = useCallback(async () => {
    setSignInError(null);
    try {
      await loginWithGoogle();
      setIsLeaving(true);
      setTimeout(() => router.push("/dashboard"), 220);
    } catch (err) {
      // Don't redirect on failure — a silent bounce to /dashboard's login
      // gate looks like nothing happened. Tell the user here instead.
      setSignInError(err instanceof Error ? err.message : "Sign-in failed. Please try again.");
    }
  }, [loginWithGoogle, router]);

  return (
    <main className="relative min-h-screen w-full bg-[#080808] text-[#ededed] overflow-x-hidden font-serif">
      {/* Fade-to-black overlay, shown while a nav to /dashboard is in flight */}
      <div
        className="fixed inset-0 z-[200] pointer-events-none bg-[#080808]"
        style={{ opacity: isLeaving ? 1 : 0, transition: "opacity 220ms var(--ease-out-quint)" }}
      />
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
        className="fixed top-0 inset-x-0 z-50 transition-all duration-300 bg-[#080808]"
        style={{
          borderBottom: scrolled ? "1px solid rgba(139,92,246,0.12)" : "1px solid transparent",
        }}
      >
        <div className="w-full px-6 md:px-10 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <KairosLogo size={30} showText />
            <span className="text-zinc-600 text-sm">×</span>
            <AMDLogo className="h-4 text-white" />
            <span className="text-zinc-600 text-sm">×</span>
            <GemmaLogo className="text-xl" />
          </div>
          <div className="hidden md:flex items-center gap-6 text-xs font-mono tracking-wide text-zinc-400">
            <a href="#demo" className="hover:text-white transition-colors">Demo</a>
            <a href="#problem" className="hover:text-white transition-colors">The Problem</a>
            <a href="#agents" className="hover:text-white transition-colors">Agents</a>
            <a href="#intelligence" className="hover:text-white transition-colors">Intelligence</a>
            <a href="#why" className="hover:text-white transition-colors">Why KAIROS</a>
            <a href="#mcp" className="hover:text-white transition-colors">MCP</a>
          </div>
          <Magnetic strength={0.25}>
            <button
              onClick={enter}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 transition-colors text-white shadow-[0_0_20px_rgba(139,92,246,0.35)]"
            >
              {user ? "Open Dashboard" : "Enter KAIROS"}
            </button>
          </Magnetic>
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

          <h1 className="text-5xl md:text-7xl font-display font-bold leading-[1.05] tracking-tight">
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
            <Magnetic strength={0.3}>
              <button
                onClick={enter}
                className="px-7 py-3.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 transition-all text-white shadow-[0_0_30px_rgba(139,92,246,0.45)] hover:shadow-[0_0_44px_rgba(139,92,246,0.65)] hover:-translate-y-0.5"
              >
                {user ? "Open Dashboard →" : "Enter KAIROS →"}
              </button>
            </Magnetic>
            {!user && (
              <button
                onClick={signIn}
                className="px-7 py-3.5 rounded-xl text-sm font-semibold bg-white/5 border border-violet-500/20 hover:bg-white/10 hover:border-violet-500/40 transition-all text-white flex items-center gap-3"
              >
                <svg className="w-4 h-4" viewBox="0 0 48 48">
                  <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
                  <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
                  <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
                  <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
                </svg>
                Sign in with Google
              </button>
            )}
          </div>

          {signInError && (
            <p className="mt-4 text-xs text-rose-400 max-w-md mx-auto">{signInError}</p>
          )}

          <div className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[11px] font-mono tracking-wide text-zinc-500">
            <span><span className="text-violet-300 font-semibold">10</span> parallel agents</span>
            <span className="text-zinc-700">·</span>
            <span><span className="text-violet-300 font-semibold">7</span> connectors</span>
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

      {/* ── Live demo ── */}
      <section id="demo" className="relative py-24 md:py-28 px-6">
        <div className="max-w-5xl mx-auto">
          <Reveal className="text-center mb-12">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">See It Answer</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
              Ask the question everyone forgot.
            </h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Not a search box that hands you links — a straight answer with the who, when, and why,
              every claim traced to its source.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <DemoShowcase />
          </Reveal>
        </div>
      </section>

      {/* ── Problem ── */}
      <section id="problem" className="relative py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">The Problem</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
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

      {/* ── How it works ── */}
      <section id="how" className="relative py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">How It Works</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">From raw chatter to cited answers</h2>
          </Reveal>

          <div className="grid md:grid-cols-4 gap-5 relative">
            <div className="hidden md:block absolute top-8 left-[12%] right-[12%] h-px bg-gradient-to-r from-violet-500/0 via-violet-500/30 to-violet-500/0" />
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 100}>
                <div className="relative flex flex-col items-center text-center gap-3">
                  <div className="relative z-10 w-16 h-16 rounded-2xl border border-violet-500/25 bg-[#0b0b0d] flex items-center justify-center text-lg font-mono font-bold text-violet-300 shadow-[0_0_24px_rgba(139,92,246,0.15)]">
                    {s.n}
                  </div>
                  <h3 className="text-base font-semibold">{s.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans max-w-[15rem]">{s.body}</p>
                </div>
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
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">Nine agents, running in parallel</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Orchestrated with LangGraph — five own a source and extract decisions, four reason
              over the graph to route, retrieve, synthesize and answer live queries.
            </p>
          </Reveal>

          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Extraction Agents</p>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mb-14">
            {AGENTS.extraction.map((a, i) => (
              <Reveal key={a.name} delay={i * 80}>
                <div className="group h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:bg-white/[0.04] hover:border-violet-500/40 transition-all">
                  <div className="w-16 h-16 -ml-1 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <div className="animate-mascot-float" style={{ animationDelay: `${i * 0.15}s` }}>
                      {a.icon}
                    </div>
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{a.name}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{a.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Reasoning Layer</p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
            {AGENTS.reasoning.map((a, i) => (
              <Reveal key={a.name} delay={i * 80}>
                <div className="group h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:bg-white/[0.04] hover:border-violet-500/40 transition-all">
                  <div className="w-12 h-12 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                    {a.icon}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{a.name}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{a.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Decision Intelligence ── */}
      <section id="intelligence" className="relative py-28 px-6 overflow-hidden">
        <div
          className="absolute top-0 right-0 w-[40rem] h-[40rem] rounded-full bg-fuchsia-700/10 blur-[150px] pointer-events-none"
        />
        <div className="max-w-6xl mx-auto relative">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">New — Proactive, Not Just Reactive</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
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
                <TiltCard className="h-full p-6 rounded-2xl border border-violet-500/15 bg-gradient-to-b from-violet-500/[0.03] to-transparent hover:border-violet-500/40 transition-colors flex flex-col">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-xl">
                      {f.icon}
                    </div>
                    <span className="font-mono text-[10.5px] text-violet-400">{f.tool}()</span>
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
            <div className="p-6 md:p-8 rounded-2xl border border-violet-500/20 bg-[#0b0b0d] flex flex-col md:flex-row items-center gap-8">
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
      <section id="connectors" className="relative py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Connectors</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">Connect once. No passwords to hand over.</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              You sign in and connect your own accounts — no admin, no IT ticket. KAIROS keeps
              reading in the background and your decision graph stays up to date.
            </p>
          </Reveal>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 items-stretch">
            {CONNECTORS.map((c, i) => (
              <Reveal key={c.key} delay={i * 80} className="h-full">
                <TiltCard className="h-full p-6 rounded-2xl border border-violet-500/15 bg-white/[0.02] hover:border-violet-500/35 transition-colors flex flex-col items-center justify-center text-center gap-3">
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

      {/* ── Comparison ── */}
      <section id="why" className="relative py-28 px-6">
        <div className="max-w-5xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Why Not Just Confluence?</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
              A wiki stores what you write.
              <br />
              <span className="text-zinc-500">KAIROS remembers what you decided.</span>
            </h2>
          </Reveal>

          <div className="space-y-4">
            {COMPARE.map((row, i) => (
              <Reveal key={row.us} delay={i * 110}>
                <div className="grid md:grid-cols-2 rounded-2xl border border-violet-500/15 overflow-hidden">
                  <div className="p-6 md:p-7 bg-white/[0.015] border-b md:border-b-0 md:border-r border-violet-500/10">
                    <div className="flex items-center gap-2 mb-2.5">
                      <span className="text-zinc-600 text-lg leading-none">✕</span>
                      <span className="text-sm font-semibold text-zinc-400">{row.them}</span>
                    </div>
                    <p className="text-sm text-zinc-500 leading-relaxed font-sans">{row.themDesc}</p>
                  </div>
                  <div className="p-6 md:p-7 bg-gradient-to-br from-violet-600/[0.08] to-transparent">
                    <div className="flex items-center gap-2 mb-2.5">
                      <span className="text-violet-400 text-lg leading-none">✓</span>
                      <span className="text-sm font-semibold text-white">{row.us}</span>
                    </div>
                    <p className="text-sm text-zinc-300 leading-relaxed font-sans">{row.usDesc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── MCP ── */}
      <section id="mcp" className="relative py-28 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Works With Your AI</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">KAIROS MCP</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Connect Claude, ChatGPT, or Cursor straight to your company&apos;s memory. Before it
              answers you, your AI checks what KAIROS already knows. The moment it learns something
              new and important, it saves that back to KAIROS too — so the next question, from
              anyone, gets a smarter answer.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-5 mb-12">
            {MCP_TOOLS.map((t, i) => (
              <Reveal key={t.title} delay={i * 110}>
                <div className="h-full p-6 rounded-2xl border border-violet-500/15 bg-[#0c0c0e] hover:border-violet-500/30 transition-all">
                  <h3 className="text-[15px] font-semibold text-white mb-2.5">{t.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed font-sans">{t.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── AMD ── */}
      <section id="amd" className="relative py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <AMDLogo className="h-7 md:h-9 text-white mx-auto mb-6" />
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Hardware Partner</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
              Every model call runs on <span className="text-white">AMD Instinct</span>.
            </h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Fireworks AI — KAIROS&apos;s primary LLM provider — is AMD&apos;s official inference
              partner. Every Fireworks call KAIROS makes (synthesis, extraction, embeddings,
              intent classification) runs on AMD Instinct accelerators, not NVIDIA.
            </p>
          </Reveal>

          <Reveal delay={80}>
            <div className="mb-10 overflow-x-auto rounded-2xl border border-violet-500/15">
              <table className="w-full text-sm border-collapse min-w-[720px]">
                <thead>
                  <tr className="bg-white/[0.03] text-left text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                    <th className="px-5 py-3.5 font-medium">Spec</th>
                    <th className="px-5 py-3.5 font-medium">MI300X</th>
                    <th className="px-5 py-3.5 font-medium">MI350X</th>
                    <th className="px-5 py-3.5 font-medium">
                      MI355X
                      <span className="ml-2 inline-block px-1.5 py-0.5 rounded text-[9.5px] font-sans font-semibold bg-violet-500/20 text-violet-300 align-middle normal-case tracking-normal">
                        FLAGSHIP
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-violet-500/10">
                  {AMD_GPU_SPECS.map((row) => (
                    <tr key={row.label} className="transition-colors hover:bg-violet-500/[0.04]">
                      <td className="px-5 py-3.5 font-mono text-[12.5px] text-zinc-500 whitespace-nowrap">{row.label}</td>
                      <td className="px-5 py-3.5 text-zinc-300 font-sans whitespace-nowrap">{row.mi300x}</td>
                      <td className="px-5 py-3.5 text-zinc-300 font-sans whitespace-nowrap">{row.mi350x}</td>
                      <td className="px-5 py-3.5 text-white font-sans font-medium whitespace-nowrap">{row.mi355x}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Reveal>

          <Reveal delay={200}>
            <div className="p-6 md:p-8 rounded-2xl border border-violet-500/20 bg-[#0b0b0d] grid md:grid-cols-3 gap-6">
              <div>
                <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-400 mb-2">Compute stack</p>
                <p className="text-lg text-white font-semibold mb-1.5">ROCm, hipBLASLt, Composable Kernel</p>
                <p className="text-sm text-zinc-400 leading-relaxed font-sans">
                  Fireworks&apos; serving stack targets AMD&apos;s open ROCm runtime directly — vLLM
                  and SGLang kernels compiled against Instinct, no CUDA translation layer in the path.
                </p>
              </div>
              <div>
                <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-400 mb-2">Native low-precision</p>
                <p className="text-lg text-white font-semibold mb-1.5">MXFP6 / MXFP4, 2:4 sparsity</p>
                <p className="text-sm text-zinc-400 leading-relaxed font-sans">
                  New in CDNA 4 (MI350X/MI355X) — structured 2:4 sparsity alone doubles matrix
                  throughput, from 5.0 to 10.1 PFLOPS FP8 on the MI355X.
                </p>
              </div>
              <div>
                <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-400 mb-2">Chiplet packaging</p>
                <p className="text-lg text-white font-semibold mb-1.5">8 XCDs, 3D-stacked</p>
                <p className="text-sm text-zinc-400 leading-relaxed font-sans">
                  Every Instinct GPU KAIROS runs on is a multi-die package — compute dies on the
                  leading node, I/O dies on a cheaper one, stitched together over Infinity Fabric.
                </p>
              </div>
            </div>
          </Reveal>

          <Reveal delay={280}>
            <div className="mt-6 p-6 md:p-8 rounded-2xl border border-violet-500/25 bg-gradient-to-br from-violet-600/[0.08] to-transparent">
              <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-300 mb-3">Impact on KAIROS</p>
              <p className="text-base text-white leading-relaxed font-sans max-w-3xl">
                KAIROS fans ten agents out in parallel every ingestion cycle — Slack, Gmail, Drive,
                Notion, Zoom, Jira, GitHub, plus Intent, Context, and Synthesis reasoning over
                whatever they pull in. That only stays cheap and fast because Fireworks&apos; paid
                AMD Instinct capacity clears far more tokens/minute than a free-tier fallback would
                — the ingestion throttle in <span className="text-violet-300 font-mono text-[13px]">config.py</span> (24
                items/cycle) exists for the Groq safety-net path, not the AMD-backed primary one.
                Bigger HBM capacity (192–288GB) also means Fireworks can batch many users&apos;
                concurrent requests on one accelerator without KAIROS ever seeing it queue.
              </p>
            </div>
          </Reveal>

          <p className="mt-6 text-xs text-zinc-600 font-mono">
            Specs: AMD Instinct MI300X/MI350X/MI355X datasheets, amd.com. KAIROS also draws on the
            $50 Fireworks AI credit issued through the AMD AI Developer Program.
          </p>
        </div>
      </section>

      {/* ── Gemma ── */}
      <section id="gemma" className="relative py-28 px-6 bg-gradient-to-b from-transparent via-violet-950/10 to-transparent overflow-hidden">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <GemmaLogo className="text-3xl md:text-4xl justify-center mb-6" />
            <p className="text-xs font-mono tracking-[0.25em] text-violet-400 uppercase mb-4">Model Partner — Google DeepMind</p>
            <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight">
              Five sizes. One family.
              <br />
              <span className="text-zinc-500">One of them, live in KAIROS.</span>
            </h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto font-sans">
              Gemma 4 shipped April 2026 under a clean Apache 2.0 license — the first time
              Google DeepMind&apos;s open-weight family has dropped the old research-only terms.
              Every size takes text and image input natively; KAIROS&apos;s{" "}
              <span className="text-violet-300 font-mono text-[13px]">IntentAgent</span> calls the
              26B-A4B mixture-of-experts directly, on the AMD Instinct hardware above, for cheap,
              latency-sensitive query classification — falling back to the primary Fireworks chain
              if it&apos;s ever unavailable.
            </p>
          </Reveal>

          <Reveal delay={80}>
            <div className="mb-14 overflow-x-auto rounded-2xl border border-violet-500/15">
              <table className="w-full text-sm border-collapse min-w-[640px]">
                <thead>
                  <tr className="bg-white/[0.03] text-left text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                    <th className="px-5 py-3.5 font-medium">Model</th>
                    <th className="px-5 py-3.5 font-medium">Parameters</th>
                    <th className="px-5 py-3.5 font-medium">Context</th>
                    <th className="px-5 py-3.5 font-medium">Modalities</th>
                    <th className="px-5 py-3.5 font-medium">Role</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-violet-500/10">
                  {GEMMA_MODELS.map((m) => (
                    <tr
                      key={m.name}
                      className={`transition-colors hover:bg-violet-500/[0.04] ${
                        m.name === "26B-A4B" ? "bg-violet-500/[0.06]" : ""
                      }`}
                    >
                      <td className="px-5 py-4 font-mono font-semibold text-white whitespace-nowrap">
                        Gemma 4 {m.name}
                        {m.name === "26B-A4B" && (
                          <span className="ml-2 inline-block px-1.5 py-0.5 rounded text-[9.5px] font-sans font-semibold bg-violet-500/20 text-violet-300 align-middle">
                            USED IN KAIROS
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-zinc-400 font-sans whitespace-nowrap">{m.params}</td>
                      <td className="px-5 py-4 text-zinc-400 font-mono whitespace-nowrap">{m.ctx}</td>
                      <td className="px-5 py-4 text-zinc-400 font-sans whitespace-nowrap">{m.modalities}</td>
                      <td className="px-5 py-4 text-zinc-400 font-sans">{m.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Reveal>

          <Reveal delay={160}>
            <div className="p-6 md:p-9 rounded-2xl border border-violet-500/15 bg-[#0b0b0d]">
              <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-8">
                <div>
                  <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-400 mb-2">Official Gemma 4 Model-Card Benchmarks</p>
                  <h3 className="text-xl font-semibold text-white">Score climbs with every size, across every discipline</h3>
                </div>
                <p className="text-xs text-zinc-500 font-sans max-w-xs">Hover any point on the chart for the full breakdown at that size.</p>
              </div>
              <GemmaBenchmarkChart />
            </div>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-6 p-6 md:p-8 rounded-2xl border border-violet-500/25 bg-gradient-to-br from-violet-600/[0.08] to-transparent">
              <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-violet-300 mb-3">Impact on KAIROS</p>
              <p className="text-base text-white leading-relaxed font-sans max-w-3xl">
                <span className="text-violet-300 font-mono text-[13px]">IntentAgent</span> runs
                first on every single query — before Context or Synthesis ever sees it — deciding
                whether you asked to search memory, pull live Gmail/Drive/Jira data, or just record
                a new decision. Before this, that classification hop rode the same flagship
                reasoning model (qwen3p7-plus) as the answer itself, paying its full latency and
                cost twice per question. Routing it to Gemma 4&apos;s 26B-A4B instead — 3.8B active
                parameters, so it runs at dense-4B speed — cuts that first hop&apos;s cost and
                latency without giving up the instruction-following reliability a raw 4B dense model
                would sacrifice, since the fallback in <span className="text-violet-300 font-mono text-[13px]">agents/intent_agent.py</span> only
                drops back to the primary chain if Gemma itself is unavailable.
              </p>
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
          <h2 className="text-4xl md:text-6xl font-display font-bold tracking-tight">
            Stop losing the <span className="text-violet-300">why</span>.
          </h2>
          <p className="mt-5 text-zinc-400 max-w-xl mx-auto font-sans">
            Connect your workspace and ask KAIROS your first question. The memory builds itself.
          </p>
          <Magnetic strength={0.3} className="mt-10">
            <button
              onClick={enter}
              className="px-9 py-4 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 transition-all text-white shadow-[0_0_36px_rgba(139,92,246,0.5)] hover:-translate-y-0.5"
            >
              {user ? "Open Dashboard →" : "Enter KAIROS →"}
            </button>
          </Magnetic>
        </Reveal>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-violet-950/40 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-zinc-500 font-mono">
          <div className="flex items-center">
            <KairosLogo size={22} showText className="text-zinc-300" />
          </div>
          <div className="flex items-center gap-2 text-zinc-500">
            <span>In collaboration with</span>
            <AMDLogo className="h-3.5 text-zinc-300" />
            <span className="text-zinc-700">×</span>
            <GemmaLogo className="text-base" />
          </div>
          <p>Built by Antigravity · MIT License · &quot;Every company forgets why. KAIROS never does.&quot;</p>
        </div>
      </footer>
    </main>
  );
}
