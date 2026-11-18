"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export type StreamConnectionState = "connected" | "connecting" | "offline";

export interface RealtimeEnvelope {
  event_id?: string;
  type: string;
  timestamp_utc?: string;
  payload?: Record<string, unknown>;
}

interface UseRealtimeStreamOptions {
  enabled: boolean;
  onEvent?: (envelope: RealtimeEnvelope) => void;
  onResyncRequired?: () => void;
}

const CLOSE_SESSION_SUPERSEDED = 4401;
const CLOSE_SUBSCRIPTION_EXPIRED = 4403;

function buildWsUrl(): string {
  const base = API_BASE_URL.replace(/^http/, "ws").replace(/\/+$/, "");
  return `${base}/ws/v1/stream`;
}

export function useRealtimeStream({
  enabled,
  onEvent,
  onResyncRequired,
}: UseRealtimeStreamOptions): StreamConnectionState {
  const [state, setState] = useState<StreamConnectionState>("offline");
  const onEventRef = useRef(onEvent);
  const onResyncRef = useRef(onResyncRequired);
  onEventRef.current = onEvent;
  onResyncRef.current = onResyncRequired;

  useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      setState("offline");
      return;
    }

    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let hadConnectedOnce = false;

    const connect = () => {
      if (cancelled) return;
      setState("connecting");
      try {
        // Cookie-only WebSocket handshake — zero tokens in URL query strings
        socket = new WebSocket(buildWsUrl());
      } catch {
        setState("offline");
        return;
      }

      socket.onopen = () => {
        if (cancelled) return;
        attempt = 0;
        setState("connected");
        if (hadConnectedOnce) {
          onResyncRef.current?.();
        }
        hadConnectedOnce = true;
      };

      socket.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(String(ev.data)) as RealtimeEnvelope;
          if (parsed.type === "ping") {
            socket?.send(JSON.stringify({ type: "pong" }));
            return;
          }
          if (parsed.type === "session.invalidated") {
            cancelled = true;
            const code = String(parsed.payload?.code ?? "SESSION_SUPERSEDED");
            const reason =
              code === "SESSION_REVOKED" ? "session_revoked" : "session_superseded";
            window.location.assign(`/login?reason=${reason}`);
            return;
          }
          onEventRef.current?.(parsed);
        } catch {
          // Ignore malformed frames cleanly
        }
      };

      socket.onclose = (ev) => {
        if (cancelled) return;
        setState("offline");
        if (ev.code === CLOSE_SESSION_SUPERSEDED) {
          cancelled = true;
          window.location.assign("/login?reason=session_superseded");
          return;
        }
        if (ev.code === CLOSE_SUBSCRIPTION_EXPIRED) {
          cancelled = true;
          return;
        }
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s with small jitter
        const baseDelay = Math.min(30000, 1000 * Math.pow(2, attempt));
        const jitter = Math.floor(Math.random() * 500);
        attempt += 1;
        reconnectTimer = setTimeout(connect, baseDelay + jitter);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [enabled]);

  return state;
}
