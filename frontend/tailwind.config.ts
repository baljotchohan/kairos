import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-hover": "rgb(var(--surface-hover) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        "border-focus": "rgb(var(--border-focus) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "text-primary": "rgb(var(--text-primary) / <alpha-value>)",
        "text-muted": "rgb(var(--text-muted) / <alpha-value>)",
        "graph-node-bg": "rgb(var(--graph-node-bg) / <alpha-value>)",
        "graph-node-border": "rgb(var(--graph-node-border) / <alpha-value>)",
        kairos: {
          bg: "#080808",
          surface: "#111111",
          border: "#1e1e1e",
          accent: "#7c3aed",
          "accent-light": "#8b5cf6",
          "text-primary": "#f5f5f5",
          "text-muted": "#6b7280",
          green: "#10b981",
          red: "#ef4444",
        },
        source: {
          slack: "#4a154b",
          email: "#ea4335",
          drive: "#4285f4",
          jira: "#0052cc",
          meeting: "#ff6b35",
        },
      },
      fontFamily: {
        // Apple system-font stack: -apple-system / BlinkMacSystemFont resolve to
        // the real San Francisco (SF Pro) on Mac/iOS Safari & Chrome automatically —
        // SF Pro's font files aren't legally distributable on a public website
        // (Apple licenses them for apps on Apple platforms only), so this system-UI
        // approach is how sites legitimately get the genuine Apple look. Named
        // fallbacks cover the rare case where SF Pro Display/Text is locally
        // installed but the browser doesn't map -apple-system correctly.
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display", "SF Pro Text", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        serif: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display", "SF Pro Text", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "blink": "blink 1s step-end infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "shimmer": "shimmer 1.5s infinite",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
