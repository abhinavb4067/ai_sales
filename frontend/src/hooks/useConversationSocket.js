import { useEffect, useRef } from "react";
import { API_BASE_URL } from "../services/apiClient";
import { getAccessToken } from "../services/tokenStore";

const RECONNECT_DELAY_MS = 3000;

/**
 * Live conversation/message events for the current business, with
 * reconnect handling per the architecture doc: on reconnect (or on first
 * connect) the caller is expected to do a REST fetch of current state —
 * this hook never assumes an event it missed while disconnected will be
 * replayed, it only signals "something changed, go refetch."
 */
export function useConversationSocket(onEvent) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let socket;
    let reconnectTimer;
    let closedByCaller = false;

    const connect = () => {
      const token = getAccessToken();
      if (!token) return;

      const wsBase = API_BASE_URL.replace(/^http/, "ws").replace(/\/api\/v1\/?$/, "");
      socket = new WebSocket(`${wsBase}/ws/conversations/?token=${token}`);

      socket.onmessage = (event) => {
        try {
          onEventRef.current?.(JSON.parse(event.data));
        } catch {
          // Ignore malformed frames — never let a bad payload crash the UI.
        }
      };

      socket.onclose = () => {
        if (!closedByCaller) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
    };

    connect();

    return () => {
      closedByCaller = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);
}
