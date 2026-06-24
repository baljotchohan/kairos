"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("KAIROS fatal error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          height: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#171717",
          color: "#ececec",
          fontFamily:
            "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: 360,
            width: "100%",
            borderRadius: 16,
            border: "1px solid #2c2c2e",
            background: "#212121",
            padding: 24,
            textAlign: "center",
          }}
        >
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>
            KAIROS could not start
          </h2>
          <p style={{ fontSize: 12, color: "#b4b4b4", margin: "0 0 16px" }}>
            A fatal error occurred while loading the application.
          </p>
          <button
            onClick={reset}
            style={{
              width: "100%",
              padding: "10px 16px",
              background: "#7c3aed",
              color: "#fff",
              border: "none",
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
