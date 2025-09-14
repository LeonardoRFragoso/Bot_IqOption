/* Lightweight WebSocket client for real-time trading updates */

export type TradingWsEventType =
  | 'open'
  | 'close'
  | 'error'
  | 'status_update'
  | 'operation_update'
  | 'session_update'
  | 'trading_update'
  | 'logs_update'
  | 'pong';

export interface TradingWsMessage<T = any> {
  type: TradingWsEventType | string;
  data?: T;
  [key: string]: any;
}

export type TradingWsListener = (msg: TradingWsMessage) => void;

export interface TradingSocket {
  connect: () => void;
  disconnect: () => void;
  send: (message: Record<string, any>) => void;
  on: (event: TradingWsEventType | 'message', listener: TradingWsListener) => void;
  off: (event: TradingWsEventType | 'message', listener: TradingWsListener) => void;
  isConnected: () => boolean;
}

function defaultWsBase(): string {
  // Prefer explicit env var if provided (e.g., ws://127.0.0.1:8000)
  const env = (import.meta as any)?.env;
  const envUrl = env?.VITE_WS_URL || env?.VITE_BACKEND_WS_URL;
  if (envUrl) return envUrl.replace(/\/$/, '');
  // Fallback to local backend default used by REST client
  return (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + '127.0.0.1:8000';
}

export function createTradingSocket(): TradingSocket {
  const WS_BASE = defaultWsBase();
  const token = localStorage.getItem('access_token');
  const url = `${WS_BASE}/ws/trading/${token ? `?token=${encodeURIComponent(token)}` : ''}`;

  let ws: WebSocket | null = null;
  let connected = false;
  let reconnectAttempts = 0;
  let reconnectTimer: number | null = null;
  let pingTimer: number | null = null;
  const listeners = new Map<string, Set<TradingWsListener>>();

  function emit(event: string, payload: TradingWsMessage) {
    // 'message' wildcard listeners
    const anyListeners = listeners.get('message');
    if (anyListeners) anyListeners.forEach((l) => l(payload));
    const set = listeners.get(event);
    if (set) set.forEach((l) => l(payload));
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    const delay = Math.min(30000, 1000 * Math.pow(2, reconnectAttempts || 0));
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      reconnectAttempts += 1;
      connect();
    }, delay) as unknown as number;
  }

  function startPing() {
    stopPing();
    pingTimer = window.setInterval(() => {
      try {
        if (ws && connected) {
          ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        }
      } catch {}
    }, 5000) as unknown as number;
  }

  function stopPing() {
    if (pingTimer) {
      window.clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function connect() {
    try {
      if (ws && connected) return;
      ws = new WebSocket(url);

      ws.onopen = () => {
        connected = true;
        reconnectAttempts = 0;
        emit('open', { type: 'open' });
        // Request initial status
        try { ws?.send(JSON.stringify({ type: 'get_status' })); } catch {}
        // Start keepalive
        startPing();
      };

      ws.onmessage = (evt) => {
        let msg: TradingWsMessage;
        try {
          msg = JSON.parse(evt.data);
        } catch {
          msg = { type: 'message', data: evt.data } as any;
        }
        if (msg.type) emit(msg.type, msg);
        emit('message', msg);
      };

      ws.onclose = () => {
        connected = false;
        emit('close', { type: 'close' });
        stopPing();
        scheduleReconnect();
      };

      ws.onerror = () => {
        emit('error', { type: 'error' });
      };
    } catch (e) {
      scheduleReconnect();
    }
  }

  function disconnect() {
    try {
      if (reconnectTimer) { window.clearTimeout(reconnectTimer); reconnectTimer = null; }
      stopPing();
      ws?.close();
      ws = null;
      connected = false;
    } catch {}
  }

  function send(message: Record<string, any>) {
    try {
      if (ws && connected) ws.send(JSON.stringify(message));
    } catch {}
  }

  function on(event: TradingWsEventType | 'message', listener: TradingWsListener) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event)!.add(listener);
  }

  function off(event: TradingWsEventType | 'message', listener: TradingWsListener) {
    listeners.get(event)?.delete(listener);
  }

  function isConnected() { return connected; }

  // Auto-connect immediately
  connect();

  return { connect, disconnect, send, on, off, isConnected };
}
