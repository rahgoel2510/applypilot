"""WebSocket endpoint for real-time pipeline event streaming.

Clients connect to /ws/events and receive JSON messages as the agent
processes jobs. Events are pushed from the webhook/agent endpoint and
from internal pipeline stages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._event_history: list[dict] = []  # Last 100 events for new clients
        self._max_history = 100

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self.active_connections))
        # Send recent history to new client
        if self._event_history:
            await websocket.send_json({"type": "history", "events": self._event_history[-50:]})

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(self.active_connections))

    async def broadcast(self, event: dict):
        """Send event to all connected clients."""
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # Broadcast to all active connections
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except Exception:
                disconnected.append(connection)
        
        # Clean up dead connections
        for conn in disconnected:
            try:
                self.active_connections.remove(conn)
            except ValueError:
                pass

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Singleton manager
manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    """Get the WebSocket connection manager singleton."""
    return manager


async def push_event(
    event_type: str,
    title: str = "",
    company: str = "",
    location: str = "",
    match_score: float | None = None,
    stage: str = "",
    status: str = "",
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Push a pipeline event to all connected WebSocket clients.
    
    Call this from anywhere in the backend to broadcast real-time updates.
    """
    event = {
        "type": "pipeline_event",
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "title": title,
            "company": company,
            "location": location,
            "match_score": match_score,
            "stage": stage,
            "status": status,
            "message": message,
            "metadata": metadata or {},
        },
    }
    await manager.broadcast(event)


async def push_stats_update(stats: dict) -> None:
    """Push updated KPI stats to all clients."""
    event = {
        "type": "stats_update",
        "timestamp": datetime.now().isoformat(),
        "data": stats,
    }
    await manager.broadcast(event)


async def push_agent_status(status: str, message: str = "") -> None:
    """Push agent status change (running/stopped/error)."""
    event = {
        "type": "agent_status",
        "timestamp": datetime.now().isoformat(),
        "data": {"status": status, "message": message},
    }
    await manager.broadcast(event)


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline events.
    
    Clients connect and receive JSON messages:
    - {type: 'pipeline_event', event_type: '...', data: {...}}
    - {type: 'stats_update', data: {total_jobs: N, applied: N, ...}}
    - {type: 'agent_status', data: {status: 'running'|'stopped'}}
    - {type: 'history', events: [...]}
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
