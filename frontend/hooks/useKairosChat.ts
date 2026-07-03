"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { wsClient } from "@/lib/websocket";

export interface Source {
  id: string;
  title: string;
  date: string;
  source: "slack" | "email" | "drive" | "jira" | "meeting" | string;
  source_url: string;
}

export interface TraceStep {
  type: "think" | "act" | "observe" | "reflect" | "error" | "result";
  content: string;
  timestamp: number;
  duration_ms: number;
  tool_name?: string;
  tool_input?: string;
  metadata?: Record<string, any>;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  sources: Source[];
  hasWarning: boolean;
  intent?: {
    intent: string;
    confidence?: number;
    search_strategy?: string;
    entities?: Record<string, any>;
    rewritten_query?: string;
  };
  confidence?: number;
  traces?: TraceStep[];
  session_id?: string;
  user_context?: Record<string, any>;
  thinkingStep?: {
    agent: string;
    content: string;
  };
}

export interface KairosStats {
  total_decisions: number;
  total_relations: number;
  connected_components: number;
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 11);
}

export function useKairosChat(token: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  // The socket is a singleton that survives route changes — a remounting page
  // must start from its real state, not assume "disconnected".
  const [isConnected, setIsConnected] = useState(() => wsClient.isConnected());
  const [isReconnectExhausted, setIsReconnectExhausted] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [stats, setStats] = useState<KairosStats | null>(null);
  const [ingestProgress, setIngestProgress] = useState<string | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [userProfile, setUserProfile] = useState<any>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(undefined);
  const currentAssistantId = useRef<string | null>(null);

  // Fetch session history & profile
  const fetchSessions = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/memory/sessions", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error("Error fetching sessions", e);
    }
  }, [token]);

  const fetchUserProfile = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/memory/profile", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setUserProfile(data);
    } catch (e) {
      console.error("Error fetching user profile", e);
    }
  }, [token]);

  const loadSession = useCallback(async (sessionId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`/api/memory/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const turns = await res.json();
      if (!res.ok || !Array.isArray(turns)) return;
      const loadedMessages: Message[] = turns.map((turn: any) => ({
        id: turn.id,
        role: turn.role,
        content: turn.content ?? "",
        isStreaming: false,
        sources: turn.metadata?.sources ?? [],
        hasWarning: (turn.content || "").includes("WARNING") || (turn.content || "").includes("ALERT"),
        intent: turn.query_intent ? { intent: turn.query_intent } : undefined,
        confidence: turn.metadata?.confidence
      }));
      setMessages(loadedMessages);
      setActiveSessionId(sessionId);
    } catch (e) {
      console.error("Error loading session", e);
    }
  }, [token]);

  const deleteSession = useCallback(async (sessionId: string) => {
    if (!token) return;
    try {
      await fetch(`/api/memory/sessions/${sessionId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      await fetchSessions();
    } catch (e) {
      console.error("Error deleting session", e);
    }
  }, [token, fetchSessions]);

  const resetProfile = useCallback(async () => {
    if (!token) return;
    try {
      await fetch("/api/memory/profile/reset", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      await fetchUserProfile();
    } catch (e) {
      console.error("Error resetting profile", e);
    }
  }, [token, fetchUserProfile]);

  // Fetch initial profile & sessions on token change
  useEffect(() => {
    if (token) {
      fetchSessions();
      fetchUserProfile();
    } else {
      setMessages([]);
      setSessions([]);
      setUserProfile(null);
      setStats(null);
      setIngestProgress(null);
      setActiveSessionId(undefined);
    }
  }, [token, fetchSessions, fetchUserProfile]);

  // Bootstrap WebSocket listeners once
  useEffect(() => {
    if (!token) {
      wsClient.disconnect();
      setIsConnected(false);
      return;
    }

    wsClient.connect(token);

    // If the singleton was already open (returning to this page), there's no
    // "connection" event coming — sync state and fetch stats immediately.
    if (wsClient.isConnected()) {
      setIsConnected(true);
      wsClient.send({ type: "stats" });
    }

    const unsubConnection = wsClient.on(
      "connection",
      (data: unknown) => {
        const d = data as { connected: boolean; exhausted?: boolean };
        setIsConnected(d.connected);
        if (d.connected) {
          setIsReconnectExhausted(false);
          // Request stats on connect
          wsClient.send({ type: "stats" });
        } else if (d.exhausted) {
          setIsReconnectExhausted(true);
        }
      }
    );

    const unsubStart = wsClient.on("start", (data: unknown) => {
      const d = data as { question: string };
      const id = generateId();
      currentAssistantId.current = id;
      setIsStreaming(true);
      setMessages((prev) => [
        ...prev,
        {
          id,
          role: "assistant",
          content: "",
          isStreaming: true,
          sources: [],
          hasWarning: false,
          traces: []
        },
      ]);
      void d;
    });

    const unsubThinking = wsClient.on("thinking", (data: unknown) => {
      const d = data as { agent: string; content: string };
      const id = currentAssistantId.current;
      if (!id) return;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? { ...msg, thinkingStep: { agent: d.agent, content: d.content } }
            : msg
        )
      );
    });

    const unsubAgentTrace = wsClient.on("agent_trace", (data: unknown) => {
      const d = data as { agent: string; trace: TraceStep[] };
      const id = currentAssistantId.current;
      if (!id) return;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? { ...msg, traces: [...(msg.traces || []), ...d.trace] }
            : msg
        )
      );
    });

    const unsubToken = wsClient.on("token", (data: unknown) => {
      const d = data as { content: string };
      const id = currentAssistantId.current;
      if (!id) return;

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? { ...msg, content: msg.content + d.content }
            : msg
        )
      );
    });

    const unsubDone = wsClient.on("done", (data: unknown) => {
      const d = data as {
        answer: string;
        sources: Source[];
        intent: any;
        confidence: number;
        traces: TraceStep[];
        session_id: string;
        user_context: any;
      };
      const id = currentAssistantId.current;
      if (!id) return;

      const answer = d.answer ?? "";
      const hasWarning =
        answer.includes("WARNING") || answer.includes("ALERT");

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? {
                ...msg,
                content: answer || msg.content,
                isStreaming: false,
                sources: d.sources ?? [],
                hasWarning,
                intent: d.intent,
                confidence: d.confidence,
                traces: d.traces ?? msg.traces,
                session_id: d.session_id,
                user_context: d.user_context,
                thinkingStep: undefined
              }
            : msg
        )
      );

      setIsStreaming(false);
      currentAssistantId.current = null;
      setActiveSessionId(d.session_id);

      // Refresh stats and user sessions/profile
      wsClient.send({ type: "stats" });
      fetchSessions();
      fetchUserProfile();
    });

    const unsubProgress = wsClient.on("progress", (data: unknown) => {
      const d = data as { message: string };
      setIngestProgress(d.message);
    });

    const unsubIngestDone = wsClient.on("ingest_done", (data: unknown) => {
      const d = data as { decisions_extracted: number };
      setIngestProgress(
        `Done. ${d.decisions_extracted} decisions extracted.`
      );
      setTimeout(() => setIngestProgress(null), 4000);
      wsClient.send({ type: "stats" });
    });

    const unsubStats = wsClient.on("stats", (data: unknown) => {
      const d = data as { data: KairosStats };
      if (d.data) setStats(d.data);
    });

    const unsubError = wsClient.on("error", (data: unknown) => {
      const d = data as { message: string };
      const id = currentAssistantId.current ?? generateId();

      setIsStreaming(false);
      currentAssistantId.current = null;

      setMessages((prev) => {
        const exists = prev.find((m) => m.id === id);
        if (exists) {
          return prev.map((m) =>
            m.id === id
              ? {
                  ...m,
                  content: d.message || "Something went wrong. Please try again.",
                  isStreaming: false,
                  hasWarning: true,
                  thinkingStep: undefined
                }
              : m
          );
        }
        return [
          ...prev,
          {
            id,
            role: "assistant",
            content: d.message || "Something went wrong. Please try again.",
            isStreaming: false,
            sources: [],
            hasWarning: true,
          },
        ];
      });
    });

    // Cleanup on unmount: remove listeners but DON'T disconnect the singleton
    // socket. Tearing it down here meant every route change (dashboard ↔
    // integrations) closed and re-opened the WebSocket, flashing "Reconnecting…"
    // and cancelling any in-flight query. The socket now survives navigation;
    // it's only closed explicitly on logout (the !token branch above).
    return () => {
      unsubConnection();
      unsubStart();
      unsubThinking();
      unsubAgentTrace();
      unsubToken();
      unsubDone();
      unsubProgress();
      unsubIngestDone();
      unsubStats();
      unsubError();
    };
  }, [token, fetchSessions, fetchUserProfile]);

  const sendQuestion = useCallback((question: string) => {
    if (!question.trim() || isStreaming) return;

    // Add the user message immediately
    const userMsgId = generateId();
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        content: question.trim(),
        isStreaming: false,
        sources: [],
        hasWarning: false,
      },
    ]);

    const sent = wsClient.send({ type: "query", question: question.trim(), session_id: activeSessionId });
    if (!sent) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: "Message not sent — you're disconnected. Reconnecting automatically; please try again in a moment.",
          isStreaming: false,
          sources: [],
          hasWarning: true,
        },
      ]);
    }
  }, [isStreaming, activeSessionId]);

  const startIngest = useCallback((sources: string[]) => {
    wsClient.send({ type: "ingest", sources });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setActiveSessionId(undefined);
  }, []);

  const retryConnection = useCallback(() => {
    setIsReconnectExhausted(false);
    wsClient.retryConnection();
  }, []);

  return {
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
    startIngest,
    clearMessages,
    loadSession,
    deleteSession,
    resetProfile,
    fetchSessions,
    fetchUserProfile
  };
}
