import asyncio
from typing import Any, Dict, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class RealtimeHub:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, socket: WebSocket):
        await socket.accept()
        async with self._lock:
            self.connections.add(socket)

    async def disconnect(self, socket: WebSocket):
        async with self._lock:
            self.connections.discard(socket)

    async def broadcast(self, event: Dict[str, Any]):
        async with self._lock:
            sockets = tuple(self.connections)
        stale = []
        for socket in sockets:
            try:
                await socket.send_json(event)
            except (WebSocketDisconnect, RuntimeError, OSError):
                stale.append(socket)
        if stale:
            async with self._lock:
                for socket in stale:
                    self.connections.discard(socket)


realtime_hub = RealtimeHub()
