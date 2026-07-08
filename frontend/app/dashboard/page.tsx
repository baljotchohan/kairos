"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useKairosChat, Source, KairosStats } from "@/hooks/useKairosChat";
import { useAuth } from "@/hooks/useAuth";
import ConnectionStatus from "@/components/ConnectionStatus";
import SourcePanel from "@/components/SourcePanel";
import StreamingText, { ThinkingIndicator } from "@/components/StreamingText";
import DecisionGraph, { GraphNode, GraphEdge } from "@/components/DecisionGraph";
import { ChatHistoryPanel } from "@/components/ChatHistoryPanel";
import IntegrationGrid from "@/components/IntegrationGrid";
import KairosLogo from "@/components/KairosLogo";

type Tab = "chat" | "dashboard" | "decisions" | "integrations" | "agents" | "mcp";

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

const explorerDecisions = [
  { id: "dec-1", title: "Approve SaaS Vendor Contract Renewal ($2.3M/year)", date: "2019-11-15", owner: "John Smith", source: "drive", context: "Software contract approval for $2.3M/year with unchecked 3-year auto-renewals. Signed by former IT Director." },
  { id: "dec-2", title: "Choose React over Vue for Core Web Clients", date: "2022-08-06", owner: "Frontend Dev Team", source: "slack", context: "Selected React (4-2 vote) over Vue. Priya Sharma advocated Vue. Decided for larger hiring pool." },
  { id: "dec-3", title: "Terminate Project Phoenix (Mobile Client Development)", date: "2021-03-10", owner: "Board of Directors", source: "meeting", context: "Discontinued React Native client. Wrote down ₹40 Lakhs due to lack of team mobile development experience." },
  { id: "dec-4", title: "Migrate analytical pipelines from Redshift to BigQuery", date: "2024-02-12", owner: "Alex Rivera", source: "jira", context: "Data warehousing consolidation. BigQuery chosen due to native integration with streaming pipelines." },
  { id: "dec-5", title: "Implement SSO via Okta across all corporate platforms", date: "2023-05-18", owner: "Security Ops Team", source: "email", context: "Mandated SSO compliance before internal security audit. Approved by CEO." }
];

const McpLogos = {
  claude: (
    <img src="/claude-logo.svg" className="w-5 h-5 shrink-0 select-none pointer-events-none" alt="Claude" />
  ),
  chatgpt: (
    <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
      <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3654-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.8956zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.4071-.6772zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z" />
    </svg>
  ),
  cursor: (
    <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" fill="currentColor">
      <path d="M22.106 5.68L12.5.135a.998.998 0 00-.998 0L1.893 5.68a.84.84 0 00-.419.726v11.186c0 .3.16.577.42.727l9.607 5.547a.999.999 0 00.998 0l9.608-5.547a.84.84 0 00.42-.727V6.407a.84.84 0 00-.42-.726zm-.603 1.176L12.228 22.92c-.063.108-.228.064-.228-.061V12.34a.59.59 0 00-.295-.51l-9.11-5.26c-.107-.062-.063-.228.062-.228h18.55c.264 0 .428.286.296.514z" />
    </svg>
  ),
  antigravity: (
    <img src="/antigravity.svg" className="w-5 h-5 shrink-0 select-none pointer-events-none" alt="Antigravity" />
  )
};

// Animates a number counting up to `value` whenever it changes, instead of
// snapping — used for the metrics tab's stat tiles.
function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);

  useEffect(() => {
    const from = fromRef.current;
    const to = value;
    if (from === to) return;
    const duration = 700;
    let raf = 0;
    const start = typeof performance !== "undefined" ? performance.now() : 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <>{display.toFixed(decimals)}</>;
}

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

  const router = useRouter();

  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthActionPending, setIsAuthActionPending] = useState(false);

  const handleGoogleLogin = useCallback(async () => {
    setAuthError(null);
    setIsAuthActionPending(true);
    try {
      await loginWithGoogle();
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Google sign-in failed. Please try again.");
    } finally {
      setIsAuthActionPending(false);
    }
  }, [loginWithGoogle]);

  const handleGuestLogin = useCallback(async () => {
    setAuthError(null);
    setIsAuthActionPending(true);
    try {
      await loginAnonymously();
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Guest sign-in failed. Please try again.");
    } finally {
      setIsAuthActionPending(false);
    }
  }, [loginAnonymously]);

  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isGraphOpen, setIsGraphOpen] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [sidebarWidth, setSidebarWidth] = useState(240);
  const [historyWidth, setHistoryWidth] = useState(320);
  const [graphWidth, setGraphWidth] = useState(420);
  const [sourcesHeight, setSourcesHeight] = useState(200);
  const [isResizing, setIsResizing] = useState(false);

  // The sidebar/chat/graph three-pane layout uses fixed pixel widths that
  // simply can't coexist below ~700px — on a phone viewport they'd overlap
  // or force horizontal scroll. Below the md breakpoint the sidebar becomes
  // a slide-in overlay drawer (closed by default) and the graph panel
  // becomes a full-screen overlay instead of a fixed-width flex sibling.
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const apply = () => setIsMobile(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  useEffect(() => {
    if (isMobile) {
      setIsSidebarOpen(false);
      setIsGraphOpen(false);
    }
    // Intentionally only reacts to the mobile/desktop transition, not to
    // isMobile being read elsewhere — this just sets sane defaults once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMobile]);

  const handleResize = (
    direction: "horizontal" | "vertical",
    setter: React.Dispatch<React.SetStateAction<number>>,
    min: number,
    max: number,
    invert: boolean = false
  ) => (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startY = e.clientY;
    
    let initialSize = 0;
    setter((prev) => {
      initialSize = prev;
      return prev;
    });

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (direction === "horizontal") {
        const deltaX = moveEvent.clientX - startX;
        const newSize = initialSize + (invert ? -deltaX : deltaX);
        setter(Math.max(min, Math.min(max, newSize)));
      } else {
        const deltaY = moveEvent.clientY - startY;
        const newSize = initialSize + (invert ? -deltaY : deltaY);
        setter(Math.max(min, Math.min(max, newSize)));
      }
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  const {
    messages,
    isConnected,
    isReconnectExhausted,
    retryConnection,
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
  const [currentGraphEdges, setCurrentGraphEdges] = useState<GraphEdge[]>([]);
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
    github: "synced",
  });

  const [autoExtractionEnabled, setAutoExtractionEnabled] = useState(true);

  const [slackToken, setSlackToken] = useState("xoxb-8241793264-9182371239-••••••••");
  const [googleClient, setGoogleClient] = useState("9182371982-client.apps.googleusercontent.com");
  const [jiraUrl, setJiraUrl] = useState("https://company.atlassian.net");
  const [zoomKey, setZoomKey] = useState("z_api_key_8123981273");

  // System Sync logs console simulation
  const [logs, setLogs] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const [realDecisions, setRealDecisions] = useState<any[]>([]);
  const [activeSimulationDecisions, setActiveSimulationDecisions] = useState<any[]>([]);

  // Per-user remote MCP connect info (personal URL + ready-to-paste configs)
  const [mcpConnection, setMcpConnection] = useState<any>(null);
  const [mcpConnectionError, setMcpConnectionError] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [mcpPlatform, setMcpPlatform] = useState<"claude" | "chatgpt" | "cursor" | "antigravity">("claude");
  const [showMcpAdvanced, setShowMcpAdvanced] = useState<boolean>(false);

  // Per-user agent persona overrides (display name shown instead of the raw agent_key)
  const [agentPersonas, setAgentPersonas] = useState<Record<string, string>>({});

  // Decision Debt Score — pure SQL/graph aggregation, no LLM (core/decision_intelligence.py)
  const [debtScore, setDebtScore] = useState<{
    debt_score: number; high_risk_count: number; total_decisions: number; top_offenders: string[];
  } | null>(null);
  const [debtScoreLoading, setDebtScoreLoading] = useState(false);

  // Real MCP activity logs, fetched from /api/admin/mcp-activity (core/mcp_telemetry.py) —
  // previously this was a hardcoded array plus a setInterval that fabricated
  // random entries every 4.5s, with no relationship to actual MCP tool calls.
  const [mcpLogs, setMcpLogs] = useState<any[]>([]);

  const [mcpStats, setMcpStats] = useState({
    totalRequests: 0,
    readOps: 0,
    writeOps: 0,
    activeClients: 0
  });

  // Real on-disk storage size (MB), from /api/admin/status. Was a hardcoded 84.2.
  const [dbSizeMb, setDbSizeMb] = useState<number>(0);
  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  // Helper to compile a global graph from a list of decisions, deduping participants, sources, dates
  const compileGlobalGraph = useCallback((decisionsList: any[]) => {
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];
    const seenNodeIds = new Set<string>();
    const seenEdgeKeys = new Set<string>();

    const addNode = (node: GraphNode) => {
      if (!seenNodeIds.has(node.id)) {
        seenNodeIds.add(node.id);
        nodes.push(node);
      }
    };

    const addEdge = (source: string, target: string) => {
      const key1 = `${source}->${target}`;
      const key2 = `${target}->${source}`;
      if (!seenEdgeKeys.has(key1) && !seenEdgeKeys.has(key2)) {
        seenEdgeKeys.add(key1);
        edges.push({ source, target });
      }
    };

    decisionsList.forEach((d) => {
      const decisionId = d.id;
      
      let decIcon = "💡";
      const titleLower = (d.title || "").toLowerCase();
      if (titleLower.includes("react") || titleLower.includes("vue")) decIcon = "⚛️";
      else if (titleLower.includes("vendor") || titleLower.includes("contract")) decIcon = "🤝";
      else if (titleLower.includes("phoenix") || titleLower.includes("mobile")) decIcon = "📱";
      else if (titleLower.includes("redshift") || titleLower.includes("bigquery")) decIcon = "📊";
      else if (titleLower.includes("sso") || titleLower.includes("okta")) decIcon = "🔐";

      addNode({
        id: decisionId,
        label: d.title || "Untitled Decision",
        type: "decision",
        info: d.summary || d.context || "",
        icon: decIcon
      });

      let participantsList: string[] = [];
      if (Array.isArray(d.participants)) {
        participantsList = d.participants;
      } else if (typeof d.owner === "string" && d.owner !== "Unknown") {
        participantsList = d.owner.split(",").map((s: string) => s.trim());
      }

      participantsList.forEach((p: string) => {
        if (!p) return;
        const cleanName = p.trim();
        const personId = `person-${cleanName.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
        addNode({
          id: personId,
          label: cleanName,
          type: "person",
          info: "Participant",
          icon: "👤"
        });
        addEdge(decisionId, personId);
      });

      if (d.date) {
        const cleanDate = d.date.trim();
        const dateId = `date-${cleanDate.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
        addNode({
          id: dateId,
          label: cleanDate,
          type: "date",
          info: "Decision Date",
          icon: "📅"
        });
        addEdge(decisionId, dateId);
      }

      if (d.source) {
        const cleanSource = d.source.trim();
        const sourceId = `source-${cleanSource.toLowerCase()}`;
        
        let icon = "🔌";
        const srcLower = cleanSource.toLowerCase();
        if (srcLower === "slack") icon = "#";
        else if (srcLower === "email" || srcLower === "gmail") icon = "@";
        else if (srcLower === "drive" || srcLower === "google drive") icon = "D";
        else if (srcLower === "jira") icon = "J";
        else if (srcLower === "meeting" || srcLower === "zoom") icon = "M";

        addNode({
          id: sourceId,
          label: cleanSource.toUpperCase(),
          type: "source",
          info: d.source_url || "Ingested Source",
          icon: icon
        });
        addEdge(decisionId, sourceId);
      }

      if (d.outcome) {
        const cleanOutcome = d.outcome.trim();
        const outcomeId = `outcome-${decisionId}`;
        addNode({
          id: outcomeId,
          label: cleanOutcome,
          type: "outcome",
          info: "Decision Outcome",
          icon: "✅"
        });
        addEdge(decisionId, outcomeId);
      }
    });

    return { nodes, edges };
  }, []);

  // Synchronize decisions to global graph
  useEffect(() => {
    const decisionsToGraph = token ? realDecisions : activeSimulationDecisions;
    if (decisionsToGraph.length > 0) {
      const { nodes, edges } = compileGlobalGraph(decisionsToGraph);
      setCurrentGraphNodes(nodes);
      setCurrentGraphEdges(edges);
      setCurrentGraphTitle(token ? "Global Organizational Memory Network" : "Simulated Memory Graph");
    }
  }, [token, realDecisions, activeSimulationDecisions, compileGlobalGraph]);

  // When authenticated: show real stats or zeros (never fake demo numbers).
  // When guest/no token: show simulatedStats so the demo feels alive.
  const displayStats = (isConnected && stats)
    ? stats
    : token
      ? { total_decisions: 0, total_relations: 0, connected_components: 0 }
      : simulatedStats;
  const chatHistory = isConnected ? messages : simulatedMessages;
  const isChatStreaming = isConnected ? isStreaming : simulatedStreaming;
  const activeSources = chatHistory.length > 0 ? (chatHistory[chatHistory.length - 1]?.sources || []) : [];

  // Initialize theme from localStorage namespaced by user UID
  useEffect(() => {
    const themeKey = user ? `kairos-theme-${user.uid}` : "kairos-theme-default";
    const savedTheme = localStorage.getItem(themeKey) as "dark" | "light" | null;
    const currentTheme = savedTheme || "dark";
    setTheme(currentTheme);
    document.documentElement.setAttribute("data-theme", currentTheme);
    document.documentElement.className = `${currentTheme} h-full`;
  }, [user]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    const themeKey = user ? `kairos-theme-${user.uid}` : "kairos-theme-default";
    localStorage.setItem(themeKey, nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    document.documentElement.className = `${nextTheme} h-full`;
  };

  // Seed default decisions on mount if in simulation mode
  useEffect(() => {
    if (!token) {
      setActiveSimulationDecisions(explorerDecisions.slice(0, 2));
    } else {
      setActiveSimulationDecisions([]);
    }
  }, [token]);

  // Sync log simulation
  useEffect(() => {
    if (!user) return;

    const generalLogs = [
      "INFO: [chromadb] Persisting vector embeddings to ./chroma_db",
      "SUCCESS: [memory] SQLite database synchronized (relations updated)."
    ];

    const platformLogs: Record<string, string[]> = {
      slack: [
        "INFO: [slack] Polling Workspace channels...",
        "INFO: [slack] Found 1 new decision thread in #engineering-core",
        "SUCCESS: [slack] Ingested decision: Standardize analytical schemas to Parquet format"
      ],
      gmail: [
        "INFO: [gmail] Fetching unread approvals thread for user 'john.smith@company.com'"
      ],
      drive: [
        "INFO: [drive] Indexing spec changes in: architecture_v2_evaluation.docx",
        "SUCCESS: [drive] Mapped 3 relations (People: Priya, Technology: React, Date: Aug 2022)"
      ],
      jira: [
        "INFO: [jira] Scanning sprint epics for resolution status changes"
      ],
      zoom: [
        "INFO: [zoom] Running Whisper-large-v3 transcription on: Q4_Planning_Record.mp4",
        "SUCCESS: [zoom] Audio transcription completed (length: 42m 14s). Extracted 2 decisions."
      ],
      github: [
        "INFO: [github] Checking latest PR approvals and code owner reviews",
        "SUCCESS: [github] Parsed decision from PR-128: Shift database migrations to async script"
      ]
    };

    const getActiveLogPool = () => {
      const pool = [...generalLogs];
      let activeCount = 0;
      Object.keys(platformLogs).forEach((plat) => {
        if (syncStatus[plat] === "synced") {
          pool.push(...platformLogs[plat]);
          activeCount++;
        }
      });
      return { pool, activeCount };
    };

    const initialPoolData = getActiveLogPool();
    if (initialPoolData.activeCount === 0) {
      setLogs([
        `[${new Date().toLocaleTimeString()}] SYSTEM: Ingestion engine idle. No active connectors found. Go to Connectors to authorize apps.`
      ]);
    } else {
      setLogs([
        `[${new Date().toLocaleTimeString()}] SYSTEM: Ingestion engine initialized.`,
        `[${new Date().toLocaleTimeString()}] INFO: chromaDB persistence connected.`,
        ...initialPoolData.pool.slice(0, 2).map(msg => `[${new Date().toLocaleTimeString()}] ${msg}`)
      ]);
    }

    const interval = setInterval(() => {
      const poolData = getActiveLogPool();
      const timestamp = new Date().toLocaleTimeString();
      if (poolData.activeCount === 0) {
        setLogs((prev) => [...prev.slice(-30), `[${timestamp}] SYSTEM: Ingestion engine idle. No active connectors found. Go to Connectors to authorize apps.`]);
      } else {
        const randomMsg = poolData.pool[Math.floor(Math.random() * poolData.pool.length)];
        setLogs((prev) => [...prev.slice(-30), `[${timestamp}] ${randomMsg}`]);
      }
    }, 9000);

    return () => clearInterval(interval);
  }, [user, syncStatus]);

  // Handle user logout/switching cleanup
  useEffect(() => {
    if (!user) {
      setSimulatedMessages([]);
      setSimulatedStats({
        total_decisions: 0,
        total_relations: 0,
        connected_components: 0,
      });
      setSyncStatus({
        slack: "disconnected",
        gmail: "disconnected",
        drive: "disconnected",
        jira: "disconnected",
        zoom: "disconnected",
      });
      setSlackToken("");
      setGoogleClient("");
      setJiraUrl("");
      setZoomKey("");
      setLogs([]);
      setCurrentGraphNodes([]);
      setCurrentGraphTitle("");
    } else {
      if (!token) {
        setSyncStatus({
          slack: "synced",
          gmail: "synced",
          drive: "synced",
          jira: "synced",
          zoom: "synced",
          github: "synced",
        });
      } else {
        setSyncStatus({
          slack: "disconnected",
          gmail: "disconnected",
          drive: "disconnected",
          jira: "disconnected",
          zoom: "disconnected",
          github: "disconnected",
        });
      }
      setSlackToken("xoxb-8241793264-9182371239-••••••••");
      setGoogleClient("9182371982-client.apps.googleusercontent.com");
      setJiraUrl("https://company.atlassian.net");
      setZoomKey("z_api_key_8123981273");
    }
  }, [user, token]);

  // Fetch real connection statuses and db metrics from backend
  const fetchAdminStatus = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/admin/status", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.connectors) {
        const newSyncStatus: Record<string, string> = {};
        data.connectors.forEach((conn: any) => {
          newSyncStatus[conn.name] = conn.connected ? "synced" : "disconnected";
        });
        setSyncStatus(newSyncStatus);

        setSimulatedStats({
          total_decisions: data.total_decisions || 0,
          total_relations: data.total_relations || 0,
          connected_components: Math.ceil((data.total_decisions || 0) / 4)
        });
      }
      if (typeof data?.db_size_mb === "number") {
        setDbSizeMb(data.db_size_mb);
      }
    } catch (e) {
      console.error("Error fetching admin status", e);
    }
  }, [token]);

  const fetchSettings = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/memory/profile/settings", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data && typeof data.auto_extraction === "boolean") {
        setAutoExtractionEnabled(data.auto_extraction);
      }
    } catch (e) {
      console.error("Error fetching settings", e);
    }
  }, [token]);

  const toggleAutoExtraction = async (val: boolean) => {
    setAutoExtractionEnabled(val);
    if (!token) return;
    try {
      await fetch("/api/memory/profile/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ auto_extraction: val })
      });
    } catch (e) {
      console.error("Error updating settings", e);
    }
  };

  useEffect(() => {
    if (token) {
      fetchAdminStatus();
      fetchSettings();
    }
  }, [token, fetchAdminStatus, fetchSettings]);

  // Fetch real decisions dynamically from database
  const fetchRealDecisions = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/decisions", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.decisions) {
        setRealDecisions(data.decisions.map((d: any) => ({
          id: d.id,
          title: d.title,
          date: d.date,
          owner: d.participants?.join(", ") || "Unknown",
          source: d.source || "unknown",
          context: d.summary || ""
        })));
      }
    } catch (e) {
      console.error("Error fetching decisions", e);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchRealDecisions();
    } else {
      setRealDecisions([]);
    }
  }, [token, stats, fetchRealDecisions]);

  // Fetch single decision detail and compile its local star graph
  const fetchDecisionGraphData = useCallback(async (decisionId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`/api/decisions/${decisionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data) {
        const nodes: GraphNode[] = [];
        const edges: GraphEdge[] = [];

        const addEdge = (source: string, target: string) => {
          edges.push({ source, target });
        };
        
        nodes.push({
          id: data.id,
          label: data.title,
          type: "decision",
          info: data.summary,
          icon: "💡"
        });

        if (data.participants) {
          data.participants.forEach((p: string, idx: number) => {
            const pId = `${data.id}-person-${idx}`;
            nodes.push({
              id: pId,
              label: p,
              type: "person",
              info: "Participant",
              icon: "👤"
            });
            addEdge(data.id, pId);
          });
        }

        if (data.date) {
          const dId = `${data.id}-date`;
          nodes.push({
            id: dId,
            label: data.date,
            type: "date",
            info: "Decision Date",
            icon: "📅"
          });
          addEdge(data.id, dId);
        }

        if (data.source) {
          const sId = `${data.id}-source`;
          nodes.push({
            id: sId,
            label: data.source.toUpperCase(),
            type: "source",
            info: data.source_url || "Ingested Source",
            icon: getSourceIcon(data.source) === "◆" ? "📁" : "🔌"
          });
          addEdge(data.id, sId);
        }

        if (data.outcome) {
          const oId = `${data.id}-outcome`;
          nodes.push({
            id: oId,
            label: data.outcome,
            type: "outcome",
            info: "Decision Outcome",
            icon: "✅"
          });
          addEdge(data.id, oId);
        }

        if (data.related) {
          data.related.forEach((r: any) => {
            nodes.push({
              id: r.id,
              label: r.title,
              type: "decision",
              info: `Related | ${r.date} | ${r.source}`,
              icon: "🔗"
            });
            addEdge(data.id, r.id);
          });
        }

        setCurrentGraphNodes(nodes);
        setCurrentGraphEdges(edges);
        setCurrentGraphTitle(data.title);
      }
    } catch (e) {
      console.error("Error compiling local star graph", e);
    }
  }, [token]);

  // Refresh decision graph from backend after every completed assistant message
  useEffect(() => {
    if (!token || chatHistory.length === 0) return;
    const lastMsg = chatHistory[chatHistory.length - 1];
    if (lastMsg.role !== "assistant" || lastMsg.isStreaming) return;
    // Re-fetch decisions so newly stored nodes from live_data_agent appear
    fetchRealDecisions();
  }, [chatHistory, token, fetchRealDecisions]);

  // Poll graph every 45s while user has a token (picks up background ingestion)
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(fetchRealDecisions, 45000);
    return () => clearInterval(interval);
  }, [token, fetchRealDecisions]);

  // Fetch this user's personal remote-MCP connect info when the MCP tab opens
  const fetchMcpConnection = useCallback(() => {
    if (!token) return;
    setMcpConnectionError(false);
    fetch("/api/mcp/connection", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`status ${r.status}`))))
      .then((d) => setMcpConnection(d))
      .catch((e) => {
        console.error("Error fetching MCP connection", e);
        setMcpConnectionError(true);
      });
  }, [token]);

  useEffect(() => {
    if (activeTab !== "mcp" || !token) return;
    fetchMcpConnection();
  }, [activeTab, token, fetchMcpConnection]);

  // Fetch this user's agent persona overrides when the Agents tab opens
  useEffect(() => {
    if (activeTab !== "agents" || !token) return;
    fetch("/api/v1/agents", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.agents) return;
        const labels: Record<string, string> = {};
        for (const p of d.agents) labels[p.agent_key] = p.display_name;
        setAgentPersonas(labels);
      })
      .catch((e) => console.error("Error fetching agent personas", e));
  }, [activeTab, token]);

  // Fetch the Decision Debt Score when the Metrics tab opens
  useEffect(() => {
    if (activeTab !== "dashboard" || !token) return;
    setDebtScoreLoading(true);
    fetch("/api/v1/decisions/debt-score", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setDebtScore(d))
      .catch((e) => console.error("Error fetching decision debt score", e))
      .finally(() => setDebtScoreLoading(false));
  }, [activeTab, token]);

  // Real MCP activity — polls /api/admin/mcp-activity (core/mcp_telemetry.py),
  // which both MCP transports (mcp_server.py stdio tools, api/routes/mcp_remote.py)
  // write to on every actual tool call. Replaces a setInterval that used to
  // fabricate a random log entry + stat increment every 4.5s regardless of
  // whether any real MCP activity occurred.
  const guessLogo = (clientName: string): string => {
    const c = (clientName || "").toLowerCase();
    if (c.includes("claude")) return "claude";
    if (c.includes("cursor")) return "cursor";
    if (c.includes("chatgpt") || c.includes("openai")) return "chatgpt";
    if (c.includes("antigravity")) return "antigravity";
    return "generic";
  };

  const fetchMcpActivity = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/admin/mcp-activity", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data?.logs) {
        setMcpLogs(data.logs.map((log: any) => ({ ...log, logo: guessLogo(log.client) })));
      }
      if (data?.stats) {
        setMcpStats(data.stats);
      }
    } catch (e) {
      console.error("Error fetching MCP activity", e);
    }
  }, [token]);

  useEffect(() => {
    if (activeTab !== "mcp" || !token) return;
    fetchMcpActivity();
    const interval = setInterval(fetchMcpActivity, 8000);
    return () => clearInterval(interval);
  }, [activeTab, token, fetchMcpActivity]);

  // Compile combined decision graph from message citations
  useEffect(() => {
    if (!token || chatHistory.length === 0) return;
    const lastMsg = chatHistory[chatHistory.length - 1];
    if (lastMsg.role !== "assistant" || lastMsg.isStreaming) return;
    if (!lastMsg.sources || lastMsg.sources.length === 0) return;

    const compileCombinedGraph = async () => {
      try {
        const fetchPromises = lastMsg.sources.map(async (src: Source) => {
          try {
            const res = await fetch(`/api/decisions/${src.id}`, {
              headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) return await res.json();
          } catch (e) {
            console.error(`Failed to fetch decision ${src.id}`, e);
          }
          return null;
        });

        const results = await Promise.all(fetchPromises);
        const validResults = results.filter(Boolean);

        if (validResults.length === 0) return;

        const nodes: GraphNode[] = [];
        const edges: GraphEdge[] = [];
        const seenIds = new Set<string>();

        const addEdge = (source: string, target: string) => {
          edges.push({ source, target });
        };

        validResults.forEach((data: any) => {
          if (!seenIds.has(data.id)) {
            seenIds.add(data.id);
            nodes.push({
              id: data.id,
              label: data.title,
              type: "decision",
              info: data.summary,
              icon: "💡"
            });
          }

          if (data.participants) {
            data.participants.forEach((p: string, idx: number) => {
              const pid = `${data.id}-person-${idx}`;
              if (!seenIds.has(pid)) {
                seenIds.add(pid);
                nodes.push({
                  id: pid,
                  label: p,
                  type: "person",
                  info: "Participant",
                  icon: "👤"
                });
              }
              addEdge(data.id, pid);
            });
          }

          if (data.date) {
            const did = `${data.id}-date`;
            if (!seenIds.has(did)) {
              seenIds.add(did);
              nodes.push({
                id: did,
                label: data.date,
                type: "date",
                info: "Decision Date",
                icon: "📅"
              });
            }
            addEdge(data.id, did);
          }

          if (data.source) {
            const sid = `${data.id}-source`;
            if (!seenIds.has(sid)) {
              seenIds.add(sid);
              nodes.push({
                id: sid,
                label: data.source.toUpperCase(),
                type: "source",
                info: data.source_url || "Ingested Source",
                icon: getSourceIcon(data.source) === "◆" ? "📁" : "🔌"
              });
            }
            addEdge(data.id, sid);
          }

          if (data.outcome) {
            const oid = `${data.id}-outcome`;
            if (!seenIds.has(oid)) {
              seenIds.add(oid);
              nodes.push({
                id: oid,
                label: data.outcome,
                type: "outcome",
                info: "Decision Outcome",
                icon: "✅"
              });
            }
            addEdge(data.id, oid);
          }

          if (data.related) {
            data.related.forEach((r: any) => {
              if (!seenIds.has(r.id)) {
                seenIds.add(r.id);
                nodes.push({
                  id: r.id,
                  label: r.title,
                  type: "decision",
                  info: `Related | ${r.date} | ${r.source}`,
                  icon: "🔗"
                });
              }
              addEdge(data.id, r.id);
            });
          }
        });

        setCurrentGraphNodes(nodes);
        setCurrentGraphEdges(edges);
        setCurrentGraphTitle(`Combined Query Sources Graph (${validResults.length} decisions)`);
      } catch (err) {
        console.error("Error compiling combined graph", err);
      }
    };

    void compileCombinedGraph();
  }, [chatHistory, token]);

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

          let matchedDecId = "";
          if (textLower.includes("vendor") || textLower.includes("paying") || textLower.includes("2.3")) {
            matchedDecId = "dec-1";
          } else if (textLower.includes("react") || textLower.includes("vue") || textLower.includes("framework")) {
            matchedDecId = "dec-2";
          } else if (textLower.includes("mobile") || textLower.includes("phoenix") || textLower.includes("app")) {
            matchedDecId = "dec-3";
          }

          if (matchedDecId) {
            const decObj = explorerDecisions.find(d => d.id === matchedDecId);
            if (decObj) {
              setActiveSimulationDecisions(prev => {
                if (prev.some(d => d.id === matchedDecId)) return prev;
                return [...prev, decObj];
              });
            }
          }

          setSimulatedStats((prev) => ({
            ...prev,
            total_decisions: prev.total_decisions + 1,
            total_relations: prev.total_relations + 4,
          }));
          setLogs((prev) => [
            ...prev,
            `[${timestamp}] INFO: Query matches decision index for: "${userText.slice(0, 20)}..."`,
            `[${timestamp}] SUCCESS: Extracted decision graph with updated nodes.`
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
      setActiveSimulationDecisions(explorerDecisions.slice(0, 2));
    }
  };

  const triggerSync = async (platform: string) => {
    setSyncStatus((prev) => ({ ...prev, [platform]: "syncing" }));
    const startTimestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${startTimestamp}] INFO: Triggering sync on platform connector: [${platform}]`]);

    if (!token) {
      // Demo mode — simulate locally
      setTimeout(() => {
        setSyncStatus((prev) => ({ ...prev, [platform]: "synced" }));
        const doneTimestamp = new Date().toLocaleTimeString();
        setLogs((prev) => [...prev, `[${doneTimestamp}] DEMO: Sync simulated (sign in to ingest real data)`]);
      }, 1200);
      return;
    }

    try {
      const res = await fetch("/api/v1/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ sources: [platform], lookback_days: 30 }),
      });
      const doneTimestamp = new Date().toLocaleTimeString();
      if (res.ok) {
        setSyncStatus((prev) => ({ ...prev, [platform]: "synced" }));
        setLogs((prev) => [
          ...prev,
          `[${doneTimestamp}] SUCCESS: Ingestion started for [${platform}] — decisions will appear shortly`,
        ]);
        // Refresh graph after a short delay to pick up new decisions
        setTimeout(() => {
          fetchRealDecisions();
          fetchAdminStatus();
        }, 15000);
      } else {
        setSyncStatus((prev) => ({ ...prev, [platform]: "error" }));
        setLogs((prev) => [...prev, `[${doneTimestamp}] ERROR: Ingest failed for [${platform}]: ${res.status}`]);
      }
    } catch (e) {
      setSyncStatus((prev) => ({ ...prev, [platform]: "error" }));
      const errTimestamp = new Date().toLocaleTimeString();
      setLogs((prev) => [...prev, `[${errTimestamp}] ERROR: Network error triggering sync for [${platform}]`]);
    }
  };

  const exportDecisionIndex = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(filteredDecisions, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `kairos_decisions_${selectedSourceFilter}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${timestamp}] SYSTEM: Exported decision index JSON payload.`]);
  };

  const exportDecisionPDF = () => {
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    const html = `
      <html>
        <head>
          <title>KAIROS Decision Index Export - ${new Date().toLocaleDateString()}</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
              color: #111;
              line-height: 1.5;
              padding: 40px;
              max-width: 800px;
              margin: 0 auto;
            }
            .header {
              border-bottom: 2px solid #333;
              padding-bottom: 20px;
              margin-bottom: 30px;
            }
            .logo {
              font-size: 24px;
              font-weight: bold;
              letter-spacing: -0.5px;
            }
            .subtitle {
              font-size: 12px;
              color: #666;
              font-family: monospace;
              margin-top: 5px;
            }
            .summary-info {
              margin-top: 15px;
              font-size: 13px;
              color: #444;
            }
            .decision-card {
              border-bottom: 1px solid #eee;
              padding: 20px 0;
              page-break-inside: avoid;
            }
            .decision-title {
              font-size: 18px;
              font-weight: bold;
              color: #111;
              margin: 0 0 8px 0;
            }
            .meta-grid {
              display: grid;
              grid-template-columns: repeat(4, 1fr);
              gap: 10px;
              font-size: 11px;
              color: #666;
              margin-bottom: 12px;
              font-family: monospace;
              background: #f9f9f9;
              padding: 8px 12px;
              border-radius: 6px;
            }
            .meta-item strong {
              color: #333;
            }
            .section-title {
              font-size: 12px;
              font-weight: bold;
              text-transform: uppercase;
              letter-spacing: 0.5px;
              color: #444;
              margin: 12px 0 4px 0;
            }
            .section-content {
              font-size: 13px;
              color: #222;
              margin-bottom: 10px;
            }
            @media print {
              body {
                padding: 20px;
              }
              .decision-card {
                page-break-inside: avoid;
              }
            }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="logo">KAIROS Decision Index Export</div>
            <div class="subtitle">Generated on ${new Date().toLocaleString()} · Scope: ${selectedSourceFilter.toUpperCase()}</div>
            <div class="summary-info">Exported <strong>${filteredDecisions.length}</strong> decisions from corporate memory.</div>
          </div>
          <div>
            ${filteredDecisions.map((d, index) => `
              <div class="decision-card">
                <h2 class="decision-title">${index + 1}. ${d.title}</h2>
                <div class="meta-grid">
                  <div class="meta-item"><strong>Date:</strong> ${d.date}</div>
                  <div class="meta-item"><strong>Source:</strong> ${d.source.toUpperCase()}</div>
                  <div class="meta-item"><strong>Owner:</strong> ${d.owner || "N/A"}</div>
                  <div class="meta-item"><strong>ID:</strong> ${d.id.slice(0, 8)}...</div>
                </div>
                <div class="section-title">Context / Rationale</div>
                <div class="section-content">${d.context || "No context provided."}</div>
                ${d.outcome ? `
                  <div class="section-title">Outcome</div>
                  <div class="section-content">${d.outcome}</div>
                ` : ""}
              </div>
            `).join("")}
          </div>
          <script>
            window.onload = function() {
              window.print();
              setTimeout(function() { window.close(); }, 500);
            }
          </script>
        </body>
      </html>
    `;

    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${timestamp}] SYSTEM: Exported decision index PDF document.`]);
  };

  const getSourceIcon = (source: string) => {
    switch (source.toLowerCase()) {
      case "slack": return "#";
      case "email":
      case "gmail": return "@";
      case "drive":
      case "google drive": return "D";
      case "jira": return "J";
      case "meeting":
      case "zoom": return "M";
      case "notion":
      case "notion page":
      case "notion database":
      case "notion_page":
      case "notion_db": return "N";
      case "github": return "⌥";
      default: return "◆";
    }
  };



  const decisionsToUse = token ? realDecisions : explorerDecisions;

  const filteredDecisions = decisionsToUse.filter((d) => {
    const matchesSearch = d.title.toLowerCase().includes(searchQuery.toLowerCase()) || d.owner.toLowerCase().includes(searchQuery.toLowerCase()) || d.context.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = selectedSourceFilter === "all" || d.source.toLowerCase() === selectedSourceFilter;
    return matchesSearch && matchesSource;
  });



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
      <div className="flex h-full w-full bg-[rgb(var(--bg))] text-[rgb(var(--text-primary))] items-center justify-center p-6 relative">
        {/* Toggle Theme button top right */}
        <div className="absolute top-4 right-4">
          <button
            onClick={toggleTheme}
            className="p-2 hover:bg-[rgb(var(--surface-hover))] border border-[rgb(var(--border))] rounded text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all theme-transition animate-[fadeIn_0.3s_ease-out]"
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

        <div className="w-full max-w-sm p-6 rounded-2xl border border-[rgb(var(--border))] bg-[rgb(var(--surface))] text-center shadow-lg flex flex-col gap-6 theme-transition animate-message-in">
          {/* Logo */}
          <div className="flex flex-col items-center gap-2 mt-4">
            <div className="w-64 h-16 flex items-center justify-center">
              <KairosLogo size={52} showText />
            </div>
            <p className="text-[9px] text-[rgb(var(--text-muted))] font-mono tracking-widest font-semibold uppercase">Memory OS</p>
          </div>

          <div className="space-y-1.5">
            <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
              Every company forgets why it made its decisions. KAIROS never does. Connect to your workspace memory.
            </p>
          </div>

          {/* Login Buttons */}
          <div className="flex flex-col gap-2 mt-2 mb-4">
            <button
              onClick={handleGoogleLogin}
              disabled={isAuthActionPending}
              className="w-full py-2.5 px-4 bg-transparent border border-[rgb(var(--border))] hover:bg-[rgb(var(--surface-hover))] rounded-xl text-xs font-semibold text-[rgb(var(--text-primary))] flex items-center justify-center gap-3.5 transition-all theme-transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {/* Google Icon */}
              <svg className="w-4 h-4" viewBox="0 0 48 48">
                <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
                <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
                <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
                <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
              </svg>
              Sign In with Google
            </button>
            <button
              onClick={handleGuestLogin}
              disabled={isAuthActionPending}
              className="w-full py-2.5 px-4 bg-[rgb(var(--text-primary))] hover:opacity-90 border border-[rgb(var(--border))] rounded-xl text-xs font-semibold text-[rgb(var(--bg))] flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4 text-[rgb(var(--bg))]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Continue as Guest
            </button>
            {authError && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-left animate-pop-in">
                <span className="text-rose-400 text-xs mt-px">!</span>
                <p className="text-[11px] text-rose-300 leading-relaxed">{authError}</p>
              </div>
            )}
          </div>

          <div className="text-[9px] text-[rgb(var(--text-muted))] font-mono uppercase tracking-wider">
            {isSimulation ? "Running in client-simulation mode" : "Secured by Firebase Auth"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full bg-[rgb(var(--bg))] text-[rgb(var(--text-primary))] overflow-hidden theme-transition animate-[fadeIn_0.4s_var(--ease-out-expo)_both] relative">

      {/* Mobile sidebar backdrop — tap to close the drawer */}
      {isMobile && isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* 1. LEFT SIDEBAR — a slide-in overlay drawer on mobile (closed by
          default, opened via the hamburger button), a normal flex sibling
          with a resizable width on desktop */}
      {(!isMobile || isSidebarOpen) && (
      <div
        className={`bg-[rgb(var(--surface))] border-r border-[rgb(var(--border))]/60 flex flex-col justify-between shrink-0 theme-transition ${
          isMobile ? "fixed inset-y-0 left-0 z-50" : "relative"
        }`}
        style={{
          width: isMobile ? "min(85vw, 300px)" : (isSidebarOpen ? `${sidebarWidth}px` : "64px"),
          transition: isResizing ? "none" : "width 0.3s ease, background-color 0.2s ease, border-color 0.2s ease",
        }}
      >
        {isSidebarOpen && (
          <div
            className="w-1 cursor-col-resize hover:bg-[rgb(var(--accent))]/45 active:bg-[rgb(var(--accent))] transition-colors absolute right-0 top-0 bottom-0 z-50"
            onMouseDown={handleResize("horizontal", setSidebarWidth, 180, 400)}
          />
        )}
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo & Sidebar Controls */}
          <div className={`p-4 border-b border-[rgb(var(--border))]/40 flex theme-transition ${
            isSidebarOpen ? "items-center justify-between" : "flex-col items-center gap-3"
          }`}>
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="h-7 flex items-center shrink-0">
                <KairosLogo size={26} showText={isSidebarOpen} />
              </div>
            </div>
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-1.5 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/60 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all shrink-0"
              title={isSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            >
              {isSidebarOpen ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-3 border-b border-[rgb(var(--border))]/30 flex justify-center">
            {isSidebarOpen ? (
              <button
                onClick={handleNewChat}
                className="w-full py-2 px-4 border border-[rgb(var(--border))] hover:border-[rgb(var(--border-focus))] bg-transparent hover:bg-[rgb(var(--surface-hover))]/60 rounded-xl text-xs font-semibold text-[rgb(var(--text-primary))] flex items-center justify-center gap-2.5 transition-all"
              >
                <svg className="w-4 h-4 text-[rgb(var(--text-muted))]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                New Chat
              </button>
            ) : (
              <button
                onClick={handleNewChat}
                className="w-9 h-9 border border-[rgb(var(--border))] hover:border-[rgb(var(--border-focus))] bg-transparent hover:bg-[rgb(var(--surface-hover))]/60 rounded-full text-[rgb(var(--text-primary))] flex items-center justify-center transition-all"
                title="New Chat"
              >
                <svg className="w-4 h-4 text-[rgb(var(--text-muted))]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            )}
          </div>

          {/* Navigation Links */}
          <div className="px-2.5 py-3 flex flex-col gap-1 border-b border-[rgb(var(--border))]/30">
            {[
              {
                id: "chat",
                label: "Chat Console",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                )
              },
              {
                id: "dashboard",
                label: "Metrics Overview",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
                  </svg>
                )
              },
              {
                id: "decisions",
                label: "Decision Index",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                )
              },
              {
                id: "integrations",
                label: "Connectors",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                )
              },
              {
                id: "agents",
                label: "AI Agents",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                  </svg>
                )
              },
              {
                id: "mcp",
                label: "MCP Server",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                )
              }
            ].map((link) => {
              const isActive = activeTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => {
                    setActiveTab(link.id as Tab);
                  }}
                  className={`relative flex items-center rounded-xl text-xs font-semibold transition-all group ${
                    isSidebarOpen ? "gap-3 px-3.5 py-2.5 w-full" : "justify-center w-10 h-10 mx-auto"
                  } ${
                    isActive
                      ? "bg-[rgb(var(--surface-hover))] text-[rgb(var(--text-primary))] shadow-sm"
                      : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--surface-hover))]/40"
                  }`}
                  title={link.label}
                >
                  {isActive && (
                    <span className={`absolute rounded-full bg-[rgb(var(--accent))] shadow-[0_0_8px_rgb(var(--accent))] ${
                      isSidebarOpen ? "left-1.5 top-3.5 bottom-3.5 w-0.5" : "left-1 top-2.5 bottom-2.5 w-0.5"
                    }`} />
                  )}
                  <div className="shrink-0 transition-transform duration-200 group-hover:scale-105">
                    {link.icon}
                  </div>
                  {isSidebarOpen && link.label}
                </button>
              );
            })}
 
            {/* Conversational Memory Toggle */}
            <button
              onClick={() => {
                setActiveTab("chat");
                setIsHistoryOpen(!isHistoryOpen);
              }}
              className={`relative flex items-center rounded-xl text-xs font-semibold transition-all group ${
                isSidebarOpen ? "gap-3 px-3.5 py-2.5 w-full" : "justify-center w-10 h-10 mx-auto"
              } ${
                isHistoryOpen
                  ? "bg-[rgb(var(--accent))]/10 text-[rgb(var(--accent))] border border-[rgb(var(--accent))]/20 shadow-sm"
                  : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--surface-hover))]/40"
              }`}
              title="Conversational Memory"
            >
              {isHistoryOpen && (
                <span className={`absolute rounded-full bg-[rgb(var(--accent))] shadow-[0_0_8px_rgb(var(--accent))] ${
                  isSidebarOpen ? "left-1.5 top-3.5 bottom-3.5 w-0.5" : "left-1 top-2.5 bottom-2.5 w-0.5"
                }`} />
              )}
              <div className="shrink-0 transition-transform duration-200 group-hover:scale-105">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              {isSidebarOpen && "Conversational Memory"}
            </button>
          </div>

          {/* Learned User Profile Context */}
          {userProfile && (userProfile.department || userProfile.role_context || (userProfile.frequent_topics && userProfile.frequent_topics.length > 0)) && (
            isSidebarOpen ? (
              <div className="mx-3 mt-4 p-3.5 bg-gradient-to-br from-[rgb(var(--accent))]/5 to-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/15 rounded-2xl text-[11px] theme-transition shadow-sm shadow-[rgb(var(--accent))]/2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono text-[rgb(var(--accent))] font-bold uppercase tracking-wider">
                    🧠 Learned Profile
                  </span>
                  <button
                    onClick={resetProfile}
                    className="text-[9px] font-mono text-rose-400 hover:text-rose-300 hover:underline"
                    title="Reset profile"
                  >
                    Reset
                  </button>
                </div>
                {userProfile.department && (
                  <div className="flex justify-between py-1 border-b border-[rgb(var(--accent))]/5 text-[rgb(var(--text-muted))]">
                    <span>Department:</span>
                    <span className="text-[rgb(var(--text-primary))] font-semibold">{userProfile.department}</span>
                  </div>
                )}
                {userProfile.role_context && (
                  <p className="text-[rgb(var(--text-muted))] mt-1.5 italic leading-normal">
                    "{userProfile.role_context}"
                  </p>
                )}
                {userProfile.frequent_topics && userProfile.frequent_topics.length > 0 && (
                  <div className="mt-2.5">
                    <span className="text-[9.5px] text-[rgb(var(--text-muted))] block mb-1">Top Topics:</span>
                    <div className="flex flex-wrap gap-1">
                      {userProfile.frequent_topics.map((t: string, idx: number) => (
                        <span key={idx} className="bg-[rgb(var(--accent))]/15 text-[rgb(var(--accent))] px-1.5 py-0.5 rounded-[4px] text-[9px] font-semibold">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex justify-center mt-5">
                <span className="cursor-help text-sm filter grayscale hover:grayscale-0 transition-all p-1 hover:bg-[rgb(var(--surface-hover))]/60 rounded-lg" title={`🧠 Learned Profile:\n${userProfile.role_context || "Context active"}`}>
                  🧠
                </span>
              </div>
            )
          )}

          {/* Conversational Memory (Session History inline) */}
          {isSidebarOpen && isHistoryOpen && (
            <div className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-2">
              <span className="text-[10px] text-[rgb(var(--text-muted))] font-mono tracking-wider font-bold px-2.5">CONVERSATIONAL MEMORY</span>
              <div className="flex flex-col gap-0.5 mt-1">
                {sessions.length > 0 ? sessions.slice(0, 8).map((session) => (
                  <button
                    key={session.session_id}
                    onClick={() => {
                      setActiveTab("chat");
                      loadSession(session.session_id);
                    }}
                    className={`w-full text-left px-2.5 py-2 hover:bg-[rgb(var(--surface-hover))]/60 rounded-xl text-[11.5px] font-medium truncate transition-all ${
                      activeSessionId === session.session_id
                        ? "text-[rgb(var(--text-primary))] bg-[rgb(var(--surface-hover))]/40"
                        : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                    }`}
                  >
                    {session.preview || "New Session"}
                  </button>
                )) : (
                  <p className="text-[10px] text-[rgb(var(--text-muted))]/60 px-2.5 italic">No sessions yet. Start chatting!</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-[rgb(var(--border))]/40 bg-[rgb(var(--surface))]/90 flex flex-col gap-3">
          {isSidebarOpen ? (
            <>
              {/* Profile card */}
              <div className="flex items-center justify-between pb-2.5 border-b border-[rgb(var(--border))]/40">
                <div className="flex items-center gap-2.5 overflow-hidden">
                  {user.photoURL ? (
                    <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full object-cover shrink-0 shadow-sm ring-1 ring-[rgb(var(--border))]/30" />
                  ) : (
                    <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white flex items-center justify-center shrink-0 font-bold text-[11px] shadow-sm shadow-indigo-500/10">
                      {user.displayName ? user.displayName.charAt(0) : "G"}
                    </div>
                  )}
                  <div className="flex flex-col overflow-hidden">
                    <span className="text-[11.5px] font-semibold text-[rgb(var(--text-primary))] truncate leading-tight">
                      {user.displayName || "Guest User"}
                    </span>
                    <span className="text-[9px] text-[rgb(var(--text-muted))] truncate mt-0.5">
                      {user.email || "Temporary Access"}
                    </span>
                  </div>
                </div>
                <button
                  onClick={logout}
                  className="p-1.5 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/60 rounded-lg text-[rgb(var(--text-muted))] hover:text-rose-400 transition-all shrink-0"
                  title="Sign Out"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              </div>

              {/* Theme & Connection status indicators */}
              <div className="flex items-center justify-between text-[10px] text-[rgb(var(--text-muted))] font-mono">
                <span>Theme:</span>
                <button
                  onClick={toggleTheme}
                  className="p-1 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/80 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all"
                  title="Toggle Theme"
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
              <div className="flex items-center justify-between text-[10px] text-[rgb(var(--text-muted))] font-mono">
                <span>Sync Engine:</span>
                <ConnectionStatus isConnected={isConnected} exhausted={isReconnectExhausted} onRetry={retryConnection} />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-3.5">
              {/* Profile Avatar */}
              {user.photoURL ? (
                <img src={user.photoURL} alt="" className="w-8 h-8 rounded-full object-cover shadow-sm ring-1 ring-[rgb(var(--border))]/30" title={`${user.displayName || "Guest User"} (${user.email || "Guest"})`} />
              ) : (
                <div 
                  className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shadow-sm"
                  title={`${user.displayName || "Guest User"} (${user.email || "Guest"})`}
                >
                  {user.displayName ? user.displayName.charAt(0) : "G"}
                </div>
              )}

              {/* Theme Toggle */}
              <button
                onClick={toggleTheme}
                className="p-2 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/85 rounded-xl text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all"
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

              {/* Status Indicator */}
              <div title={isConnected ? "Sync Engine: Connected" : "Sync Engine: Offline"}>
                <span className="relative flex h-2.5 w-2.5">
                  {isConnected && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                  )}
                  <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isConnected ? "bg-emerald-500" : "bg-red-500"}`} />
                </span>
              </div>

              {/* Logout Button */}
              <button
                onClick={logout}
                className="p-2 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/85 rounded-xl text-[rgb(var(--text-muted))] hover:text-rose-400 transition-all"
                title="Sign Out"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>
      )}

      {/* 2. MAIN CONTAINER */}
      <main className="flex-1 flex flex-col min-w-0 bg-[rgb(var(--bg))] relative transition-colors duration-300">
        
        {/* Header */}
        <header className="h-14 border-b border-[rgb(var(--border))]/30 flex items-center justify-between px-3 md:px-6 shrink-0 bg-[rgb(var(--surface))]/70 backdrop-blur-xl z-20 gap-2">
          <div className="flex items-center gap-3 min-w-0">
            {isMobile && (
              <button
                onClick={() => setIsSidebarOpen(true)}
                className="p-1.5 -ml-1 shrink-0 hover:bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/60 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all"
                title="Open Menu"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <div className="flex items-center gap-2 select-none min-w-0">
              <span className="hidden sm:inline text-[10px] font-bold text-[rgb(var(--text-muted))] tracking-wider uppercase font-mono">KAIROS</span>
              <span className="hidden sm:inline text-[10px] text-[rgb(var(--text-muted))]/40 font-mono">/</span>
              <span className="text-[11px] font-bold text-[rgb(var(--text-primary))] bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/50 px-2.5 py-1 rounded-lg uppercase tracking-wider font-mono shadow-sm truncate">
                {activeTab === "chat" ? "Chat Console" : activeTab === "dashboard" ? "Metrics Overview" : activeTab === "decisions" ? "Decision Index" : activeTab === "integrations" ? "Connectors" : activeTab === "agents" ? "AI Agents" : "MCP Server"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-3 shrink-0">
            {activeTab === "chat" && (
              <button
                onClick={() => setIsGraphOpen(!isGraphOpen)}
                className={`px-2.5 md:px-3 py-1.5 rounded-xl border text-[9.5px] font-bold tracking-wider font-mono transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] shadow-sm whitespace-nowrap ${
                  isGraphOpen
                    ? "bg-[rgb(var(--surface-hover))] border-[rgb(var(--border-focus))] text-[rgb(var(--text-primary))]"
                    : "bg-transparent border-[rgb(var(--border))] text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                }`}
              >
                {isGraphOpen ? "HIDE GRAPH" : "SHOW GRAPH"}
              </button>
            )}
            <span className="hidden sm:flex items-center gap-1.5 text-[9.5px] font-mono px-2.5 py-1 rounded-lg bg-[rgb(var(--surface))]/80 border border-[rgb(var(--border))]/55 text-[rgb(var(--text-muted))] font-bold shadow-sm select-none">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              OS ENGINE: OK
            </span>
          </div>
        </header>

        {/* Tab Router Contents */}
        <div className="flex-1 overflow-y-auto">
          {/* CHAT CONSOLE */}
          {activeTab === "chat" && (
            <div className="h-[calc(100vh-3.5rem)] flex overflow-hidden animate-message-in">

              {/* Chat History Panel (Past Sessions) */}


               {/* Left Column: Chat log */}
              <div className="flex-1 flex flex-col h-full bg-[rgb(var(--bg))] relative min-w-0">
                
                {/* Message list */}
                <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-8">
                  <div className="max-w-4xl mx-auto space-y-8 w-full">
                    
                    {/* Welcome Empty State Screen */}
                    {chatHistory.length === 0 && (
                      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-2xl mx-auto gap-8 px-4 animate-[fadeIn_0.3s_ease-out]">
                        <div className="flex flex-col items-center gap-3">
                          <div className="w-20 h-20 flex items-center justify-center">
                            <KairosLogo size={64} />
                          </div>
                          <h1 className="text-3xl font-extrabold tracking-tight text-[rgb(var(--text-primary))] mt-2">What do you want to analyze today?</h1>
                          <p className="text-sm text-[rgb(var(--text-muted))] max-w-md mt-1 leading-relaxed">
                            KAIROS scans your corporate history across Slack channels, Gmail, G Drive documentation, Zoom meetings, and Jira boards to resolve tech tradeoffs, contract terms, or retrospects.
                          </p>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 w-full max-w-xl">
                          {[
                            {
                              title: "React vs Vue",
                              desc: "Why do we use React instead of Vue?",
                              icon: "⚛️",
                              query: "Why do we use React instead of Vue?"
                            },
                            {
                              title: "Vendor Contract",
                              desc: "Why are we paying this vendor $2.3M/year?",
                              icon: "💸",
                              query: "Why are we paying this vendor $2.3M/year?"
                            },
                            {
                              title: "Mobile Retrospective",
                              desc: "Has anyone tried building a mobile app before?",
                              icon: "📱",
                              query: "Has anyone tried building a mobile app before?"
                            }
                          ].map((card, idx) => (
                            <button
                              key={idx}
                              onClick={() => {
                                setInputVal(card.query);
                                if (isConnected) {
                                  sendQuestion(card.query);
                                } else {
                                  setInputVal("");
                                  setSimulatedStreaming(true);
                                  const newMsgList = [...simulatedMessages, { id: Math.random().toString(), role: "user", content: card.query, sources: [] }];
                                  setSimulatedMessages(newMsgList);
                                  const textLower = card.query.toLowerCase();
                                  const match = SIMULATED_RESPONSES.find((resp) =>
                                    resp.keywords.some((kw) => textLower.includes(kw))
                                  );
                                  setTimeout(() => {
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

                                      let matchedDecId = "";
                                      if (textLower.includes("vendor") || textLower.includes("paying") || textLower.includes("2.3")) {
                                        matchedDecId = "dec-1";
                                      } else if (textLower.includes("react") || textLower.includes("vue") || textLower.includes("framework")) {
                                        matchedDecId = "dec-2";
                                      } else if (textLower.includes("mobile") || textLower.includes("phoenix") || textLower.includes("app")) {
                                        matchedDecId = "dec-3";
                                      }

                                      if (matchedDecId) {
                                        const decObj = explorerDecisions.find(d => d.id === matchedDecId);
                                        if (decObj) {
                                          setActiveSimulationDecisions(prev => {
                                            if (prev.some(d => d.id === matchedDecId)) return prev;
                                            return [...prev, decObj];
                                          });
                                        }
                                      }
                                    }
                                    setSimulatedStreaming(false);
                                  }, 1000);
                                }
                              }}
                              className="text-left p-4 rounded-2xl border border-[rgb(var(--border))]/80 hover:border-[rgb(var(--border-focus))] bg-[rgb(var(--surface))]/10 hover:bg-[rgb(var(--surface-hover))]/20 transition-all flex flex-col gap-2.5 group cursor-pointer shadow-sm"
                            >
                              <span className="text-xl">{card.icon}</span>
                              <div>
                                <h4 className="text-xs font-bold text-[rgb(var(--text-primary))] group-hover:text-[rgb(var(--accent))] transition-colors">{card.title}</h4>
                                <p className="text-[11px] text-[rgb(var(--text-muted))] leading-normal mt-1">{card.desc}</p>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Messages flow */}
                    {chatHistory.map((msg, i) => (
                      <div
                        key={msg.id || i}
                        className={`w-full flex gap-5 items-start animate-message-in ${
                          msg.role === "user" ? "justify-end py-1" : "py-5 border-b border-[rgb(var(--border))]/30"
                        }`}
                      >
                        {msg.role === "assistant" && (
                          <div className="w-8 h-8 flex items-center justify-center shrink-0">
                            <KairosLogo size={28} />
                          </div>
                        )}

                        <div
                          className={`overflow-hidden ${
                            msg.role === "user"
                              ? "max-w-[75%] bg-[rgb(var(--surface-hover))] px-4 py-3 rounded-2xl text-[14px] leading-relaxed text-[rgb(var(--text-primary))] shadow-sm"
                              : "flex-1 space-y-4 text-[14.5px] leading-relaxed text-[rgb(var(--text-primary))]"
                          }`}
                        >
                          {msg.thinkingStep && !msg.content ? (
                            <div className="flex flex-col gap-1.5">
                              <ThinkingIndicator />
                              <p className="text-[11.5px] text-[rgb(var(--text-muted))] pl-7 truncate">
                                {msg.thinkingStep.agent} · {msg.thinkingStep.content}
                              </p>
                            </div>
                          ) : (
                            <StreamingText
                              text={msg.content}
                              isStreaming={msg.isStreaming ?? false}
                              hasWarning={msg.hasWarning}
                              className="kairos-prose"
                            />
                          )}

                          {/* Assistant Metadata Context */}
                          {msg.role === "assistant" && (
                            <div className="flex items-center gap-3.5 mt-3 flex-wrap">
                              {msg.intent && (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-[10.5px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
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
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-[rgb(var(--text-muted))] font-mono uppercase">Confidence:</span>
                                  <div className="w-16 h-1.5 bg-[rgb(var(--surface-hover))] rounded-full overflow-hidden border border-[rgb(var(--border))]/50">
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
                                  <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] font-bold">{(msg.confidence * 100).toFixed(0)}%</span>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Trace block */}
                          {msg.traces && msg.traces.length > 0 && (
                            <details className="text-[10.5px] text-[rgb(var(--text-muted))] bg-[rgb(var(--surface))]/30 border border-[rgb(var(--border))]/60 rounded-xl p-3.5 mt-3 transition-all duration-200">
                              <summary className="cursor-pointer font-bold text-[rgb(var(--text-primary))]/80 select-none hover:text-[rgb(var(--text-primary))] transition-colors flex items-center gap-1.5">
                                <span>👀</span> View Multi-Agent Traces ({msg.traces.length} steps)
                              </summary>
                              <div className="mt-3.5 space-y-3 font-mono border-l border-[rgb(var(--border))] pl-3 max-h-48 overflow-y-auto text-[10px] leading-relaxed">
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
                                        <span className="text-[9px] text-[rgb(var(--text-muted))]">
                                          ({trace.tool_name})
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-[10.5px] text-[rgb(var(--text-primary))]/80 mt-1 whitespace-pre-wrap leading-normal">{trace.content}</p>
                                    {trace.duration_ms > 0 && (
                                      <span className="text-[8.5px] text-[rgb(var(--text-muted))] mt-0.5">Duration: {trace.duration_ms.toFixed(0)}ms</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}

                          {/* Sources Citation block */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="flex items-center gap-2 flex-wrap pt-4 border-t border-[rgb(var(--border))]/40 mt-4">
                              <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] uppercase tracking-wider block mr-1 font-bold">Sources:</span>
                              {msg.sources.map((src: Source) => (
                                <span
                                  key={src.id}
                                  onClick={async () => {
                                    if (token) {
                                      await fetchDecisionGraphData(src.id);
                                      setIsGraphOpen(true);
                                    } else {
                                      const match = SIMULATED_RESPONSES.find((r) => r.keywords.some((k) => src.title.toLowerCase().includes(k)));
                                      if (match) {
                                        const edges = match.graph.slice(1).map((node) => ({
                                          source: match.graph[0].id,
                                          target: node.id
                                        }));
                                        setCurrentGraphNodes(match.graph);
                                        setCurrentGraphEdges(edges);
                                        setCurrentGraphTitle(match.question);
                                        setIsGraphOpen(true);
                                      }
                                    }
                                  }}
                                  className="inline-flex items-center gap-1.5 text-[10px] font-mono bg-[rgb(var(--surface))]/80 text-[rgb(var(--text-primary))] border border-[rgb(var(--border))]/80 px-2.5 py-1 rounded-lg hover:border-[rgb(var(--border-focus))] cursor-pointer transition-all shadow-sm"
                                  title={`${src.title}\nDate: ${src.date}\nSource: ${src.source}`}
                                >
                                  <span className="text-[9px] text-indigo-400 font-bold">{getSourceIcon(src.source)}</span>
                                  {src.title}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {isChatStreaming && chatHistory[chatHistory.length - 1]?.role !== "assistant" && (
                      <div className="flex gap-5 items-start py-5 w-full">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0">
                          <KairosLogo size={28} />
                        </div>
                        <ThinkingIndicator />
                      </div>
                    )}
                  </div>
                  <div ref={chatBottomRef} />
                </div>

                {/* Processing Toast Overlay */}
                {ingestProgress && (
                  <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-xl bg-[rgb(var(--surface))] border border-[rgb(var(--border))] text-[rgb(var(--text-primary))] text-xs font-semibold flex items-center gap-2.5 shadow-2xl z-20 theme-transition">
                    <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
                    {ingestProgress}
                  </div>
                )}

                {/* Floating Chat Input form */}
                <form onSubmit={handleSend} className="p-6 shrink-0 bg-gradient-to-t from-[rgb(var(--bg))] via-[rgb(var(--bg))]/90 to-transparent theme-transition">
                  <div className="max-w-4xl mx-auto relative bg-[rgb(var(--surface))] border border-[rgb(var(--border))] focus-within:border-[rgb(var(--border-focus))] focus-within:ring-2 focus-within:ring-[rgb(var(--accent))]/15 focus-within:shadow-[0_0_30px_-8px_rgb(var(--accent)/0.25)] rounded-[26px] shadow-xl transition-all duration-300 p-2 flex items-center">
                    <input
                      type="text"
                      value={inputVal}
                      onChange={(e) => setInputVal(e.target.value)}
                      disabled={isChatStreaming}
                      placeholder="Ask KAIROS organizational memory database..."
                      className="flex-1 bg-transparent px-5 py-3 text-sm text-[rgb(var(--text-primary))] placeholder-zinc-500 focus:outline-none disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={isChatStreaming || !inputVal.trim()}
                      className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 shrink-0 shadow active:scale-90 ${
                        inputVal.trim()
                          ? "bg-[rgb(var(--accent))] text-white hover:opacity-90 hover:scale-105 hover:shadow-[0_0_16px_-2px_rgb(var(--accent)/0.6)]"
                          : "bg-[rgb(var(--surface-hover))] text-[rgb(var(--text-muted))] opacity-40 cursor-not-allowed"
                      }`}
                    >
                      <svg className="w-4 h-4 transform rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
                      </svg>
                    </button>
                  </div>
                  <p className="text-[10px] text-[rgb(var(--text-muted))] text-center mt-2.5 font-sans">
                    KAIROS memory indices can make mistakes. Verify critical facts and historical timestamps.
                  </p>
                </form>
              </div>
 
              {/* Right Column: Obsidian Graph Panel — a full-screen overlay
                  on mobile (a fixed-pixel side column can't coexist with the
                  chat column below ~700px), a resizable flex sibling on desktop */}
              {isGraphOpen && (
                <div
                  className={`border-l border-[rgb(var(--border))]/55 flex flex-col bg-[rgb(var(--bg))] md:bg-[rgb(var(--bg))]/40 shrink-0 relative ${
                    isMobile ? "fixed inset-0 z-40 h-full" : "h-full"
                  }`}
                  style={isMobile ? undefined : {
                    width: `${graphWidth}px`,
                    transition: isResizing ? "none" : "width 0.3s ease",
                  }}
                >
                  {isMobile && (
                    <button
                      onClick={() => setIsGraphOpen(false)}
                      className="absolute top-3 left-3 z-50 p-2 bg-[rgb(var(--surface))]/90 backdrop-blur-md border border-[rgb(var(--border))]/60 rounded-xl text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] shadow-lg"
                      title="Close Graph"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                  {/* Left Resize Handle (desktop only — dragging a 1px hairline is impractical with touch) */}
                  {!isMobile && (
                  <div
                    className="w-1 cursor-col-resize hover:bg-[rgb(var(--accent))]/45 active:bg-[rgb(var(--accent))] transition-colors absolute left-0 top-0 bottom-0 z-50"
                    onMouseDown={handleResize("horizontal", setGraphWidth, 300, 800, true)}
                  />
                  )}
                  <div className="flex-1 relative overflow-hidden">
                    <DecisionGraph
                      nodes={currentGraphNodes}
                      edges={currentGraphEdges}
                      decisionTitle={currentGraphTitle}
                      onNodeClick={async (nodeId) => {
                        if (nodeId && !nodeId.includes("-person-") && !nodeId.includes("-date") && !nodeId.includes("-source") && !nodeId.includes("-outcome")) {
                          if (token) {
                            await fetchDecisionGraphData(nodeId);
                          } else {
                            const match = SIMULATED_RESPONSES.find((r) => r.graph.some((n) => n.id === nodeId));
                            if (match) {
                              const edges = match.graph.slice(1).map((node) => ({
                                source: match.graph[0].id,
                                target: node.id
                              }));
                              setCurrentGraphNodes(match.graph);
                              setCurrentGraphEdges(edges);
                              setCurrentGraphTitle(match.question);
                            }
                          }
                        }
                      }}
                    />
                  </div>
                  <div
                    className="relative shrink-0"
                    style={{
                      height: isMobile ? "35vh" : `${sourcesHeight}px`,
                    }}
                  >
                    {/* Top Height Resize Handle (desktop only) */}
                    {!isMobile && (
                    <div
                      className="h-1 cursor-row-resize hover:bg-[rgb(var(--accent))]/45 active:bg-[rgb(var(--accent))] transition-colors absolute left-0 right-0 top-0 z-50"
                      onMouseDown={handleResize("vertical", setSourcesHeight, 140, 500, true)}
                    />
                    )}
                    <div className="h-full overflow-hidden">
                      <SourcePanel sources={activeSources} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* DASHBOARD & STATS OVERVIEW */}
          {activeTab === "dashboard" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-message-in">
              <div className="border-b border-[rgb(var(--border))]/40 pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h3 className="text-lg font-bold tracking-tight text-[rgb(var(--text-primary))] mb-0.5">System Ingest Metrics</h3>
                  <p className="text-xs text-[rgb(var(--text-muted))]">Monitor indexing sizes, relations logs, and dynamic app integration statuses.</p>
                </div>
                <div className="flex items-center gap-3.5 bg-[rgb(var(--surface))]/40 border border-[rgb(var(--border))]/60 rounded-2xl px-4 py-2.5 shrink-0 self-start sm:self-auto shadow-sm">
                  <div className="flex flex-col">
                    <span className="text-[10.5px] font-bold text-[rgb(var(--text-primary))] font-mono tracking-wider uppercase">Auto-Extraction</span>
                    <span className="text-[9px] text-[rgb(var(--text-muted))]">Runs background scraper tasks</span>
                  </div>
                  <button
                    onClick={() => toggleAutoExtraction(!autoExtractionEnabled)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2 ${
                      autoExtractionEnabled ? "bg-indigo-500" : "bg-zinc-600"
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        autoExtractionEnabled ? "translate-x-4" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>

              {/* Metrics cards grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { label: "Decisions Index", value: displayStats.total_decisions, decimals: 0, tag: "records" },
                  { label: "Graph Relations", value: displayStats.total_relations, decimals: 0, tag: "links" },
                  { label: "Connected APIs", value: displayStats.connected_components, decimals: 0, tag: "active" },
                  { label: "Memory DB Size", value: dbSizeMb, decimals: 1, tag: "MB" },
                ].map((stat, idx) => (
                  <div
                    key={idx}
                    className="p-5 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/40 backdrop-blur-sm shadow-sm hover:shadow-md transition-all flex flex-col gap-1.5 animate-pop-in"
                    style={{ animationDelay: `${idx * 60}ms` }}
                  >
                    <span className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase block tracking-wider font-bold">{stat.label}</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-black text-[rgb(var(--text-primary))] tabular-nums">
                        <CountUp value={stat.value} decimals={stat.decimals} />
                      </span>
                      <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] font-bold">{stat.tag}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Decision Debt Score — pure SQL/graph aggregation, no LLM call */}
              {debtScoreLoading && !debtScore && (
                <div className="p-5 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/40 backdrop-blur-sm shadow-sm flex items-center gap-6 animate-pulse">
                  <div className="shrink-0 w-20 h-20 rounded-full bg-[rgb(var(--border))]/60" />
                  <div className="flex-1 space-y-2">
                    <div className="h-2.5 w-40 rounded bg-[rgb(var(--border))]/60" />
                    <div className="h-3.5 w-64 rounded bg-[rgb(var(--border))]/50" />
                    <div className="h-2.5 w-56 rounded bg-[rgb(var(--border))]/40" />
                  </div>
                </div>
              )}
              {debtScore && debtScore.total_decisions > 0 && (
                <div className="p-5 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/40 backdrop-blur-sm shadow-sm flex items-center gap-6">
                  <div className="relative shrink-0 w-20 h-20">
                    <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
                      <path
                        d="M18 2.5 a15.5 15.5 0 0 1 0 31 a15.5 15.5 0 0 1 0 -31"
                        fill="none"
                        stroke="rgb(var(--border))"
                        strokeWidth="3"
                      />
                      <path
                        d="M18 2.5 a15.5 15.5 0 0 1 0 31 a15.5 15.5 0 0 1 0 -31"
                        fill="none"
                        stroke={debtScore.debt_score >= 60 ? "#f43f5e" : debtScore.debt_score >= 30 ? "#f59e0b" : "#10b981"}
                        strokeWidth="3"
                        strokeDasharray={`${debtScore.debt_score}, 100`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-black text-[rgb(var(--text-primary))]">{debtScore.debt_score}</span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <span className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase block tracking-wider font-bold mb-1">
                      Decision Debt Score
                    </span>
                    <p className="text-xs text-[rgb(var(--text-primary))] leading-relaxed">
                      <strong>{debtScore.high_risk_count}</strong> high-impact decision{debtScore.high_risk_count === 1 ? "" : "s"} out of{" "}
                      <strong>{debtScore.total_decisions}</strong> total have gone 12+ months without review.
                    </p>
                    <p className="text-[10.5px] text-[rgb(var(--text-muted))] mt-1">
                      Lower is better — this is a pure count/weight of unreviewed decisions, not model-generated.
                    </p>
                  </div>
                </div>
              )}

              {/* Connected APIs */}
              <div className="space-y-4">
                <h4 className="text-sm font-bold text-[rgb(var(--text-primary))] tracking-tight">Ingestion Connectors</h4>
                <div className="grid grid-cols-1 md:grid-cols-6 gap-3.5">
                  {[
                    { key: "slack", name: "Slack", details: "Workspace API" },
                    { key: "gmail", name: "Gmail", details: "OAuth Client" },
                    { key: "drive", name: "G Drive", details: "Specs Scraper" },
                    { key: "jira", name: "JIRA Cloud", details: "REST Sync" },
                    { key: "zoom", name: "Zoom Sync", details: "Whisper audio" },
                    { key: "github", name: "GitHub", details: "PRs & Issues" },
                  ].map((plat) => (
                    <div key={plat.key} className="p-4 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/30 flex flex-col justify-between h-28 hover:border-[rgb(var(--border-focus))] transition-all">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase font-bold">{plat.key}</span>
                        <span
                          className={`w-2 h-2 rounded-full ${
                            syncStatus[plat.key] === "syncing"
                              ? "bg-amber-500 animate-pulse"
                              : syncStatus[plat.key] === "synced"
                              ? "bg-emerald-500"
                              : syncStatus[plat.key] === "error"
                              ? "bg-rose-500 animate-pulse"
                              : "bg-zinc-500/80"
                          }`}
                          title={syncStatus[plat.key] || "disconnected"}
                        />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-[rgb(var(--text-primary))] block">{plat.name}</span>
                        <span className="text-[9.5px] text-[rgb(var(--text-muted))] block mt-0.5">{plat.details}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* logs terminal box */}
              <div className="space-y-3.5">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-bold text-[rgb(var(--text-primary))] tracking-tight">Ingestion Container Logs</h4>
                  <span className="text-[9px] font-mono bg-[rgb(var(--bg))] text-emerald-400 px-2 py-0.5 rounded-lg border border-[rgb(var(--border))] font-bold">
                    SYSTEM: OK
                  </span>
                </div>
                <div className="bg-[rgb(var(--bg))] rounded-2xl border border-[rgb(var(--border))]/80 p-5 h-44 font-mono text-[10px] text-emerald-500 overflow-y-auto shadow-inner flex flex-col gap-1.5">
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
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-message-in">
              <div className="border-b border-[rgb(var(--border))]/40 pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h3 className="text-lg font-bold tracking-tight text-[rgb(var(--text-primary))] mb-0.5">Decision Records Index</h3>
                  <p className="text-xs text-[rgb(var(--text-muted))] font-medium">Export and browse through historically captured corporate decision points.</p>
                </div>

                <div className="flex gap-2 items-center flex-wrap">
                  <button
                    onClick={exportDecisionIndex}
                    className="px-3.5 py-1.5 rounded-xl bg-[rgb(var(--surface))] border border-[rgb(var(--border))]/80 hover:bg-[rgb(var(--surface-hover))] text-[10px] font-mono font-bold tracking-wider text-[rgb(var(--text-primary))] flex items-center gap-2 transition-all shadow-sm"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    EXPORT JSON
                  </button>

                  <button
                    onClick={exportDecisionPDF}
                    className="px-3.5 py-1.5 rounded-xl bg-[rgb(var(--surface))] border border-[rgb(var(--border))]/80 hover:bg-[rgb(var(--surface-hover))] text-[10px] font-mono font-bold tracking-wider text-[rgb(var(--text-primary))] flex items-center gap-2 transition-all shadow-sm"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    EXPORT PDF
                  </button>

                  <div className="flex gap-1 overflow-x-auto max-w-xs md:max-w-none">
                    {["all", "slack", "email", "drive", "jira", "meeting", "github"].map((src) => (
                      <button
                        key={src}
                        onClick={() => setSelectedSourceFilter(src)}
                        className={`px-2.5 py-1 rounded-lg text-[9.5px] font-mono uppercase tracking-wider border transition-all ${
                          selectedSourceFilter === src ? "bg-[rgb(var(--surface-hover))] text-[rgb(var(--text-primary))] border-[rgb(var(--border-focus))]" : "bg-transparent text-[rgb(var(--text-muted))] border-[rgb(var(--border))]/80 hover:text-[rgb(var(--text-primary))]"
                        }`}
                      >
                        {src}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Search bar */}
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search index database..."
                  className="w-full bg-[rgb(var(--surface))] border border-[rgb(var(--border))]/85 rounded-xl pl-9 pr-4 py-2.5 text-xs text-[rgb(var(--text-primary))] focus:outline-none focus:border-[rgb(var(--border-focus))] placeholder-zinc-500 transition-colors"
                />
                <svg className="w-4 h-4 text-[rgb(var(--text-muted))] absolute left-3 top-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>

              {/* List cards */}
              <div className="flex flex-col gap-4">
                {filteredDecisions.length === 0 ? (
                  <div className="p-10 text-center border border-dashed border-[rgb(var(--border))]/80 rounded-2xl text-[rgb(var(--text-muted))] text-xs">
                    No results found matching filters.
                  </div>
                ) : (
                  filteredDecisions.map((dec, i) => (
                    <div
                      key={dec.id}
                      className="p-5 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/20 hover:bg-[rgb(var(--surface-hover))]/20 transition-all shadow-sm animate-pop-in"
                      style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
                    >
                      <div className="flex items-center justify-between text-[10.5px] text-[rgb(var(--text-muted))] mb-3.5 font-mono">
                        <span className="uppercase font-bold">{dec.source} | {dec.date}</span>
                        <span className="font-semibold">{dec.owner}</span>
                      </div>
                      <h4 className="text-sm font-bold text-[rgb(var(--text-primary))] mb-1.5">{dec.title}</h4>
                      <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed mb-4">{dec.context}</p>
                      <button
                        onClick={async () => {
                          if (token) {
                            await fetchDecisionGraphData(dec.id);
                            setIsGraphOpen(true);
                            setActiveTab("chat");
                          } else {
                            const match = SIMULATED_RESPONSES.find((r) => r.keywords.some((k) => dec.title.toLowerCase().includes(k)));
                            if (match) {
                              const edges = match.graph.slice(1).map((node) => ({
                                source: match.graph[0].id,
                                target: node.id
                              }));
                              setCurrentGraphNodes(match.graph);
                              setCurrentGraphEdges(edges);
                              setCurrentGraphTitle(match.question);
                              setActiveTab("chat");
                            }
                          }
                        }}
                        className="text-[10px] font-mono font-bold text-[rgb(var(--accent))] hover:text-indigo-400 transition-colors tracking-wider"
                      >
                        [INSPECT NETWORK GRAPH]
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* INTEGRATIONS OAuth */}
          {activeTab === "integrations" && (
            <div className="p-8 max-w-2xl mx-auto flex flex-col gap-6 animate-message-in">
              <div className="border-b border-[rgb(var(--border))]/40 pb-4">
                <h3 className="text-lg font-bold tracking-tight text-[rgb(var(--text-primary))] mb-0.5">
                  Connect Your Apps
                </h3>
                <p className="text-xs text-[rgb(var(--text-muted))]">
                  One-click OAuth authentication. Connect platforms to dynamically sync corporate memory.
                </p>
              </div>

              <IntegrationGrid token={token} />

              {/* How it works card */}
              <div className="p-5 rounded-2xl border border-indigo-500/15 bg-indigo-500/5 text-[11.5px] text-[rgb(var(--text-muted))] space-y-2">
                <p className="text-[10px] font-mono text-indigo-400 font-bold uppercase tracking-wider mb-2.5">Workflow Sync Integration</p>
                {[
                  "Trigger apps oauth connection flow popup.",
                  "Approve requested read scopes for the organization workspace.",
                  "Tokens are encrypted and saved securely inside credentials.",
                  "KAIROS index agents start scrapes automatically.",
                ].map((step, i) => (
                  <div key={i} className="flex gap-2.5 leading-relaxed">
                    <span className="text-[rgb(var(--accent))] font-bold font-mono">{i + 1}.</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>

              {/* Data permissions card */}
              <div className="p-5 rounded-2xl border border-purple-500/15 bg-purple-500/5 text-[11.5px] text-[rgb(var(--text-muted))] space-y-2.5">
                <p className="text-[10px] font-mono text-purple-400 font-bold uppercase tracking-wider mb-2.5">Read-Only Safety Guarantee</p>
                {[
                  ["💬 Slack Integration", "Filters channels for decision threads. Never posts text messages."],
                  ["📧 Gmail Connector", "Retrieves approval signatures. Never checks external attachments."],
                  ["📄 G Drive Scrape", "Scans text spec changes. Never edits or deletes folders."],
                  ["🎯 Jira Boards", "Indices ticket issues and comments. Never executes updates."],
                  ["📹 Zoom Transcription", "Whisper large transcription indexes. Never accesses live meetings."],
                ].map(([label, desc]) => (
                  <div key={label} className="flex gap-2 leading-relaxed">
                    <span className="text-purple-300 font-bold w-36 shrink-0">{label}</span>
                    <span>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI AGENTS REGISTRY */}
          {activeTab === "agents" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-6 animate-message-in">
              <div className="border-b border-[rgb(var(--border))]/40 pb-4 flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-lg font-bold tracking-tight text-[rgb(var(--text-primary))] mb-0.5">Agent Registry</h3>
                  <p className="text-xs text-[rgb(var(--text-muted))]">Monitor parallel models execution, processing metrics, and active states.</p>
                </div>
                <button
                  onClick={() => router.push("/settings/agents")}
                  className="shrink-0 text-[10px] font-mono px-3 py-1.5 rounded-lg border border-[rgb(var(--border))] text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:border-[rgb(var(--border-focus))] transition-colors"
                >
                  Customize names & tone →
                </button>
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
                  },
                  {
                    name: "notion_agent",
                    label: "Notion Extraction Agent",
                    status: syncStatus.notion === "syncing" ? "processing" : "idle",
                    description: "Walks Notion pages and databases recursively, extracting decisions logged in specs and wikis.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "🗂️",
                    metrics: [
                      { label: "Decisions", value: "22" },
                      { label: "Reliability", value: "95.6%" },
                      { label: "Execution Cache", value: "90%" }
                    ]
                  },
                  {
                    name: "live_data_agent",
                    label: "Live Agent",
                    status: isChatStreaming ? "processing" : "idle",
                    description: "Skips stored memory entirely for on-demand questions — \"how many unread emails do I have?\" — answered straight from your connected accounts.",
                    model: "Llama 3.3 70B (Groq Cloud)",
                    hardware: "Groq LPU Accelerator",
                    icon: "⚡",
                    metrics: [
                      { label: "Live Queries", value: "36" },
                      { label: "Avg Latency", value: "640ms" },
                      { label: "Sources Hit", value: "4.1 avg" }
                    ]
                  },
                  {
                    name: "synthesis_agent",
                    label: "Decision Synthesis Hub",
                    status: isChatStreaming ? "processing" : "idle",
                    description: "Acts as the orchestration layer for the multi-agent memory network. Evaluates context variables, queries SQLite graph relational index, runs ChromaDB hybrid semantic search, and compiles real-time citation stream responses.",
                    model: "Qwen 2.5 72B Instruct",
                    hardware: "AMD Instinct GPU (Fireworks Cloud)",
                    icon: "🧠",
                    metrics: [
                      { label: "Total Queries", value: "142" },
                      { label: "Avg Response", value: "1.2s" },
                      { label: "Cache Hit", value: "84.1%" }
                    ]
                  }
                ].map((agent, i) => (
                  <div
                    key={agent.name}
                    className="p-5 rounded-2xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/30 flex flex-col justify-between gap-5 hover:border-[rgb(var(--border-focus))] transition-all shadow-sm animate-pop-in"
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">{agent.icon}</span>
                          <span className="text-xs font-bold text-[rgb(var(--text-primary))]">{agentPersonas[agent.name] || agent.label}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${agent.status === "processing" ? "bg-amber-500 animate-ping" : "bg-emerald-500"}`} />
                          <span className="text-[9px] font-mono font-bold tracking-wider uppercase text-[rgb(var(--text-muted))]">
                            {agent.status === "processing"
                              ? (["intent_agent", "context_agent", "research_agent", "live_data_agent", "synthesis_agent"].includes(agent.name) ? "QUERYING" : "SYNCING")
                              : "IDLE"
                            }
                          </span>
                        </div>
                      </div>
                      <p className="text-[11.5px] text-[rgb(var(--text-muted))] leading-relaxed mb-3.5">{agent.description}</p>
                      
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-[rgb(var(--text-muted))]">Model:</span>
                          <span className="text-[rgb(var(--text-primary))] font-bold">{agent.model}</span>
                        </div>
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-[rgb(var(--text-muted))]">Hardware:</span>
                          <span className="text-[rgb(var(--text-primary))]">{agent.hardware}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2.5 pt-3.5 border-t border-[rgb(var(--border))]/40">
                      {agent.metrics.map((m, idx) => (
                        <div key={idx} className="text-center">
                          <span className="text-[9px] font-mono text-[rgb(var(--text-muted))] uppercase block font-bold tracking-wider">{m.label}</span>
                          <span className="text-[11px] font-bold text-[rgb(var(--text-primary))] font-mono">{m.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* MCP SERVER INTERFACE */}
          {activeTab === "mcp" && (
            <div className="p-8 max-w-4xl mx-auto flex flex-col gap-8 animate-message-in">
              
              {/* Header */}
              <div className="border-b border-[rgb(var(--border))]/40 pb-4">
                <h3 className="text-lg font-bold tracking-tight text-[rgb(var(--text-primary))] mb-1 flex items-center gap-2">
                  <span>🔌</span> Connect Your AI Assistants
                </h3>
                <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
                  Sync KAIROS memory directly to your favorite AI Assistant (like Claude, ChatGPT, or Antigravity) so it has access to your company's full decision history.
                </p>
              </div>

              {/* Status and AI Link Card */}
              <div className="p-6 rounded-2xl border border-[rgb(var(--border))]/70 bg-[rgb(var(--surface))]/10 flex flex-col justify-between gap-4 shadow-lg shadow-black/20">
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🔒</span>
                      <h4 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider">Personal AI Link</h4>
                    </div>
                    <span className="flex items-center gap-1.5 text-[9px] font-mono px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold uppercase tracking-wider">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                      </span>
                      Sync Active
                    </span>
                  </div>

                  <p className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">
                    Use this unique URL to connect remote clients. Keep it secret to protect your company's memory space.
                  </p>

                  {/* Personal MCP URL + copy */}
                  <div className="flex items-stretch gap-2 bg-[rgb(var(--bg))]/80 border border-[rgb(var(--border))]/80 rounded-xl p-1 mt-1">
                    <div className="flex-1 px-2.5 py-2 font-mono text-[10px] text-[rgb(var(--text-muted))] overflow-x-auto whitespace-nowrap scrollbar-none flex items-center select-all">
                      {mcpConnectionError
                        ? "Couldn't load — see below"
                        : mcpConnection?.url || "Generating connection URL…"}
                    </div>
                    <button
                      disabled={!mcpConnection?.url}
                      onClick={() => copyToClipboard(mcpConnection.url, "url")}
                      className="shrink-0 px-3 py-1.5 rounded-lg bg-[rgb(var(--accent))] text-white text-[9.5px] font-bold tracking-wider hover:opacity-90 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed uppercase"
                    >
                      {copiedKey === "url" ? "✓" : "Copy"}
                    </button>
                  </div>
                  {mcpConnectionError && (
                    <div className="flex items-center justify-between gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 mt-1">
                      <p className="text-[10px] text-rose-300 font-mono">Couldn&apos;t reach the server to load your MCP connection.</p>
                      <button
                        onClick={fetchMcpConnection}
                        className="text-[10px] font-semibold text-rose-300 hover:text-rose-200 underline shrink-0"
                      >
                        Retry
                      </button>
                    </div>
                  )}
                </div>

                {/* Badges (Horizontal Layout) */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 border-t border-[rgb(var(--border))]/40 pt-3.5 mt-1">
                  {[
                    { text: "100% Secure & Scoped", icon: "🛡️" },
                    { text: user?.displayName ? `${user.displayName}'s Workspace` : "Your Workspace", icon: "🏢" },
                    { text: "Real-time Two-way Sync", icon: "⚡" }
                  ].map((badge, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-[10px] text-[rgb(var(--text-muted))]">
                      <span className="text-xs shrink-0">{badge.icon}</span>
                      <span className="font-mono">{badge.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Onboarding Wizard / Platform Tabs */}
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[rgb(var(--border))]/30 pb-2">
                  <h4 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider">Choose your Assistant</h4>
                  <span className="text-[10px] text-[rgb(var(--text-muted))] font-mono">Select a platform below to see step-by-step setup</span>
                </div>

                {/* Tabs */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {[
                    { id: "claude", name: "Claude AI", color: "hover:border-amber-500/30 active:border-amber-500/50", activeColor: "border-amber-500/50 bg-amber-500/5 text-amber-300", logo: McpLogos.claude, logoColor: "text-amber-500/80" },
                    { id: "chatgpt", name: "ChatGPT", color: "hover:border-emerald-500/30 active:border-emerald-500/50", activeColor: "border-emerald-500/50 bg-emerald-500/5 text-emerald-300", logo: McpLogos.chatgpt, logoColor: "text-emerald-500/80" },
                    { id: "cursor", name: "Cursor IDE", color: "hover:border-sky-500/30 active:border-sky-500/50", activeColor: "border-sky-500/50 bg-sky-500/5 text-sky-300", logo: McpLogos.cursor, logoColor: "text-sky-400/80" },
                    { id: "antigravity", name: "Antigravity", color: "hover:border-violet-500/30 active:border-violet-500/50", activeColor: "border-violet-500/50 bg-violet-500/5 text-violet-300", logo: McpLogos.antigravity, logoColor: "text-violet-400/80" }
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setMcpPlatform(tab.id as any)}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border transition-all text-center gap-1.5 ${
                        mcpPlatform === tab.id
                          ? tab.activeColor
                          : `border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 text-[rgb(var(--text-muted))] ${tab.color}`
                      }`}
                    >
                      <span className={`text-base ${tab.logoColor}`}>{tab.logo}</span>
                      <span className="text-xs font-semibold tracking-wide">{tab.name}</span>
                    </button>
                  ))}
                </div>

                {/* Step contents */}
                <div className="p-6 rounded-2xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 min-h-[160px] flex flex-col justify-center animate-[fadeIn_0.15s_ease-out]">
                  {mcpPlatform === "claude" && (
                    <div className="flex flex-col gap-4">
                      <h5 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider flex items-center gap-1.5">
                        <span className="text-amber-500 shrink-0">{McpLogos.claude}</span> Claude Web / Mobile Integration
                      </h5>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                        {[
                          { step: "1️⃣", title: "Copy Your URL", desc: "Click the 'Copy Link' button on your personal card above." },
                          { step: "2️⃣", title: "Open Settings", desc: "Go to your Claude account settings and click on 'Connectors'." },
                          { step: "3️⃣", title: "Paste & Connect", desc: "Add a custom connector, paste your URL, and click save. Done!" }
                        ].map((s, idx) => (
                          <div key={idx} className="flex flex-col gap-1.5 p-3 rounded-xl bg-[rgb(var(--surface-hover))]/40 border border-[rgb(var(--border))]/60">
                            <span className="font-bold text-sm text-[rgb(var(--text-primary))]/85">{s.step} {s.title}</span>
                            <span className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">{s.desc}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {mcpPlatform === "chatgpt" && (
                    <div className="flex flex-col gap-4">
                      <h5 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider flex items-center gap-1.5">
                        <span className="text-emerald-500 shrink-0">{McpLogos.chatgpt}</span> ChatGPT Integration
                      </h5>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                        {[
                          { step: "1️⃣", title: "Copy Your URL", desc: "Click the 'Copy Link' button on your personal card above." },
                          { step: "2️⃣", title: "Enable Dev mode", desc: "In ChatGPT settings under 'Connectors', toggle developer mode on." },
                          { step: "3️⃣", title: "Paste URL", desc: "Click 'Add custom connector', paste your link, and register. Done!" }
                        ].map((s, idx) => (
                          <div key={idx} className="flex flex-col gap-1.5 p-3 rounded-xl bg-[rgb(var(--surface-hover))]/40 border border-[rgb(var(--border))]/60">
                            <span className="font-bold text-sm text-[rgb(var(--text-primary))]/85">{s.step} {s.title}</span>
                            <span className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">{s.desc}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {mcpPlatform === "cursor" && (
                    <div className="flex flex-col gap-4">
                      <h5 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider flex items-center gap-1.5">
                        <span className="text-sky-400 shrink-0">{McpLogos.cursor}</span> Cursor & IDE Desktop Integration
                      </h5>
                      <p className="text-[11.5px] text-[rgb(var(--text-muted))] leading-relaxed">
                        Cursor and Claude Desktop require a local JSON server configuration or command line tool. Follow these simple steps:
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                        <div className="flex flex-col gap-2 p-3 rounded-xl bg-[rgb(var(--surface-hover))]/40 border border-[rgb(var(--border))]/60">
                          <span className="font-bold text-[rgb(var(--text-primary))]/85">Option A: Cursor (Simple UI setup)</span>
                          <span className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">
                            1. Open Cursor Settings → Features → MCP.<br />
                            2. Click "+ Add New MCP Server".<br />
                            3. Enter name: <code className="text-violet-400 font-mono">kairos</code>, type: <code className="text-violet-400 font-mono">command</code>.<br />
                            4. Click the "Advanced Developer Settings" toggle below and copy the command to paste.
                          </span>
                        </div>
                        <div className="flex flex-col gap-2 p-3 rounded-xl bg-[rgb(var(--surface-hover))]/40 border border-[rgb(var(--border))]/60">
                          <span className="font-bold text-[rgb(var(--text-primary))]/85">Option B: Claude Desktop Config</span>
                          <span className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">
                            1. Open the Developer options section below.<br />
                            2. Copy the pre-generated JSON configuration.<br />
                            3. Paste it directly into your local <code className="text-violet-400 font-mono">claude_desktop_config.json</code> file.
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {mcpPlatform === "antigravity" && (
                    <div className="flex flex-col gap-4">
                      <h5 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider flex items-center gap-1.5">
                        <span className="text-violet-400 shrink-0">{McpLogos.antigravity}</span> Antigravity IDE Integration
                      </h5>
                      <p className="text-[11.5px] text-[rgb(var(--text-muted))] leading-relaxed">
                        Antigravity IDE connects automatically to local and remote MCP hosts to extend its capabilities.
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                        {[
                          { step: "1️⃣", title: "Automatic Setup", desc: "If running in the Antigravity Sandbox, connection parameters are auto-provisioned." },
                          { step: "2️⃣", title: "Direct Commands", desc: "Use the built-in MCP server in CLI mode. Run: 'python mcp_server.py --stdio'." },
                          { step: "3️⃣", title: "Verify Actions", desc: "Type a prompt in the chat box or use tools to query/write context in real-time." }
                        ].map((s, idx) => (
                          <div key={idx} className="flex flex-col gap-1.5 p-3 rounded-xl bg-[rgb(var(--surface-hover))]/40 border border-[rgb(var(--border))]/60">
                            <span className="font-bold text-sm text-[rgb(var(--text-primary))]/85">{s.step} {s.title}</span>
                            <span className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed">{s.desc}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Exposed Tools Registry (Visible by Default) */}
              <div className="flex flex-col gap-5 border-t border-[rgb(var(--border))]/40 pt-6">
                <div className="flex items-center gap-2">
                  <span>🛠️</span>
                  <h4 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider">Exposed MCP Tools Registry</h4>
                </div>
                <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
                  These 8 tools are registered and exposed by the KAIROS MCP server. Once connected, your AI assistant can invoke them dynamically — memory tools read/write your decision history, control tools act on the app itself.
                </p>

                <div className="flex flex-col gap-2">
                  <span className="text-[9px] font-bold text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">Memory Tools</span>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { name: "get_context", sig: "(query)", desc: "Retrieves top decisions with full context, participants, and outcomes using vector search." },
                      { name: "store_context", sig: "(decision, ...)", desc: "Directly inserts a decision from chat into KAIROS, auto-linking related nodes." },
                      { name: "search_decisions", sig: "(topic, ...)", desc: "Structured search across metadata indices by date, project, or person." },
                      { name: "find_similar_decisions", sig: "(query, limit)", desc: "Checks whether a new situation has genuine precedent in past decisions." },
                      { name: "detect_decision_patterns", sig: "(scope, ...)", desc: "Proactively scans for contradictions, unreviewed vendor spend, and bus-factor risk." },
                      { name: "predict_decision_risk", sig: "(decision_id, scope)", desc: "Scores decisions by risk of being stale, unowned, or overdue for review." },
                    ].map((t) => (
                      <div key={t.name} className="p-4 rounded-xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 flex flex-col gap-2">
                        <div className="font-mono text-[11px]">
                          <span className="text-violet-400 font-bold">{t.name}</span>
                          <span className="text-[rgb(var(--text-muted))]">{t.sig}</span>
                        </div>
                        <p className="text-[10.5px] text-[rgb(var(--text-muted))] leading-relaxed">{t.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <span className="text-[9px] font-bold text-amber-400/90 uppercase tracking-widest font-mono flex items-center gap-1.5">
                    <span>⚡</span> Control Tools — act on the app, not just memory
                  </span>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { name: "ask_kairos", sig: "(question)", desc: "Runs the full chat pipeline (intent → retrieval → live lookups → synthesis) and returns a sourced answer, same as the chat UI." },
                      { name: "trigger_ingestion", sig: "()", desc: "Syncs connected sources on demand instead of waiting for the 12-minute cycle. Real side effects — rate-limited to once every 3 minutes." },
                    ].map((t) => (
                      <div key={t.name} className="p-4 rounded-xl border border-amber-500/25 bg-amber-500/5 flex flex-col gap-2">
                        <div className="font-mono text-[11px]">
                          <span className="text-amber-400 font-bold">{t.name}</span>
                          <span className="text-[rgb(var(--text-muted))]">{t.sig}</span>
                        </div>
                        <p className="text-[10.5px] text-[rgb(var(--text-muted))] leading-relaxed">{t.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Activity Monitor — real tool-call telemetry from core/mcp_telemetry.py,
                  polled via fetchMcpActivity() above. Every call on both transports
                  (mcp_server.py stdio tools, api/routes/mcp_remote.py's tools/call)
                  writes here; nothing on this panel is fabricated. */}
              <div className="flex flex-col gap-4 border-t border-[rgb(var(--border))]/40 pt-6">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span>📡</span>
                    <h4 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider">Activity Monitor</h4>
                  </div>
                  <span className="flex items-center gap-1.5 text-[9px] font-mono text-[rgb(var(--text-muted))]">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                    </span>
                    Live — refreshes every 8s
                  </span>
                </div>
                <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
                  Real tool calls made by your connected AI assistants, across both the local (stdio) and remote (OAuth) MCP transports.
                </p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Total Requests", value: mcpStats.totalRequests },
                    { label: "Read Ops", value: mcpStats.readOps },
                    { label: "Write Ops", value: mcpStats.writeOps },
                    { label: "Active Clients", value: mcpStats.activeClients },
                  ].map((s) => (
                    <div key={s.label} className="p-3.5 rounded-xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 flex flex-col gap-1">
                      <span className="text-lg font-bold text-[rgb(var(--text-primary))] font-mono"><CountUp value={s.value} /></span>
                      <span className="text-[9px] text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">{s.label}</span>
                    </div>
                  ))}
                </div>

                <div className="rounded-xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 overflow-hidden">
                  {mcpLogs.length === 0 ? (
                    <div className="p-6 text-center text-[11px] text-[rgb(var(--text-muted))] font-mono">
                      No MCP tool calls yet — connect an assistant above and ask it something.
                    </div>
                  ) : (
                    <div className="divide-y divide-[rgb(var(--border))]/40 max-h-80 overflow-y-auto">
                      {mcpLogs.map((log) => (
                        <div key={log.id} className="flex items-center gap-3 px-4 py-2.5 text-[11px]">
                          <span className="shrink-0 w-5 h-5 flex items-center justify-center text-[rgb(var(--text-muted))]">
                            {(McpLogos as Record<string, React.ReactNode>)[log.logo] || <span className="text-sm">🔌</span>}
                          </span>
                          <span className="font-mono text-[rgb(var(--text-primary))]/85 font-semibold shrink-0">{log.client}</span>
                          <span className="font-mono text-violet-400 truncate">{log.tool}</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-[rgb(var(--surface-hover))]/60 text-[rgb(var(--text-muted))] font-mono uppercase shrink-0">{log.transport}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-md font-mono uppercase shrink-0 ${log.status === "success" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                            {log.status}
                          </span>
                          <span className="ml-auto text-[10px] text-[rgb(var(--text-muted))] font-mono shrink-0">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Collapsible Advanced / Developer Section */}
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => setShowMcpAdvanced(!showMcpAdvanced)}
                  className="w-full flex items-center justify-between p-4 rounded-xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 hover:bg-[rgb(var(--surface))]/20 hover:border-[rgb(var(--border-focus))]/30 transition-all font-mono text-[10.5px] uppercase tracking-wider font-bold text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                >
                  <span className="flex items-center gap-2">
                    <span>⚙️</span>
                    <span>Developer Configs & Ports (CLI/Desktop)</span>
                  </span>
                  <span className={`transform transition-transform duration-200 ${showMcpAdvanced ? 'rotate-180' : ''}`}>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </span>
                </button>

                {showMcpAdvanced && (
                  <div className="flex flex-col gap-6 p-6 rounded-2xl border border-[rgb(var(--border))]/60 bg-[rgb(var(--surface))]/10 animate-message-in">
                    
                    {/* Intro & Status Card */}
                    <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-4 border-b border-[rgb(var(--border))]/40">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-lg">🔌</span>
                          <h5 className="text-xs font-bold text-[rgb(var(--text-primary))] font-mono uppercase tracking-wider">Two-way LLM Brain Integration</h5>
                        </div>
                        <p className="text-[11px] text-[rgb(var(--text-muted))] leading-relaxed max-w-2xl">
                          MCP allows LLMs to query KAIROS memory before answering questions, and store new decisions back into the graph in real-time — plus act on the app itself via control tools (ask_kairos, trigger_ingestion). This creates a unified knowledge loop.
                        </p>
                      </div>
                      <div className="shrink-0 w-full md:w-auto">
                        <span className="flex items-center justify-center gap-1.5 text-[9px] font-mono px-3 py-1.5 rounded-lg bg-[rgb(var(--surface-hover))]/80 border border-[rgb(var(--border))]/70 text-emerald-400 font-bold shadow-sm select-none">
                          MCP PORT: 8002 / STDIO
                        </span>
                      </div>
                    </div>

                    {/* Stdio / SSE Modes */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/20 flex flex-col gap-3">
                        <div>
                           <h5 className="text-[11px] font-bold text-[rgb(var(--text-primary))] mb-1 flex items-center gap-1.5 font-mono uppercase">
                            <span className="w-1.5 h-1.5 rounded-full bg-[rgb(var(--accent))]" />
                            1. Stdio Mode (Recommended)
                          </h5>
                          <p className="text-[10.5px] text-[rgb(var(--text-muted))] leading-relaxed">
                            Best for local IDE integrations where the editor manages the server process via standard I/O.
                          </p>
                        </div>
                        <pre className="bg-[rgb(var(--bg))]/75 border border-[rgb(var(--border))] rounded-xl p-3 font-mono text-[9.5px] text-[rgb(var(--text-primary))]/85 overflow-x-auto select-all">
                          python mcp_server.py --stdio
                        </pre>
                      </div>

                      <div className="p-4 rounded-xl border border-[rgb(var(--border))]/80 bg-[rgb(var(--surface))]/20 flex flex-col gap-3">
                        <div>
                          <h5 className="text-[11px] font-bold text-[rgb(var(--text-primary))] mb-1 flex items-center gap-1.5 font-mono uppercase">
                            <span className="w-1.5 h-1.5 rounded-full bg-[rgb(var(--accent))]" />
                            2. SSE Server Mode
                          </h5>
                          <p className="text-[10.5px] text-[rgb(var(--text-muted))] leading-relaxed">
                            Runs a persistent HTTP event stream on port 8002. Useful for remote setups or webhooks.
                          </p>
                        </div>
                        <pre className="bg-[rgb(var(--bg))]/75 border border-[rgb(var(--border))] rounded-xl p-3 font-mono text-[9.5px] text-[rgb(var(--text-primary))]/85 overflow-x-auto select-all">
                          python mcp_server.py
                        </pre>
                      </div>
                    </div>

                    {/* Editor Configurations */}
                    <div className="flex flex-col gap-4 border-t border-[rgb(var(--border))]/40 pt-4">
                      {/* Claude Desktop */}
                      <div className="flex flex-col gap-2">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-semibold text-[rgb(var(--text-primary))]">Claude Desktop Settings</span>
                          <button
                            disabled={!mcpConnection?.claude_desktop_config}
                            onClick={() => copyToClipboard(JSON.stringify(mcpConnection.claude_desktop_config, null, 2), "config")}
                            className="text-[9px] font-mono font-bold text-[rgb(var(--accent))] hover:underline disabled:opacity-40"
                          >
                            {copiedKey === "config" ? "✓ COPIED" : "COPY JSON"}
                          </button>
                        </div>
                        <pre className="bg-[rgb(var(--bg))] border border-[rgb(var(--border))] rounded-xl p-4 font-mono text-[10px] text-emerald-400 overflow-x-auto select-all leading-relaxed whitespace-pre">
{mcpConnection?.claude_desktop_config
  ? JSON.stringify(mcpConnection.claude_desktop_config, null, 2)
  : `{
  "mcpServers": {
    "kairos": {
      "command": "python3",
      "args": [
        "/path/to/your/kairos/mcp_server.py",
        "--stdio"
      ],
      "env": {
        "MCP_TENANT_ID": "${user?.uid || "mcp-system"}"
      }
    }
  }
}`}
                        </pre>
                      </div>

                      {/* Cursor CLI command details */}
                      <div className="flex flex-col gap-2">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-semibold text-[rgb(var(--text-primary))]">Cursor Command Line Setup</span>
                          <button
                            onClick={() => copyToClipboard(`python3 /path/to/your/kairos/mcp_server.py --stdio`, "cursor-cmd")}
                            className="text-[9px] font-mono font-bold text-[rgb(var(--accent))] hover:underline"
                          >
                            {copiedKey === "cursor-cmd" ? "✓ COPIED" : "COPY COMMAND"}
                          </button>
                        </div>
                        <div className="bg-[rgb(var(--bg))] border border-[rgb(var(--border))] p-4 rounded-xl font-mono text-[10px] text-emerald-400 overflow-x-auto select-all whitespace-pre">
{`command: python3
args: /path/to/your/kairos/mcp_server.py --stdio
env: MCP_TENANT_ID=${user?.uid || "mcp-system"}`}
                        </div>
                      </div>
                    </div>

                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
