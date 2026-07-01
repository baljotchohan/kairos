type Listener = (data: unknown) => void;

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

class KairosWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Listener[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private url = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000") + "/ws";
  private manuallyDisconnected = false;
  private token?: string;

  connect(token?: string): void {
    if (typeof window === "undefined") return;

    const tokenChanged = token && token !== this.token;
    if (token) {
      this.token = token;
    }

    if (tokenChanged && this.ws) {
      this.ws.close();
      this.ws = null;
    }

    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.manuallyDisconnected = false;

    try {
      const activeToken = this.token;
      const connectionUrl = activeToken ? `${this.url}?token=${encodeURIComponent(activeToken)}` : this.url;
      this.ws = new WebSocket(connectionUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.emit("connection", { connected: true });
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as WsMessage;
          this.emit(data.type, data);
          this.emit("*", data);
        } catch {
          // ignore malformed messages
        }
      };

      this.ws.onclose = () => {
        this.emit("connection", { connected: false });
        if (!this.manuallyDisconnected) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.emit("connection", { connected: false, error: true });
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      // Without this, the UI silently claims "Reconnecting…" forever after
      // attempts are exhausted, with no way back short of a full page reload.
      this.emit("connection", { connected: false, exhausted: true });
      return;
    }
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempts++;
      this.connect(this.token);
    }, this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts));
  }

  /** Manually retry after reconnect attempts were exhausted (e.g. a user
   * clicking a "Retry" button) — resets the backoff counter and connects. */
  retryConnection(): void {
    this.reconnectAttempts = 0;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.manuallyDisconnected = false;
    this.connect(this.token);
  }

  disconnect(): void {
    this.manuallyDisconnected = true;
    this.token = undefined;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("[KAIROS WS] Cannot send — not connected");
    }
  }

  on(type: string, callback: Listener): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(callback);

    return () => {
      const list = this.listeners.get(type);
      if (list) {
        const idx = list.indexOf(callback);
        if (idx !== -1) list.splice(idx, 1);
      }
    };
  }

  private emit(type: string, data: unknown): void {
    const list = this.listeners.get(type);
    if (list) {
      list.forEach((cb) => {
        try {
          cb(data);
        } catch {
          // listener errors are silent
        }
      });
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

// Singleton instance — safe to import from anywhere
export const wsClient = new KairosWebSocket();
