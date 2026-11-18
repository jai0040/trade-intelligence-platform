# WebSocket Real-Time Event Protocol Specification

**Endpoint:** `wss://<host>/ws/v1/stream` (local dev: `ws://localhost:8000/ws/v1/stream`)  
**Backplane:** Valkey / Redis Pub/Sub (enables horizontal scaling across multiple FastAPI replicas).

---

## 1. Connection & Authentication Handshake

1. Browser initiates WebSocket upgrade carrying the `HttpOnly`, `Secure` session cookie (`tip_session`). No token is ever passed in URL query strings (prevents session leakage into reverse-proxy logs).
2. FastAPI validates `Origin` against `CORS_ALLOWED_ORIGINS` and verifies `session_id` + `session_version` against Redis (`user:{user_id}:active_session`) and PostgreSQL `sessions`.
3. If invalid or superseded, the server rejects the handshake with HTTP `401` (or closes immediately with WebSocket application code `4401`).
4. On success, the server subscribes the connection to:
   - Private channel: `ws:user:{user_id}` (notifications, personal alert triggers, **single-session eviction**)
   - Entitled market channels: `ws:market:IN` and/or `ws:market:US` (based on active subscription entitlement)
   - Admin channel (only if `role IN ('super_admin', 'admin')`): `ws:admin:system`

---

## 2. Envelope Format

Every server-to-client frame is UTF-8 JSON following a uniform envelope:

```json
{
  "event_id": "019a0000-0000-7000-8000-000000000001",
  "type": "signal.created",
  "timestamp_utc": "2026-11-18T14:45:00Z",
  "payload": {}
}
```

---

## 3. Event Types

### 3.1 `session.invalidated` (Highest Priority — Single Active Session)
Delivered immediately to the old device when the user signs in on another device/browser or when a Super Admin revokes the session.

```json
{
  "event_id": "019a0000-0000-7000-8000-000000000002",
  "type": "session.invalidated",
  "timestamp_utc": "2026-11-18T14:46:12Z",
  "payload": {
    "code": "SESSION_SUPERSEDED",
    "reason": "Your account was signed in from another device or browser.",
    "revoked_by": "new_login"
  }
}
```
- Server closes the old WebSocket immediately after sending this frame with close code `4401` (`SESSION_SUPERSEDED`).
- Frontend clears client UI state and redirects to `/login?reason=session_superseded` displaying a clear non-alarming notice.

### 3.2 `market.status`
Broadcast on market open/close transitions, early close warnings, or provider freshness state changes.

```json
{
  "type": "market.status",
  "timestamp_utc": "2026-11-18T03:45:00Z",
  "payload": {
    "market_code": "IN",
    "exchange_code": "NSE",
    "is_open": true,
    "session_phase": "REGULAR",
    "data_freshness": {
      "provider": "licensed_india",
      "status": "HEALTHY",
      "delay_seconds": 2,
      "is_stale": false
    }
  }
}
```

### 3.3 `signal.created` & `signal.updated`
Published strictly **after** mandatory `trader-risk` validation passes and immutable PostgreSQL commit succeeds.

```json
{
  "type": "signal.created",
  "timestamp_utc": "2026-11-18T14:50:02Z",
  "payload": {
    "signal_id": "019a0000-0000-7000-8000-000000000010",
    "market_code": "US",
    "exchange_code": "NASDAQ",
    "symbol": "TSLA",
    "signal_type": "BUY",
    "strategy": "orb_15m",
    "entry_price": "364.18",
    "stop_loss": "358.32",
    "target_price": "375.90",
    "risk_reward_ratio": "2.00",
    "confidence_score": 74.5,
    "current_status": "Active",
    "expires_at_utc": "2026-11-18T20:55:00Z"
  }
}
```

### 3.4 `notification.created`
User-scoped alert (new signal matching user filter, entry/target/stop hit, signal expiry, important news, subscription renewal warning).

```json
{
  "type": "notification.created",
  "timestamp_utc": "2026-11-18T15:15:01Z",
  "payload": {
    "notification_id": "019a0000-0000-7000-8000-000000000099",
    "category": "TARGET_HIT",
    "title": "Target Hit: NSE:RELIANCE",
    "body": "Signal target ₹2,985.00 reached on 14:45 IST bar.",
    "is_read": false
  }
}
```

### 3.5 `admin.system_event` (Admin Channel Only)
Broadcast to authenticated Super Admins on kill-switch toggle, provider `DEGRADED`/`DOWN` alert, or worker failure spike.

---

## 4. Heartbeat, Backoff & Failure Handling

- **Heartbeat:** Server sends `{"type": "ping"}` every `30s`; client responds `{"type": "pong"}`. Connections silent for `> 90s` are closed cleanly.
- **Client Reconnect:** Exponential backoff (`1s`, `2s`, `4s`, `8s`, max `30s` with jitter). **Never reconnect** on close code `4401` (`SESSION_SUPERSEDED`) or `4403` (`SUBSCRIPTION_EXPIRED`).
- **State Resync:** Upon reconnect, the frontend re-fetches `/api/v1/markets/status` and latest signals so no events missed during brief network drops are lost.
