import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KAIROS — Company Organizational Memory OS",
  description:
    "Every company forgets why it made its decisions. KAIROS never does. AI-powered organizational memory that connects Slack, email, Drive, Jira, and Zoom to extract and surface every decision and its full context.",
  keywords: [
    "organizational memory",
    "decision intelligence",
    "knowledge management",
    "AI",
    "enterprise",
  ],
  authors: [{ name: "Antigravity" }],
  icons: {
    icon: "/icon.svg",
    apple: "/apple-icon.svg",
  },
  manifest: "/manifest.json",
  openGraph: {
    title: "KAIROS — Company Organizational Memory OS",
    description:
      "Every company forgets why it made its decisions. KAIROS never does.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full bg-[#080808]">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <meta name="theme-color" content="#171717" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="KAIROS" />
      </head>
      <body className="h-full bg-[#080808] text-[#f5f5f5] font-serif antialiased">
        {children}
      </body>
    </html>
  );
}
