"use client";

import { useEffect, useRef, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { auth } from "@/lib/firebase";
import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";
import KairosLogo from "@/components/KairosLogo";

/* ── Full-page node constellation background ─────────────────────────────── */
function Constellation() {
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
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(90, Math.floor((w * h) / 13000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.2,
        vy: (Math.random() - 0.5) * 0.2,
        r: Math.random() * 1.8 + 1.0,
        pulse: Math.random() * Math.PI * 2,
      }));
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        n.pulse += 0.016;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;
      }
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 150) {
            const op = (1 - d / 150) * 0.5;
            ctx.strokeStyle = `rgba(139,92,246,${op})`;
            ctx.lineWidth = 0.75;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        const dm = Math.hypot(n.x - mouse.x, n.y - mouse.y);
        const near = dm < 150;
        const radius = n.r + Math.sin(n.pulse) * 0.35 + (near ? 1.2 : 0);
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = near ? "rgba(196,181,253,0.95)" : "rgba(167,139,250,0.65)";
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };

    resize();
    draw();
    if (reduce) cancelAnimationFrame(raf);

    const onMouse = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
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
      className="fixed inset-0 w-full h-full pointer-events-none"
      style={{
        maskImage: "radial-gradient(ellipse at 50% 45%, transparent 0%, transparent 18%, black 55%, black 100%)",
        WebkitMaskImage: "radial-gradient(ellipse at 50% 45%, transparent 0%, transparent 18%, black 55%, black 100%)",
      }}
    />
  );
}

function OAuthLoginContent() {
  const searchParams = useSearchParams();
  // Backend flow: /oauth/authorize stores req_id in SQLite → redirects here
  const req_id = searchParams.get("req_id");
  // Legacy Vercel JWT flow (fallback, rarely used)
  const session = searchParams.get("session");
  // Which app is asking for access — shown so approval is an informed choice,
  // not a blind click. Falls back to a generic label if the client never
  // registered a name (see api/routes/mcp_oauth.py's oauth_register).
  const clientName = searchParams.get("client_name");
  // The ACTUAL host this grant will redirect to with an access code. client_name
  // is attacker-controllable (dynamic client registration is unauthenticated), so
  // a phishing client can call itself "Claude Desktop" while redirecting the code
  // to its own domain. redirect_host can't be spoofed the same way — always show it.
  const redirectHost = searchParams.get("redirect_host");

  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState("");

  const handleSignIn = async () => {
    setStatus("loading");
    setError("");
    try {
      if (!auth) throw new Error("Firebase not configured on this deployment.");

      const result = await signInWithPopup(auth, new GoogleAuthProvider());
      const idToken = await result.user.getIdToken();

      let resp: Response;
      if (req_id) {
        // Backend flow: POST to /api/mcp/oauth/complete → proxied to backend via afterFiles
        resp = await fetch("/api/mcp/oauth/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ firebase_token: idToken, req_id }),
        });
      } else if (session) {
        // Vercel JWT flow (legacy)
        resp = await fetch("/api/oauth/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ firebase_token: idToken, session }),
        });
      } else {
        throw new Error("Missing OAuth session. Please try adding the connector again.");
      }

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error_description || err.error || "Authorization failed");
      }

      const data = await resp.json();
      setStatus("success");

      const redirectUrl = new URL(data.redirect_uri);
      redirectUrl.searchParams.set("code", data.code);
      if (data.state) redirectUrl.searchParams.set("state", data.state);
      window.location.href = redirectUrl.toString();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed. Please try again.");
      setStatus("error");
    }
  };

  if (!req_id && !session) {
    return (
      <Shell>
        <div className="w-1.5 h-1.5 rounded-full bg-rose-500 mx-auto mb-4" />
        <p className="text-lg font-bold text-white mb-2">Invalid Request</p>
        <p className="text-sm text-zinc-400 leading-relaxed">
          Missing OAuth session. Please try adding the connector again.
        </p>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mx-auto mb-6 flex items-center justify-center">
        <KairosLogo size={52} />
      </div>

      <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-5 rounded-full border border-violet-500/30 bg-violet-500/5 text-[11px] font-mono tracking-wide text-violet-300">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
        Secure MCP Connection
      </div>

      <h1 className="text-2xl font-bold tracking-tight text-white mb-3">
        Connect Your AI to KAIROS
      </h1>

      {clientName && (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-4 rounded-full border border-white/10 bg-white/5 text-[12px] font-semibold text-zinc-200">
          <span className="text-violet-400">{clientName}</span> is requesting access
        </div>
      )}

      <p className="text-sm text-zinc-400 leading-relaxed mb-8 max-w-[320px] mx-auto">
        {clientName ? (
          <>
            Sign in with the Google account you use for KAIROS to grant <span className="text-zinc-300 font-medium">{clientName}</span> secure,
            scoped access to your organizational memory.
          </>
        ) : (
          <>
            Sign in with the Google account you use for KAIROS to grant this assistant secure,
            scoped access to your organizational memory.
          </>
        )}
      </p>

      {redirectHost && (
        <div className="mb-6 px-3 py-2.5 rounded-lg border border-amber-500/25 bg-amber-500/[0.06] text-left">
          <p className="text-[10px] font-mono uppercase tracking-wide text-amber-400/90 mb-1">
            Access will be sent to
          </p>
          <p className="text-[13px] font-semibold text-amber-100 break-all">{redirectHost}</p>
          <p className="text-[11px] text-zinc-500 mt-1 leading-relaxed">
            Only continue if you recognize this as the app you're connecting.
          </p>
        </div>
      )}

      {status === "success" && (
        <p className="text-sm text-emerald-400 font-medium mb-4">
          Connected — redirecting you back...
        </p>
      )}

      {status === "error" && (
        <p className="text-[13px] text-rose-400 mb-4 leading-relaxed break-words">
          {error}
        </p>
      )}

      {status !== "success" && (
        <button
          onClick={handleSignIn}
          disabled={status === "loading"}
          className="w-full px-7 py-3.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all text-white shadow-[0_0_30px_-6px_rgba(139,92,246,0.55)] hover:shadow-[0_0_44px_-6px_rgba(139,92,246,0.75)] hover:-translate-y-0.5 flex items-center justify-center gap-3 mb-6"
        >
          {status === "loading" ? (
            "Signing in..."
          ) : (
            <>
              <svg className="w-4 h-4 shrink-0 rounded-full bg-white p-0.5" viewBox="0 0 48 48">
                <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
                <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
                <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
                <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
              </svg>
              Sign in with Google
            </>
          )}
        </button>
      )}

      <p className="text-[11px] text-zinc-500 leading-relaxed">
        This grants your AI assistant read/write access to your KAIROS memory.
        <br />
        Your data stays scoped only to your account.
      </p>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative min-h-screen w-full bg-[#080808] text-[#ededed] overflow-hidden flex items-center justify-center px-6 font-sans">
      {/* Subtle film-grain texture, matching the landing page */}
      <div
        className="fixed inset-0 z-[1] pointer-events-none opacity-[0.035] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
      <Constellation />

      {/* Ambient glows, same treatment as the landing page hero */}
      <div className="absolute top-1/4 left-1/4 w-[36rem] h-[36rem] rounded-full bg-violet-700/20 blur-[130px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[32rem] h-[32rem] rounded-full bg-fuchsia-700/12 blur-[140px] pointer-events-none" />

      <div className="relative z-10 w-full max-w-[420px] rounded-2xl border border-violet-500/20 bg-[#0a0a0c]/90 backdrop-blur-xl shadow-[0_30px_80px_-30px_rgba(139,92,246,0.5)] px-8 py-10 sm:px-10 sm:py-12 text-center">
        {children}
      </div>

      <a
        href="/"
        className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 text-[10px] font-mono tracking-wider uppercase text-zinc-600 hover:text-zinc-400 transition-colors"
      >
        KAIROS — Company Organizational Memory OS
      </a>
    </main>
  );
}

export default function OAuthLoginPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen w-full bg-[#080808] flex items-center justify-center">
          <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
        </main>
      }
    >
      <OAuthLoginContent />
    </Suspense>
  );
}
