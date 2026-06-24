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
    <html lang="en" className="dark h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <meta name="theme-color" content="#080808" />
      </head>
      <body className="h-full bg-[#080808] text-[#f5f5f5] font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
