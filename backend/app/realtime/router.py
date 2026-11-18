"""WebSocket real-time stream endpoint (/ws/v1/stream) with cookie auth and instant eviction."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.authentication.service import validate_session_token
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.redis import build_ws_envelope
from app.realtime.ws_manager import WS_CLOSE_SESSION_SUPERSEDED, WebSocketManager
from app.subscriptions.service import get_user_entitlement

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/v1/stream")
async def realtime_stream(websocket: WebSocket) -> None:
    """Authenticate via HttpOnly session cookie, enforce Origin allowlist, and stream events."""
    settings = getattr(websocket.app.state, "settings", None) or get_settings()

    # Reject query-string session tokens to prevent secret leakage into reverse-proxy logs
    if "token" in websocket.query_params or "session" in websocket.query_params:
        await websocket.close(code=WS_CLOSE_SESSION_SUPERSEDED, reason="QUERY_TOKEN_PROHIBITED")
        return

    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origins_list:
        await websocket.close(code=1008, reason="ORIGIN_NOT_ALLOWED")
        return

    raw_token = websocket.cookies.get(settings.session_cookie_name)
    session_factory = websocket.app.state.db_session_factory
    redis_client = getattr(websocket.app.state, "redis_client", None)
    ws_manager: WebSocketManager = websocket.app.state.ws_manager

    db = session_factory()
    try:
        try:
            user, session, role_code = validate_session_token(
                db,
                redis_client=redis_client,
                raw_token=raw_token,
            )
        except APIError as exc:
            await websocket.accept()
            await websocket.send_json(
                build_ws_envelope(
                    "session.invalidated",
                    {
                        "code": exc.code,
                        "reason": exc.message,
                        "revoked_by": "validation",
                    },
                )
            )
            await websocket.close(code=WS_CLOSE_SESSION_SUPERSEDED, reason=exc.code)
            return

        entitlement = get_user_entitlement(db, user_id=user.id, role_code=role_code)
    finally:
        db.close()

    await websocket.accept()
    conn = await ws_manager.register(
        websocket,
        user_id=user.id,
        session_id=session.id,
        role_code=role_code,
        entitled_markets=entitlement.entitled_markets,
    )

    try:
        await websocket.send_json(
            build_ws_envelope(
                "connection.ready",
                {
                    "user_id": str(user.id),
                    "role": role_code,
                    "entitled_markets": entitlement.entitled_markets,
                },
            )
        )
        while True:
            try:
                raw_msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            try:
                parsed = json.loads(raw_msg)
            except ValueError:
                continue

            if isinstance(parsed, dict) and parsed.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unregister(conn)
