"use client";

import React, { useState, useEffect, useRef } from "react";
import { useKairosChat, Source, KairosStats } from "@/hooks/useKairosChat";
import { useAuth } from "@/hooks/useAuth";
import ConnectionStatus from "@/components/ConnectionStatus";
import SourcePanel from "@/components/SourcePanel";
import StreamingText, { ThinkingIndicator } from "@/components/StreamingText";
import DecisionGraph, { GraphNode } from "@/components/DecisionGraph";
import { ChatHistoryPanel } from "@/components/ChatHistoryPanel";
import IntegrationGrid from "@/components/IntegrationGrid";

type Tab = "chat" | "dashboard" | "decisions" | "integrations" | "agents";

// Local simulation data for demo cases
const SIMULATED_RESPONSES = [
  {
    keywords: ["vendor", "paying", "$2.3m", "2.3", "contract", "john"],
    question: "Why are we paying this vendor $2.3M/year?",
    answer: "Based on KAIROS organizational memory, the company signed a software licensing vendor agreement in **November 2019** for **$191,666/month** (approximating **$2.3M/year**). \n\nThe contract was executed by **John Smith** (former IT Director, who left the company in **2022**). The contract contained an automatic renewal clause and has auto-renewed **3 times** without manual review because John's corporate accounts were deactivated without auditing recurring SaaS invoices. \n\n**Key Risks Extracted:** Auto-renewal was unchecked in the procurement review, and no budget alert was set.",
    sources: [
      { id: "s1", title: "Slack approval thread #procurement-approvals", date: "2019-11-12", source: "slack", source_url: "#" },
      { id: "s2", title: "Email thread 'Execution Copy: SaaS License Agreement v4'", date: "2019-11-14", source: "email", source_url: "#" },
      { id: "s3", title: "Google Drive: Vendor_Agreement_Final_Signed.pdf", date: "2019-11-15", source: "drive", source_url: "#" }
    ] as Source[],
    graph: [
      { id: "d1", label: "Approve Vendor Contract", type: "decision", info: "Software contract approval for $2.3M/year", icon: "🤝" },
      { id: "p1", label: "John Smith", type: "person", info: "IT Director (Signed contract, left 2022)", icon: "👤" },
      { id: "t1", label: "Nov 2019", type: "date", info: "Execution date with auto-renew", icon: "📅" },
      { id: "sr1", label: "Drive: Agreement PDF", type: "source", info: "Signed document in Workspace", icon: "📄" },
      { id: "o1", label: "Auto-renewed 3x", type: "outcome", info: "Status: Unmanaged payments active", icon: "⚠️" }
    ] as GraphNode[]
  },
  {
    keywords: ["react", "vue", "framework", "frontend", "priya"],
    question: "Why do we use React instead of Vue?",
    answer: "The decision to select **React** over **Vue** was finalized in **Q3 2022** during frontend architecture evaluation. \n\nThe frontend engineering team voted **4 to 2** in favor of React. The primary reasoning was that the **local talent hiring pool was significantly larger** for React developers, projecting a 45% reduction in hiring times. \n\nThe primary advocate for Vue was **Priya Sharma** (Senior Frontend Engineer, still at the company), who raised concerns about bundle size but was outvoted by the team.",
    sources: [
      { id: "s4", title: "Slack poll in #engineering-frontend", date: "2022-08-04", source: "slack", source_url: "#" },
      { id: "s5", title: "Meeting recording: Frontend Framework evaluation sync", date: "2022-08-06", source: "meeting", source_url: "#" },
      { id: "s6", title: "Google Drive: Framework_Evaluation_2022.docx", date: "2022-08-01", source: "drive", source_url: "#" }
    ] as Source[],
    graph: [
      { id: "d2", label: "React Chosen over Vue", type: "decision", info: "Frontend technology selection", icon: "⚛️" },
      { id: "p2", label: "Priya Sharma", type: "person", info: "Senior Frontend Engineer (Vue advocate)", icon: "👤" },
      { id: "t2", label: "Aug 2022", type: "date", info: "Decided in Q3 team sync", icon: "📅" },
      { id: "sr2", label: "Slack #frontend", type: "source", info: "Vote results (4-2) and polling thread", icon: "💬" },
      { id: "o2", label: "Reduced Time-to-Hire", type: "outcome", info: "Outcome: Successful scaling of web team", icon: "✅" }
    ] as GraphNode[]
  },
  {
    keywords: ["mobile", "app", "phoenix", "failed", "board", "tried"],
    question: "Has anyone tried building a mobile app before?",
    answer: "Yes, a mobile application (codenamed **Project Phoenix**) was attempted in **2020-2021**. \n\nThe project was terminated after 6 months of development by the Board of Directors in **March 2021**. The initiative resulted in a write-down of **₹40 Lakhs (~$50,000 USD)**. \n\n**Primary Root Cause:** The team attempted to build in React Native with zero prior mobile development experience. The lack of senior mobile expertise led to performance blockades and deployment failures, causing the board to pull the budget.",
    sources: [
      { id: "s7", title: "Jira Epic MOB-100: Phoenix Mobile Client", date: "2020-10-15", source: "jira", source_url: "#" },
      { id: "s8", title: "Meeting: Board Minutes March 2021", date: "2021-03-10", source: "meeting", source_url: "#" },
      { id: "s9", title: "Drive: Project_Phoenix_Retrospective.pdf", date: "2021-03-15", source: "drive", source_url: "#" }
    ] as Source[],
    graph: [
      { id: "d3", label: "Terminate Project Phoenix", type: "decision", info: "Decision to stop mobile app development", icon: "📱" },
      { id: "p3", label: "Board of Directors", type: "person", info: "Cancelled project during quarterly review", icon: "👥" },
      { id: "t3", label: "March 2021", type: "date", info: "Project cancelled", icon: "📅" },
      { id: "sr3", label: "Jira MOB-100", type: "source", info: "Epic details and code repository checkins", icon: "🔧" },
      { id: "o3", label: "₹40L Write-off", type: "outcome", info: "Resulted in write-down & redirect to web app", icon: "❌" }
    ] as GraphNode[]
  }
];

export default function Home() {
  const {
    user,
    token,
    loading: authLoading,
    loginWithGoogle,
    loginAnonymously,
    logout,
    isSimulation,
  } = useAuth();

  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isGraphOpen, setIsGraphOpen] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const {
    messages,
    isConnected,
    isStreaming,
    stats,
    ingestProgress,
    sessions,
    userProfile,
    activeSessionId,
    sendQuestion,
    clearMessages,
    loadSession,
    deleteSession,
    resetProfile
  } = useKairosChat(token);

  const [inputVal, setInputVal] = useState("");
  const chatBottomRef = useRef<HTMLDivElement>(null);
  
  // Simulation coordinate states
  const [currentGraphNodes, setCurrentGraphNodes] = useState<GraphNode[]>([]);
  const [currentGraphTitle, setCurrentGraphTitle] = useState("");
  
  // Custom states for simulated interface
  const [simulatedMessages, setSimulatedMessages] = useState<any[]>([]);
  const [simulatedStreaming, setSimulatedStreaming] = useState(false);
  const [simulatedStats, setSimulatedStats] = useState<KairosStats>({
    total_decisions: 184,
    total_relations: 1248,
    connected_components: 5,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSourceFilter, setSelectedSourceFilter] = useState("all");

  const [syncStatus, setSyncStatus] = useState<Record<string, string>>({
    slack: "synced",
    gmail: "synced",
    drive: "synced",
    jira: "synced",
    zoom: "synced",
  });

  const [slackToken, setSlackToken] = useState("xoxb-8241793264-9182371239-••••••••");
  const [googleClient, setGoogleClient] = useState("9182371982-client.apps.googleusercontent.com");
  const [jiraUrl, setJiraUrl] = useState("https://company.atlassian.net");
  const [zoomKey, setZoomKey] = useState("z_api_key_8123981273");

  // System Sync logs console simulation
  const [logs, setLogs] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem("kairos-theme") as "dark" | "light" | null;
    const currentTheme = savedTheme || "dark";
    setTheme(currentTheme);
    document.documentElement.setAttribute("data-theme", currentTheme);
    document.documentElement.className = currentTheme;
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("kairos-theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    document.documentElement.className = nextTheme;
  };

  // Seed default graph on mount
  useEffect(() => {
    setCurrentGraphNodes(SIMULATED_RESPONSES[0].graph);
    setCurrentGraphTitle(SIMULATED_RESPONSES[0].question);
  }, []);

  // Sync log simulation
  useEffect(() => {
    const logPool = [
      "INFO: [slack] Polling Workspace channels...",
      "INFO: [slack] Found 1 new decision thread in #engineering-core",
      "SUCCESS: [slack] Ingested decision: Standardize analytical schemas to Parquet format",
      "INFO: [gmail] Fetching unread approvals thread for user 'john.smith@company.com'",
      "INFO: [drive] Indexing spec changes in: architecture_v2_evaluation.docx",
      "SUCCESS: [drive] Mapped 3 relations (People: Priya, Technology: React, Date: Aug 2022)",
      "INFO: [jira] Scanning sprint epics for resolution status changes",
      "INFO: [zoom] Running Whisper-large-v3 transcription on: Q4_Planning_Record.mp4",
      "SUCCESS: [zoom] Audio transcription completed (length: 42m 14s). Extracted 2 decisions.",
      "INFO: [chromadb] Persisting vector embeddings to ./chroma_db",
      "SUCCESS: [memory] SQLite database synchronized (relations updated)."
    ];

    setLogs([
      `[${new Date().toLocaleTimeString()}] SYSTEM: Ingestion engine initialized.`,
      `[${new Date().toLocaleTimeString()}] INFO: chromaDB persistence connected.`,
      `[${new Date().toLocaleTimeString()}] INFO: slack_connector OAuth active.`
    ]);

    const interval = setInterval(() => {
      const randomMsg = logPool[Math.floor(Math.random() * logPool.length)];
      const timestamp = new Date().toLocaleTimeString();
      setLogs((prev) => [...prev.slice(-30), `[${timestamp}] ${randomMsg}`]);
    }, 9000);

    return () => clearInterval(interval);
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Auto scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, simulatedMessages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    if (isConnected) {
      sendQuestion(inputVal);
      setInputVal("");
    } else {
      const userText = inputVal.trim();
      setInputVal("");
      setSimulatedStreaming(true);

      const newMsgList = [...simulatedMessages, { id: Math.random().toString(), role: "user", content: userText, sources: [] }];
      setSimulatedMessages(newMsgList);

      const textLower = userText.toLowerCase();
      const match = SIMULATED_RESPONSES.find((resp) =>
        resp.keywords.some((kw) => textLower.includes(kw))
      );

      setTimeout(() => {
        const timestamp = new Date().toLocaleTimeString();
        if (match) {
          setSimulatedMessages((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              role: "assistant",
              content: match.answer,
              sources: match.sources,
            },
          ]);
          setCurrentGraphNodes(match.graph);
          setCurrentGraphTitle(match.question);
          setSimulatedStats((prev) => ({
            ...prev,
            total_decisions: prev.total_decisions + 1,
            total_relations: prev.total_relations + 4,
          }));
          setLogs((prev) => [
            ...prev,
            `[${timestamp}] INFO: Query matches decision index for: "${userText.slice(0, 20)}..."`,
            `[${timestamp}] SUCCESS: Extracted decision graph with ${match.graph.length} nodes.`
          ]);
        } else {
          setSimulatedMessages((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              role: "assistant",
              content: `I scanned Slack channels, Drive specs, and Gmail threads for **"${userText}"**, but did not find any recorded historical decisions directly mapping to that query. \n\n*Try asking one of these demo questions:* \n* *"Why are we paying this vendor $2.3M/year?"*\n* *"Why do we use React instead of Vue?"*\n* *"Has anyone tried building a mobile app before?"*`,
              sources: [],
            },
          ]);
          setLogs((prev) => [
            ...prev,
            `[${timestamp}] WARN: Vector search yielded 0 matches for: "${userText.slice(0, 25)}..."`
          ]);
        }
        setSimulatedStreaming(false);
      }, 1000);
    }
  };

  const handleNewChat = () => {
    if (isConnected) {
      clearMessages();
    } else {
      setSimulatedMessages([]);
    }
  };

  const triggerSync = (platform: string) => {
    setSyncStatus((prev) => ({ ...prev, [platform]: "syncing" }));
    const startTimestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${startTimestamp}] INFO: Triggering sync on platform connector: [${platform}]`]);
    
    setTimeout(() => {
      setSyncStatus((prev) => ({ ...prev, [platform]: "synced" }));
      const doneTimestamp = new Date().toLocaleTimeString();
      const count = Math.floor(Math.random() * 3) + 1;
      setLogs((prev) => [
        ...prev,
        `[${doneTimestamp}] SUCCESS: Synchronized platform connector: [${platform}]`,
        `[${doneTimestamp}] INFO: Scraped and extracted ${count} decision nodes.`
      ]);

      if (!isConnected) {
        setSimulatedStats((prev) => ({
          ...prev,
          total_decisions: prev.total_decisions + count,
          total_relations: prev.total_relations + count * 3,
        }));
      }
    }, 1500);
  };

  const exportDecisionIndex = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(explorerDecisions, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "kairos_decision_records.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${timestamp}] SYSTEM: Exported decision index JSON payload.`]);
  };

  const getSourceIcon = (source: string) => {
    switch (source.toLowerCase()) {
      case "slack": return "#";
      case "email": return "@";
      case "drive": return "D";
      case "jira": return "J";
      case "meeting": return "M";
      default: return "?";
    }
  };

  const explorerDecisions = [
    { id: "dec-1", title: "Approve SaaS Vendor Contract Renewal ($2.3M/year)", date: "2019-11-15", owner: "John Smith", source: "drive", context: "Software contract approval for $2.3M/year with unchecked 3-year auto-renewals. Signed by former IT Director." },
    { id: "dec-2", title: "Choose React over Vue for Core Web Clients", date: "2022-08-06", owner: "Frontend Dev Team", source: "slack", context: "Selected React (4-2 vote) over Vue. Priya Sharma advocated Vue. Decided for larger hiring pool." },
    { id: "dec-3", title: "Terminate Project Phoenix (Mobile Client Development)", date: "2021-03-10", owner: "Board of Directors", source: "meeting", context: "Discontinued React Native client. Wrote down ₹40 Lakhs due to lack of team mobile development experience." },
    { id: "dec-4", title: "Migrate analytical pipelines from Redshift to BigQuery", date: "2024-02-12", owner: "Alex Rivera", source: "jira", context: "Data warehousing consolidation. BigQuery chosen due to native integration with streaming pipelines." },
    { id: "dec-5", title: "Implement SSO via Okta across all corporate platforms", date: "2023-05-18", owner: "Security Ops Team", source: "email", context: "Mandated SSO compliance before internal security audit. Approved by CEO." }
  ];

  const filteredDecisions = explorerDecisions.filter((d) => {
    const matchesSearch = d.title.toLowerCase().includes(searchQuery.toLowerCase()) || d.owner.toLowerCase().includes(searchQuery.toLowerCase()) || d.context.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = selectedSourceFilter === "all" || d.source.toLowerCase() === selectedSourceFilter;
    return matchesSearch && matchesSource;
  });

  const displayStats = isConnected && stats ? stats : simulatedStats;
  const chatHistory = isConnected ? messages : simulatedMessages;
  const isChatStreaming = isConnected ? isStreaming : simulatedStreaming;
  const activeSources = chatHistory.length > 0 ? (chatHistory[chatHistory.length - 1]?.sources || []) : [];

  // Auth Loading state rendering
  if (authLoading) {
    return (
      <div className="flex h-full w-full bg-[#0b0b0c] text-[#e4e4e7] items-center justify-center font-mono text-xs">
        <div className="flex flex-col items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
          Authenticating Memory OS...
        </div>
      </div>
    );
  }

  // Auth Unauthenticated Screen rendering
  if (!user) {
    return (
      <div className="flex h-full w-full bg-[var(--bg)] text-[var(--text-primary)] items-center justify-center p-6 relative">
        {/* Toggle Theme button top right */}
        <div className="absolute top-4 right-4">
          <button
            onClick={toggleTheme}
            className="p-2 hover:bg-[var(--surface-hover)] border border-[var(--border)] rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all theme-transition animate-[fadeIn_0.3s_ease-out]"
            title="Toggle theme"
          >
            {theme === "dark" ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </div>

        <div className="w-full max-w-sm p-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] text-center shadow-lg flex flex-col gap-6 theme-transition animate-[fadeIn_0.2s_ease-out]">
          {/* Logo */}
          <div className="flex flex-col items-center gap-2 mt-4">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
              <span className="font-bold text-white text-lg">K</span>
            </div>
            <h1 className="font-bold text-lg tracking-wider text-[var(--text-primary)] uppercase">KAIROS</h1>
            <p className="text-[9px] text-[var(--text-muted)] font-mono tracking-widest font-semibold uppercase">Memory OS</p>
          </div>

          <div className="space-y-1.5">
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Every company forgets why it made its decisions. KAIROS never does. Connect to your workspace memory.
            </p>
          </div>

          {/* Login Buttons */}
          <div className="flex flex-col gap-2 mt-2 mb-4">
            <button
              onClick={loginWithGoogle}
              className="w-full py-2.5 px-4 bg-transparent border border-[var(--border)] hover:bg-[var(--surface-hover)] rounded-xl text-xs font-semibold text-[var(--text-primary)] flex items-center justify-center gap-3.5 transition-all theme-transition"
            >
              {/* Google Icon */}
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path fill="#ea4335" d="M12.24 10.285V14.4h6.887c-.648 2.41-2.519 4.114-5.136 4.114A5.59 5.59 0 018.4 12.925a5.59 5.59 0 015.591-5.59c2.316 0 4.29 1.258 5.347 3.12l3.418-2.617A10.957 10.957 0 0013.991 3C8.196 3 3.5 7.696 3.5 13.49s4.696 10.49 10.491 10.49c6.126 0 10.285-4.305 10.285-10.49 0-.616-.056-1.22-.168-1.785H12.24z" />
              </svg>
              Sign In with Google
            </button>
            <button
              onClick={loginAnonymously}
              className="w-full py-2.5 px-4 bg-[#1e1e20] hover:bg-zinc-800 border border-[#27272a] rounded-xl text-xs font-semibold text-white flex items-center justify-center gap-2 transition-all"
            >
              <svg className="w-4 h-4 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Continue as Guest
            </button>
          </div>

          <div className="text-[9px] text-[var(--text-muted)] font-mono uppercase tracking-wider">
            {isSimulation ? "Running in client-simulation mode" : "Secured by Firebase Auth"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full bg-[var(--bg)] text-[var(--text-primary)] overflow-hidden theme-transition animate-[fadeIn_0.2s_ease-out]">
      
      {/* 1. LEFT SIDEBAR */}
      <div
        className={`bg-[var(--surface)] border-r border-[var(--border)] flex flex-col justify-between shrink-0 transition-all duration-300 theme-transition ${
          isSidebarOpen ? "w-60" : "w-0 -translate-x-full overflow-hidden"
        }`}
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo & Close sidebar */}
          <div className="p-4 border-b border-[var(--border)] flex items-center justify-between theme-transition">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-indigo-600 flex items-center justify-center shadow">
                <span className="font-bold text-white text-[10px]">K</span>
              </div>
              <span className="font-bold text-xs tracking-wider uppercase text-[var(--text-primary)] theme-transition">KAIROS</span>
            </div>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="p-1 hover:bg-[var(--surface-hover)] rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all theme-transition"
              title="Close sidebar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              </svg>
            </button>
          </div>

          {/* New Chat */}
          <div className="p-3 border-b border-[var(--border)] theme-transition">
            <button
              onClick={handleNewChat}
              className="w-full py-1.5 px-3 border border-[var(--border)] hover:border-[var(--border-focus)] bg-transparent hover:bg-[var(--surface-hover)] rounded-lg text-xs font-semibold text-[var(--text-primary)] flex items-center justify-center gap-2 transition-all theme-transition"
            >
              <svg className="w-3.5 h-3.5 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              New Chat
            </button>
          </div>

          {/* Nav Links */}
          <div className="px-2 py-1.5 flex flex-col gap-0.5 border-b border-[var(--border)] theme-transition">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === "chat" ? "bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]/60"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Chat Console
            </button>
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === "dashboard" ? "bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]/60"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
              </svg>
              Metrics Overview
            </button>
            <button
              onClick={() => setActiveTab("decisions")}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === "decisions" ? "bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]/60"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Decision Index
            </button>
            <button
              onClick={() => setActiveTab("integrations")}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === "integrations" ? "bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]/60"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Connectors
            </button>
            <button
              onClick={() => setActiveTab("agents")}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === "agents" ? "bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]/60"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
              AI Agents
            </button>
          </div>

          {/* Learned User Profile Context */}
          {userProfile && (userProfile.department || userProfile.role_context || (userProfile.frequent_topics && userProfile.frequent_topics.length > 0)) && (
            <div className="mx-3 mt-4 p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-[11px] theme-transition">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[9px] font-mono text-indigo-400 font-bold uppercase tracking-wider">
                  🧠 Learned Profile
                </span>
                <button
                  onClick={resetProfile}
                  className="text-[9px] font-mono text-rose-400 hover:underline"
                  title="Reset profile"
                >
                  Reset
                </button>
              </div>
              {userProfile.department && (
                <div className="flex justify-between py-0.5 border-b border-indigo-500/5">
                  <span className="text-zinc-500">Dept:</span>
                  <span className="text-[var(--text-primary)] font-semibold">{userProfile.department}</span>
                </div>
              )}
              {userProfile.role_context && (
                <p className="text-zinc-400 mt-1 italic leading-snug">
                  "{userProfile.role_context}"
                </p>
              )}
              {userProfile.frequent_topics && userProfile.frequent_topics.length > 0 && (
                <div className="mt-1.5">
                  <span className="text-[9px] text-zinc-500 block mb-0.5">Top Topics:</span>
                  <div className="flex flex-wrap gap-1">
                    {userProfile.frequent_topics.map((t: string, idx: number) => (
                      <span key={idx} className="bg-indigo-500/10 text-indigo-300 px-1 rounded-[3px] text-[9px] font-medium">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Historical Logs List */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-1.5">
            <span className="text-[9px] text-[var(--text-muted)] font-mono tracking-wider font-bold">RECENT INQUIRIES</span>
            {SIMULATED_RESPONSES.map((resp, i) => (
              <button
                key={i}
                onClick={() => {
                  setActiveTab("chat");
                  setInputVal(resp.question);
                }}
                className="w-full text-left px-2.5 py-1.5 hover:bg-[var(--surface-hover)] rounded text-[11px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] truncate transition-all theme-transition"
              >
                {resp.question}
              </button>
            ))}
          </div>
        </div>

        {/* Footer: User Profile details + Light/Dark switch + Connection */}
        <div className="p-4 border-t border-[var(--border)] bg-[var(--bg)] flex flex-col gap-3 theme-transition">
          
          {/* User profile details */}
          <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]/40 theme-transition">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-6 h-6 rounded bg-indigo-600/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center shrink-0 font-mono font-bold text-[10px]">
                {user.displayName ? user.displayName.charAt(0) : "G"}
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="text-[11px] font-bold text-[var(--text-primary)] truncate">
                  {user.displayName || "Guest User"}
                </span>
                <span className="text-[9px] text-[var(--text-muted)] truncate">
                  {user.email || "Temporary Access"}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              className="p-1 hover:bg-[var(--surface-hover)] border border-[var(--border)] rounded text-[var(--text-muted)] hover:text-rose-400 transition-all theme-transition shrink-0"
              title="Sign Out"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-[9px] text-[var(--text-muted)] font-mono tracking-wider uppercase font-semibold">THEME</span>
            <button
              onClick={toggleTheme}
              className="p-1 hover:bg-[var(--surface-hover)] border border-[var(--border)] rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all theme-transition"
              title="Toggle theme"
            >
              {theme === "dark" ? (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] text-[var(--text-muted)] font-mono tracking-wider uppercase font-semibold">SYNC ENGINE</span>
            <ConnectionStatus isConnected={isConnected} />
          </div>
        </div>
      </div>

      {/* Sidebar toggle button (closed state) */}
      {!isSidebarOpen && (
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="absolute top-3.5 left-4 z-50 p-1.5 bg-[var(--surface)] border border-[var(--border)] rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all theme-transition"
          title="Open sidebar"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      {/* 2. MAIN CONTAINER */}
      <main className="flex-1 flex flex-col min-w-0 bg-[var(--bg)] relative theme-transition">
        
        {/* Header */}
        <header className="h-12 border-b border-[var(--border)] flex items-center justify-between px-6 shrink-0 bg-[var(--bg)]/90 z-20 theme-transition">
          <div className="flex items-center gap-3">
            {!isSidebarOpen && <div className="w-8" />}
            <h2 className="text-[10px] font-mono tracking-widest text-[var(--text-muted)] uppercase">
              KAIROS // {activeTab}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {activeTab === "chat" && (
              <button
                onClick={() => setIsGraphOpen(!isGraphOpen)}
                className={`px-2.5 py-1 rounded border text-[9px] font-semibold tracking-wider font-mono transition-all theme-transition ${
                  isGraphOpen ? "bg-[var(--surface-hover)] border-[var(--border-focus)] text-[var(--text-primary)]" : "bg-transparent border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isGraphOpen ? "HIDE GRAPH" : "SHOW GRAPH"}
              </button>
            )}
            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-[var(--surface)] border border-[var(--border)] text-[var(--text-muted)] theme-transition">
              DEPLOYED COMPILER: OK
            </span>
          </div>
        </header>

        {/* Tab Router Contents */}
        <div className="flex-1 overflow-y-auto">
          {/* CHAT CONSOLE */}
          {activeTab === "chat" && (
            <div className="h-[calc(100vh-3rem)] flex overflow-hidden">
              
              {/* Chat History Sidebar */}
              {isConnected && (
                <ChatHistoryPanel
                  sessions={sessions}
                  activeSessionId={activeSessionId}
                  onSelectSession={loadSession}
                  onDeleteSession={deleteSession}
                />
              )}

              {/* Left Column: Chat log */}
              <div className="flex-1 flex flex-col h-full bg-[var(--bg)] relative min-w-0 theme-transition">
                
                {/* Message list */}
                <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
                  <div className="max-w-2xl mx-auto space-y-6">
                    
                    {chatHistory.length === 0 && (
                      <div className="flex flex-col items-center justify-center h-full pt-16 text-center max-w-sm mx-auto gap-4">
                        <div className="w-10 h-10 rounded-full bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center text-[var(--text-muted)] theme-transition">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-xs font-bold text-[var(--text-primary)] tracking-wider uppercase mb-1 theme-transition">Organizational memory console</h3>
                          <p className="text-[11px] text-[var(--text-muted)] leading-relaxed theme-transition">
                            Inquire regarding engineering framework tradeoffs, vendor renewals, or project retrospects.
                          </p>
                        </div>
                      </div>
                    )}

                    {chatHistory.map((msg, i) => (
                      <div
                        key={msg.id || i}
                        className={`flex gap-4 items-start ${msg.role === "user" ? "justify-end" : ""}`}
                      >
                        {msg.role === "assistant" && (
                          <div className="w-6 h-6 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 font-bold text-white text-[10px]">
                            K
                          </div>
                        )}

                        <div
                          className={`flex-1 overflow-hidden space-y-2 ${
                            msg.role === "user"
                              ? "max-w-[80%] bg-[var(--surface)] border border-[var(--border)] px-4 py-2.5 rounded-2xl text-xs text-[var(--text-primary)] theme-transition"
                              : "text-[var(--text-primary)] theme-transition"
                          }`}
                        >
                          <StreamingText
                            text={msg.content}
                            isStreaming={msg.isStreaming ?? false}
                            hasWarning={msg.hasWarning}
                            className="text-xs md:text-sm"
                          />

                          {/* Assistant context metadata (Intent & Confidence) */}
                          {msg.role === "assistant" && (
                            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                              {msg.intent && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                  {msg.intent.intent === "search" && "🔍 Search"}
                                  {msg.intent.intent === "follow_up" && "💬 Follow-up"}
                                  {msg.intent.intent === "comparison" && "⚖️ Comparison"}
                                  {msg.intent.intent === "timeline" && "📅 Timeline"}
                                  {msg.intent.intent === "person_lookup" && "👤 Person Lookup"}
                                  {msg.intent.intent === "what_if" && "❓ What-if"}
                                  {msg.intent.intent === "summary" && "📊 Summary"}
                                  {!["search", "follow_up", "comparison", "timeline", "person_lookup", "what_if", "summary"].includes(msg.intent.intent) && `🤖 ${msg.intent.intent}`}
                                </span>
                              )}

                              {msg.confidence !== undefined && (
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] text-zinc-500">Confidence:</span>
                                  <div className="w-16 h-1 bg-slate-800 rounded-full overflow-hidden border border-slate-700/50">
                                    <div
                                      className={`h-full rounded-full transition-all duration-300 ${
                                        msg.confidence > 0.8
                                          ? "bg-emerald-500"
                                          : msg.confidence > 0.5
                                          ? "bg-amber-500"
                                          : "bg-rose-500"
                                      }`}
                                      style={{ width: `${msg.confidence * 100}%` }}
                                    />
                                  </div>
                                  <span className="text-[10px] font-mono text-zinc-400">{(msg.confidence * 100).toFixed(0)}%</span>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Live Thinking Step */}
                          {msg.thinkingStep && (
                            <div className="p-2.5 bg-slate-900/60 border border-slate-800 rounded-xl flex items-center gap-3 animate-pulse text-[11px] text-indigo-400">
                              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping shrink-0" />
                              <span className="truncate"><strong>[{msg.thinkingStep.agent} thinking]:</strong> {msg.thinkingStep.content}</span>
                            </div>
                          )}

                          {/* Agent traces history */}
                          {msg.traces && msg.traces.length > 0 && (
                            <details className="text-[10px] text-zinc-400 bg-zinc-950/40 border border-zinc-800/80 rounded-xl p-2.5 mt-2">
                              <summary className="cursor-pointer font-semibold text-zinc-300 select-none hover:text-zinc-100 transition-colors">
                                👀 View Multi-Agent Traces ({msg.traces.length} steps)
                              </summary>
                              <div className="mt-2.5 space-y-2 font-mono border-l border-zinc-800 pl-2.5 max-h-48 overflow-y-auto">
                                {msg.traces.map((trace: any, idx: number) => (
                                  <div key={idx} className="flex flex-col">
                                    <div className="flex items-center gap-1.5">
                                      <span className={`text-[9px] uppercase font-bold ${
                                        trace.type === "think" ? "text-indigo-400" :
                                        trace.type === "act" ? "text-amber-400" :
                                        trace.type === "observe" ? "text-sky-400" :
                                        trace.type === "reflect" ? "text-purple-400" :
                                        trace.type === "error" ? "text-rose-400" : "text-emerald-400"
                                      }`}>
                                        [{trace.type}]
                                      </span>
                                      {trace.tool_name && (
                                        <span className="text-[9px] text-zinc-500">
                                          ({trace.tool_name})
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-[10px] text-zinc-300 mt-0.5 whitespace-pre-wrap">{trace.content}</p>
                                    {trace.duration_ms > 0 && (
                                      <span className="text-[8px] text-zinc-500">Duration: {trace.duration_ms.toFixed(0)}ms</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}

                          {/* Sources */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap pt-3 border-t border-[var(--border)]/60 theme-transition">
                              {msg.sources.map((src: Source) => (
                                <span
                                  key={src.id}
                                  className="inline-flex items-center gap-1 text-[9px] font-mono bg-[var(--surface)] text-[var(--text-muted)] border border-[var(--border)] px-2 py-0.5 rounded theme-transition"
                                >
                                  <span className="text-[8px] text-indigo-400 font-bold">{getSourceIcon(src.source)}</span>
                                  {(src.title || "").split(":")[0]}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {isChatStreaming && (
                      <div className="flex gap-4 items-start">
                        <div className="w-6 h-6 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 font-bold text-white text-[10px]">
                          K
                        </div>
                        <ThinkingIndicator />
                      </div>
                    )}
                  </div>
                  <div ref={chatBottomRef} />
                </div>

                {/* Processing toast */}
                {ingestProgress && (
                  <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text-primary)] text-xs font-semibold flex items-center gap-2 shadow-2xl z-20 theme-transition">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
                    {ingestProgress}
                  </div>
                )}

                {/* Text area input bar */}
                <form onSubmit={handleSend} className="p-6 shrink-0 bg-gradient-to-t from-[var(--bg)] via-[var(--bg)]/90 to-transparent theme-transition">
                  <div className="max-w-2xl mx-auto relative bg-[var(--surface)] border border-[var(--border)] focus-within:border-[var(--border-focus)] rounded-2xl shadow-lg transition-all p-1.5 theme-transition">
                    <input
                      type="text"
                      value={inputVal}
                      onChange={(e) => setInputVal(e.target.value)}
                      disabled={isChatStreaming}
                      placeholder="Ask KAIROS memory database..."
                      className="w-full bg-transparent px-4 py-2 text-xs md:text-sm text-[var(--text-primary)] placeholder-zinc-500 focus:outline-none disabled:opacity-50 theme-transition"
                    />
                    <div className="flex justify-end pt-1 px-1">
                      <button
                        type="submit"
                        disabled={isChatStreaming || !inputVal.trim()}
                        className="bg-[var(--surface-hover)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--text-primary)] rounded-lg p-1.5 flex items-center justify-center transition-all disabled:opacity-30 theme-transition"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l7-7m0 0l-7 7m-7-7v18" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* Right Column: Obsidian Graph */}
              {isGraphOpen && (
                <div className="w-96 border-l border-[var(--border)] flex flex-col h-full bg-[var(--bg)]/40 shrink-0 theme-transition">
                  <div className="flex-1 relative">
                    <DecisionGraph nodes={currentGraphNodes} decisionTitle={currentGraphTitle} />
                  </div>
                  <div className="h-48">
                    <SourcePanel sources={activeSources} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* DASHBOARD & STATS OVERVIEW */}
          {activeTab === "dashboard" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-[fadeIn_0.2s_ease-out]">
              <div className="border-b border-[var(--border)] pb-4 theme-transition">
                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-1 theme-transition">Active System Ingest Metrics</h3>
                <p className="text-xs text-[var(--text-muted)] theme-transition">Monitor memory storage metrics, API credit mappings, and connector status.</p>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { label: "Decisions Extracted", value: displayStats.total_decisions, tag: "records" },
                  { label: "Graph Relations", value: displayStats.total_relations, tag: "links" },
                  { label: "Connected APIs", value: displayStats.connected_components, tag: "active" },
                  { label: "SQLite Index Size", value: "84.2", tag: "MB" },
                ].map((stat, idx) => (
                  <div key={idx} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]/30 theme-transition">
                    <span className="text-[9px] font-mono text-[var(--text-muted)] uppercase block mb-1 theme-transition">{stat.label}</span>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xl font-bold text-[var(--text-primary)] theme-transition">{stat.value}</span>
                      <span className="text-[9px] font-mono text-[var(--text-muted)] theme-transition">{stat.tag}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Connected APIs */}
              <div className="space-y-3">
                <h4 className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider theme-transition">Ingestion Connectors</h4>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                  {[
                    { key: "slack", name: "Slack", details: "Workspace API" },
                    { key: "gmail", name: "Gmail", details: "OAuth client" },
                    { key: "drive", name: "G Drive", details: "Folder Scraper" },
                    { key: "jira", name: "JIRA Cloud", details: "REST client" },
                    { key: "zoom", name: "Zoom Sync", details: "Whisper API" },
                  ].map((plat) => (
                    <div key={plat.key} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]/20 flex flex-col justify-between h-28 theme-transition">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-[var(--text-muted)] uppercase theme-transition">{plat.key}</span>
                        <span className={`w-1 h-1 rounded-full ${syncStatus[plat.key] === "syncing" ? "bg-amber-500 animate-pulse" : "bg-emerald-500"}`} />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-[var(--text-primary)] block theme-transition">{plat.name}</span>
                        <span className="text-[9px] text-[var(--text-muted)] block theme-transition">{plat.details}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Deployed Polish: CLI sync activity logs console */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider theme-transition">Sync Container CLI Logs</h4>
                  <span className="text-[8px] font-mono bg-zinc-800 text-emerald-400 px-1.5 py-0.5 rounded border border-zinc-700">
                    CONTAINER: RUNNING
                  </span>
                </div>
                <div className="bg-black rounded-lg border border-zinc-800 p-4 h-36 font-mono text-[10px] text-emerald-500 overflow-y-auto shadow-inner flex flex-col gap-1">
                  {logs.map((log, index) => (
                    <div key={index} className="whitespace-pre-wrap leading-relaxed">
                      {log}
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </div>
            </div>
          )}

          {/* DECISION INDEX EXPLORER */}
          {activeTab === "decisions" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-[fadeIn_0.2s_ease-out]">
              <div className="border-b border-[var(--border)] pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 theme-transition">
                <div>
                  <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-1 theme-transition">Decision Records Ingest</h3>
                  <p className="text-xs text-[var(--text-muted)] theme-transition font-medium">Export and browse through historically captured corporate decision points.</p>
                </div>

                <div className="flex gap-2 items-center">
                  <button
                    onClick={exportDecisionIndex}
                    className="px-2.5 py-1 rounded bg-[var(--surface)] border border-[var(--border)] hover:bg-[var(--surface-hover)] text-[10px] font-mono font-bold tracking-wider text-[var(--text-primary)] flex items-center gap-1.5 transition-all theme-transition"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    EXPORT JSON
                  </button>

                  <div className="flex gap-1 overflow-x-auto">
                    {["all", "slack", "email", "drive", "jira", "meeting"].map((src) => (
                      <button
                        key={src}
                        onClick={() => setSelectedSourceFilter(src)}
                        className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border transition-all theme-transition ${
                          selectedSourceFilter === src ? "bg-[var(--surface-hover)] text-[var(--text-primary)] border-[var(--border-focus)]" : "bg-transparent text-[var(--text-muted)] border-[var(--border)] hover:text-[var(--text-primary)]"
                        }`}
                      >
                        {src}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Search */}
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search index database..."
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-lg pl-8 pr-3 py-2 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] placeholder-zinc-500 theme-transition"
                />
                <svg className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>

              {/* List */}
              <div className="flex flex-col gap-3">
                {filteredDecisions.length === 0 ? (
                  <div className="p-8 text-center border border-dashed border-[var(--border)] rounded-xl text-[var(--text-muted)] text-xs theme-transition">
                    No results found matching filters.
                  </div>
                ) : (
                  filteredDecisions.map((dec) => (
                    <div key={dec.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]/20 hover:bg-[var(--surface-hover)]/30 transition-all theme-transition">
                      <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] mb-2 theme-transition">
                        <span className="font-mono uppercase">{dec.source} | {dec.date}</span>
                        <span className="font-mono">{dec.owner}</span>
                      </div>
                      <h4 className="text-xs md:text-sm font-bold text-[var(--text-primary)] mb-1 theme-transition">{dec.title}</h4>
                      <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-3 theme-transition">{dec.context}</p>
                      <button
                        onClick={() => {
                          const match = SIMULATED_RESPONSES.find((r) => r.keywords.some((k) => dec.title.toLowerCase().includes(k)));
                          if (match) {
                            setCurrentGraphNodes(match.graph);
                            setCurrentGraphTitle(match.question);
                            setActiveTab("chat");
                          }
                        }}
                        className="text-[10px] font-mono font-bold text-[var(--accent)] hover:text-indigo-400 transition-colors"
                      >
                        [INSPECT NETWORK GRAPH]
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* INTEGRATIONS — OAuth Connect */}
          {activeTab === "integrations" && (
            <div className="p-8 max-w-2xl mx-auto flex flex-col gap-6 animate-[fadeIn_0.2s_ease-out]">
              <div className="border-b border-[var(--border)] pb-4 theme-transition">
                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-1 theme-transition">
                  Connect Your Apps
                </h3>
                <p className="text-xs text-[var(--text-muted)] theme-transition">
                  One-click OAuth. Authorize once — KAIROS ingests decisions automatically.
                </p>
              </div>

              <IntegrationGrid token={token} />

              {/* How-it-works callout */}
              <div className="p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5 text-[11px] text-[var(--text-muted)] space-y-1.5">
                <p className="text-[10px] font-mono text-indigo-400 font-bold uppercase tracking-wider mb-2">How it works</p>
                {[
                  "Click Connect → OAuth popup opens",
                  "Authorize KAIROS in your account",
                  "Token is saved to your KAIROS profile",
                  "Agents start ingesting decisions automatically",
                ].map((step, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-indigo-500 font-bold">{i + 1}.</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>

              {/* Data permissions callout */}
              <div className="p-4 rounded-xl border border-purple-500/20 bg-purple-500/5 text-[11px] text-[var(--text-muted)] space-y-1.5">
                <p className="text-[10px] font-mono text-purple-400 font-bold uppercase tracking-wider mb-2">Read-only permissions</p>
                {[
                  ["💬 Slack", "Reads messages to find decision threads. Never sends messages."],
                  ["📧 Gmail", "Reads emails for approvals and escalations. Never reads attachments."],
                  ["📄 Drive", "Reads shared docs and specs. Never modifies files."],
                  ["🎯 Jira", "Reads tickets and comments. Never creates or modifies."],
                  ["📹 Zoom", "Accesses meeting transcripts. Never records or controls meetings."],
                ].map(([label, desc]) => (
                  <div key={label} className="flex gap-2">
                    <span className="text-purple-300 font-semibold w-36 shrink-0">{label}</span>
                    <span>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI AGENTS DASHBOARD */}
          {activeTab === "agents" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-[fadeIn_0.2s_ease-out]">
              <div className="border-b border-[var(--border)] pb-4 theme-transition">
                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-1 theme-transition">AI Agents Registry</h3>
                <p className="text-xs text-[var(--text-muted)] theme-transition">Monitor the real-time execution, model allocations, and task metrics of KAIROS parallel agents.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  {
                    name: "intent_agent",
                    label: "Query Intent Classifier",
                    status: isChatStreaming ? "processing" : "idle",
                    description: "Analyzes user query semantics to determine search intent categories (search, comparison, timeline, summary, person, follow-up) and extracts named entities.",
                    model: "Llama 3.3 70B (Groq Cloud)",
                    hardware: "Groq LPU Accelerator",
                    icon: "🔍",
                    metrics: [
                      { label: "Classifications", value: "248" },
                      { label: "Accuracy", value: "99.1%" },
                      { label: "Latency", value: "85ms" }
                    ]
                  },
                  {
                    name: "context_agent",
                    label: "Query Context Resolver",
                    status: isChatStreaming ? "processing" : "idle",
                    description: "Resolves conversational history pronouns/references (e.g. 'it', 'they') and enriches queries with learned user profiles.",
                    model: "Llama 3.3 70B (Groq Cloud)",
                    hardware: "Groq LPU Accelerator",
                    icon: "💬",
                    metrics: [
                      { label: "Resolutions", value: "192" },
                      { label: "Cache Hits", value: "91%" },
                      { label: "Latency", value: "110ms" }
                    ]
                  },
                  {
                    name: "research_agent",
                    label: "Deep Graph Researcher",
                    status: isChatStreaming ? "processing" : "idle",
                    description: "Executes multi-step ReAct reasoning loops. Performs hybrid vector search, structured SQL queries, and traverses decision graphs to answer complex questions.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "🕵️‍♂️",
                    metrics: [
                      { label: "Research Runs", value: "78" },
                      { label: "Graph Hops", value: "4.2 avg" },
                      { label: "Reflections", value: "96.4%" }
                    ]
                  },
                  {
                    name: "slack_agent",
                    label: "Slack Ingestion Agent",
                    status: syncStatus.slack === "syncing" ? "processing" : "idle",
                    description: "Scrapes Slack conversation history, parses threaded topics, and extracts architectural decision nodes.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "💬",
                    metrics: [
                      { label: "Decisions", value: "48" },
                      { label: "Reliability", value: "98.4%" },
                      { label: "Execution Cache", value: "92%" }
                    ]
                  },
                  {
                    name: "email_agent",
                    label: "Email Analysis Agent",
                    status: syncStatus.gmail === "syncing" ? "processing" : "idle",
                    description: "Scrapes Gmail inbox threads for formal approvals, executive sign-offs, and critical client agreements.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "📧",
                    metrics: [
                      { label: "Decisions", value: "31" },
                      { label: "Reliability", value: "96.8%" },
                      { label: "Execution Cache", value: "95%" }
                    ]
                  },
                  {
                    name: "drive_agent",
                    label: "Specs & Docs Agent",
                    status: syncStatus.drive === "syncing" ? "processing" : "idle",
                    description: "Indexes Google Drive specs, design docs, and product requirement sheets to construct timeline traces.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "📄",
                    metrics: [
                      { label: "Decisions", value: "67" },
                      { label: "Reliability", value: "94.1%" },
                      { label: "Execution Cache", value: "88%" }
                    ]
                  },
                  {
                    name: "meeting_agent",
                    label: "Meeting Transcription Agent",
                    status: syncStatus.zoom === "syncing" ? "processing" : "idle",
                    description: "Transcribes Zoom recordings using Whisper and parses transcripts for verbal tech agreements.",
                    model: "Whisper-v3 + Qwen 2.5",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "🎙️",
                    metrics: [
                      { label: "Transcribed", value: "14.5 hrs" },
                      { label: "Reliability", value: "92.5%" },
                      { label: "Execution Cache", value: "N/A" }
                    ]
                  }
                ].map((agent) => (
                  <div key={agent.name} className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface)]/30 flex flex-col justify-between gap-4 theme-transition hover:border-[var(--border-focus)] transition-all">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">{agent.icon}</span>
                          <span className="text-xs font-bold text-[var(--text-primary)] theme-transition">{agent.label}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${agent.status === "processing" ? "bg-amber-500 animate-ping" : "bg-emerald-500"}`} />
                          <span className="text-[9px] font-mono font-bold tracking-wider uppercase text-[var(--text-muted)] theme-transition">
                            {agent.status === "processing" ? "SYNCING" : "IDLE"}
                          </span>
                        </div>
                      </div>
                      <p className="text-[11px] text-[var(--text-muted)] leading-relaxed mb-3 theme-transition">{agent.description}</p>
                      
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-[var(--text-muted)]">Model:</span>
                          <span className="text-[var(--text-primary)] font-bold">{agent.model}</span>
                        </div>
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-[var(--text-muted)]">Hardware:</span>
                          <span className="text-[var(--text-primary)]">{agent.hardware}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 pt-3 border-t border-[var(--border)]/40 theme-transition">
                      {agent.metrics.map((m, idx) => (
                        <div key={idx} className="text-center">
                          <span className="text-[9px] font-mono text-[var(--text-muted)] uppercase block">{m.label}</span>
                          <span className="text-[11px] font-bold text-[var(--text-primary)] font-mono">{m.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Synthesis Agent (Full Width Card) */}
                <div className="col-span-1 md:col-span-2 p-5 rounded-xl border border-[var(--border)] bg-[var(--surface)]/30 flex flex-col md:flex-row justify-between gap-4 theme-transition hover:border-[var(--border-focus)] transition-all">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">🧠</span>
                        <span className="text-xs font-bold text-[var(--text-primary)] theme-transition">Decision Synthesis Agent (Orchestrator)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${isChatStreaming ? "bg-indigo-500 animate-ping" : "bg-emerald-500"}`} />
                        <span className="text-[9px] font-mono font-bold tracking-wider uppercase text-[var(--text-muted)] theme-transition">
                          {isChatStreaming ? "QUERYING" : "IDLE"}
                        </span>
                      </div>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] leading-relaxed mb-3 theme-transition">
                      Acts as the synthesis hub. Performs hybrid semantic-relational search over ChromaDB and SQLite, traverses NetworkX nodes, and generates real-time streaming answer trace citations.
                    </p>
                    
                    <div className="space-y-1">
                      <div className="flex gap-4 text-[10px] font-mono">
                        <span className="text-[var(--text-muted)] w-16">Model:</span>
                        <span className="text-[var(--text-primary)] font-bold">Qwen 2.5 72B Instruct</span>
                      </div>
                      <div className="flex gap-4 text-[10px] font-mono">
                        <span className="text-[var(--text-muted)] w-16">Hardware:</span>
                        <span className="text-[var(--text-primary)]">AMD Instinct GPU (Fireworks Cloud)</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex md:flex-col justify-around gap-2 px-4 md:border-l border-[var(--border)]/40 theme-transition md:w-48 shrink-0">
                    {[
                      { label: "Queries Answered", value: "142" },
                      { label: "Avg Latency", value: "1.2s" },
                      { label: "Cache Hit Rate", value: "84.1%" }
                    ].map((m, idx) => (
                      <div key={idx} className="text-center md:text-left">
                        <span className="text-[9px] font-mono text-[var(--text-muted)] uppercase block">{m.label}</span>
                        <span className="text-[12px] font-bold text-[var(--text-primary)] font-mono">{m.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
