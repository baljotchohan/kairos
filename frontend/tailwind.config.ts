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
        // Site-wide serif — headings and body copy both read in Newsreader now
        // (a Google Fonts editorial serif with an optical-size axis, so it stays
        // sharp at large headline sizes and small dense UI text alike). sans and
        // serif intentionally point at the same stack so existing font-sans
        // usage picks up the change too; mono is untouched for code/data/labels.
        sans: ["Newsreader", "Iowan Old Style", "Palatino Linotype", "Georgia", "serif"],
        serif: ["Newsreader", "Iowan Old Style", "Palatino Linotype", "Georgia", "serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
        display: ["Newsreader", "Iowan Old Style", "Palatino Linotype", "Georgia", "serif"],
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
