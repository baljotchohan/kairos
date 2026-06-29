"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { auth } from "@/lib/firebase";
import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";

function OAuthLoginContent() {
  const searchParams = useSearchParams();
  const session = searchParams.get("session");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState("");

  const handleSignIn = async () => {
    if (!session) return;
    setStatus("loading");
    setError("");
    try {
      if (!auth) throw new Error("Firebase not configured on this deployment.");

      const result = await signInWithPopup(auth, new GoogleAuthProvider());
      const idToken = await result.user.getIdToken();

      const resp = await fetch("/api/oauth/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ firebase_token: idToken, session }),
      });

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

  if (!session) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={{ ...styles.dot, background: "#ef4444" }} />
          <p style={styles.title}>Invalid Request</p>
          <p style={styles.sub}>Missing OAuth session. Please try adding the connector again.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <svg width="40" height="40" viewBox="0 0 100 100" fill="none" style={{ marginBottom: 16 }}>
          <rect width="100" height="100" rx="12" fill="#171717" />
          <g stroke="#a855f7" strokeWidth="4" strokeLinecap="round">
            <line x1="28" y1="18" x2="28" y2="50" /><line x1="28" y1="50" x2="28" y2="82" />
            <line x1="28" y1="50" x2="48" y2="50" /><line x1="48" y1="50" x2="63" y2="35" />
            <line x1="63" y1="35" x2="78" y2="18" /><line x1="48" y1="50" x2="63" y2="65" />
            <line x1="63" y1="65" x2="78" y2="82" />
          </g>
          <circle cx="28" cy="50" r="5" fill="#a855f7" />
          <circle cx="48" cy="50" r="5" fill="#a855f7" />
        </svg>

        <p style={styles.title}>Connect KAIROS to Claude</p>
        <p style={styles.sub}>Sign in with the Google account you use for KAIROS to authorize Claude to access your organizational memory.</p>

        {status === "success" && (
          <p style={{ color: "#22c55e", fontSize: 14, marginBottom: 12 }}>
            Connected! Redirecting back to Claude...
          </p>
        )}

        {status === "error" && (
          <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 12, wordBreak: "break-word" }}>
            {error}
          </p>
        )}

        {status !== "success" && (
          <button onClick={handleSignIn} disabled={status === "loading"} style={styles.button}>
            {status === "loading" ? "Signing in..." : "Sign in with Google"}
          </button>
        )}

        <p style={styles.hint}>
          This grants Claude read/write access to your KAIROS memory.<br />
          Your data is scoped only to your account.
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    background: "#0b0b0c",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "monospace",
  },
  card: {
    background: "#111113",
    border: "1px solid #27272a",
    borderRadius: 16,
    padding: "40px 48px",
    textAlign: "center",
    maxWidth: 380,
    width: "90%",
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
    marginBottom: 12,
  },
  title: {
    color: "#e4e4e7",
    fontSize: 18,
    fontWeight: 700,
    margin: "0 0 8px 0",
  },
  sub: {
    color: "#71717a",
    fontSize: 13,
    margin: "0 0 24px 0",
    lineHeight: 1.6,
  },
  button: {
    background: "#7c3aed",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "12px 28px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    width: "100%",
    marginBottom: 16,
  },
  hint: {
    color: "#52525b",
    fontSize: 11,
    lineHeight: 1.6,
    margin: 0,
  },
};

export default function OAuthLoginPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", background: "#0b0b0c", display: "flex", alignItems: "center", justifyContent: "center", color: "#71717a", fontFamily: "monospace" }}>
        Loading...
      </div>
    }>
      <OAuthLoginContent />
    </Suspense>
  );
}
