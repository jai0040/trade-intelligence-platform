"""WebSocket connection registry with immediate Single Active Session eviction support."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("trade_intelligence.realtime")

WS_CLOSE_SESSION_SUPERSEDED = 4401
WS_CLOSE_SUBSCRIPTION_EXPIRED = 4403


@dataclass
class ManagedConnection:
    websocket: WebSocket
    user_id: str
    session_id: str
    role_code: str
    entitled_markets: set[str] = field(default_factory=set)
    loop: asyncio.AbstractEventLoop | None = None


class WebSocketManager:
    """Tracks live WebSocket connections per user/session for instant eviction and broadcasts."""

    def __init__(self) -> None:
        self._by_user: dict[str, list[ManagedConnection]] = {}

    async def register(
        self,
        websocket: WebSocket,
        *,
        user_id: uuid.UUID | str,
        session_id: uuid.UUID | str,
        role_code: str,
        entitled_markets: list[str],
    ) -> ManagedConnection:
        uid = str(user_id)
        conn = ManagedConnection(
            websocket=websocket,
            user_id=uid,
            session_id=str(session_id),
            role_code=role_code,
            entitled_markets={m.upper() for m in entitled_markets},
            loop=asyncio.get_running_loop(),
        )
        self._by_user.setdefault(uid, []).append(conn)
        return conn

    def unregister(self, conn: ManagedConnection) -> None:
        conns = self._by_user.get(conn.user_id)
        if not conns:
            return
        self._by_user[conn.user_id] = [c for c in conns if c is not conn]
        if not self._by_user[conn.user_id]:
            self._by_user.pop(conn.user_id, None)

    def active_connections_for_user(self, user_id: uuid.UUID | str) -> list[ManagedConnection]:
        return list(self._by_user.get(str(user_id), ()))

    async def _evict_connection(
        self, conn: ManagedConnection, envelope: dict[str, Any], close_code: int
    ) -> None:
        try:
            await conn.websocket.send_json(envelope)
        except Exception:
            pass
        try:
            await conn.websocket.close(code=close_code, reason=envelope["payload"].get("code", "SESSION_SUPERSEDED"))
        except Exception:
            pass
        finally:
            self.unregister(conn)

    async def evict_user_sessions_async(
        self,
        *,
        user_id: uuid.UUID | str,
        revoked_session_ids: set[str] | None,
        envelope: dict[str, Any],
        close_code: int = WS_CLOSE_SESSION_SUPERSEDED,
    ) -> int:
        """Send session.invalidated frame and close matching sockets with code 4401."""
        targets = self.active_connections_for_user(user_id)
        evicted = 0
        for conn in targets:
            if revoked_session_ids is not None and conn.session_id not in revoked_session_ids:
                continue
            await self._evict_connection(conn, envelope, close_code)
            evicted += 1
        return evicted

    def notify_session_invalidated(
        self,
        *,
        user_id: uuid.UUID | str,
        revoked_session_ids: list[str] | None,
        envelope: dict[str, Any],
        close_code: int = WS_CLOSE_SESSION_SUPERSEDED,
    ) -> None:
        """Thread-safe trigger usable from sync route handlers or async coroutines."""
        targets = self.active_connections_for_user(user_id)
        if not targets:
            return
        allowed_ids = set(revoked_session_ids) if revoked_session_ids else None
        for conn in targets:
            if allowed_ids is not None and conn.session_id not in allowed_ids:
                continue
            coro = self._evict_connection(conn, envelope, close_code)
            if conn.loop is not None and conn.loop.is_running():
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None
                if current_loop is conn.loop:
                    conn.loop.create_task(coro)
                else:
                    future = asyncio.run_coroutine_threadsafe(coro, conn.loop)
                    try:
                        future.result(timeout=2.0)
                    except Exception:
                        logger.debug("WebSocket eviction future timed out or closed", exc_info=True)
            else:
                try:
                    asyncio.run(coro)
                except Exception:
                    self.unregister(conn)
