import { useState, useEffect, useRef, useCallback } from 'react';
import { getApiKey } from '../api';

/**
 * Custom hook for WebSocket connection to the pipeline event stream.
 * Auto-reconnects on disconnect. Provides real-time events.
 * Passes API key as token query parameter for authentication.
 */
export function useWebSocket() {
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [agentStatus, setAgentStatus] = useState('stopped');
  const [liveStats, setLiveStats] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = getApiKey();
    const wsUrl = `${protocol}//${window.location.host}/ws/events${token ? `?token=${encodeURIComponent(token)}` : ''}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[WS] Connected');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'pipeline_event') {
            setEvents((prev) => [msg, ...prev].slice(0, 200));
          } else if (msg.type === 'stats_update') {
            setLiveStats(msg.data);
          } else if (msg.type === 'agent_status') {
            setAgentStatus(msg.data?.status || 'stopped');
          } else if (msg.type === 'history') {
            setEvents((prev) => {
              const history = (msg.events || []).map((e) => ({
                ...e,
                type: e.type || 'pipeline_event',
              }));
              return [...history.reverse(), ...prev].slice(0, 200);
            });
          }
        } catch (e) {
          console.warn('[WS] Parse error:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('[WS] Disconnected, reconnecting in 3s...');
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      console.warn('[WS] Connection failed:', err);
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, isConnected, agentStatus, liveStats, clearEvents };
}
