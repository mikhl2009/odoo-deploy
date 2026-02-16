from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self.channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.channels[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if websocket in self.channels[channel]:
            self.channels[channel].remove(websocket)
        if not self.channels[channel]:
            self.channels.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for socket in self.channels.get(channel, set()):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(channel, socket)


ws_manager = WSManager()
