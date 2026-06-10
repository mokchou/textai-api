"""Hub WebSocket : un socket par client, canaux multiplexés
{channel, payload}. Diffusion thread-safe (les jobs tournent hors event loop)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[WebSocket] = set()

    def bind_loop(self) -> None:
        self.loop = asyncio.get_running_loop()

    def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        """Appelable depuis n'importe quel thread."""
        if self.loop is None or not self.clients:
            return
        msg = json.dumps({"channel": channel, "payload": payload}, ensure_ascii=False, default=str)
        self.loop.call_soon_threadsafe(self._fanout, msg)

    def _fanout(self, msg: str) -> None:
        for ws in list(self.clients):
            task = asyncio.ensure_future(ws.send_text(msg))
            task.add_done_callback(lambda t: t.exception())  # avale les déconnexions

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        try:
            while True:
                await ws.receive_text()  # keep-alive ; le client n'envoie rien d'utile
        except WebSocketDisconnect:
            pass
        finally:
            self.clients.discard(ws)


hub = Hub()
