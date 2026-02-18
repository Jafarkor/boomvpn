"""
routes/broadcast.py — /api/broadcast

Аудитории:
  all           — все незабаненные
  active        — есть активная подписка
  expiring      — подписка истекает в ближайшие 3 дня
  expired       — подписка истекла (is_active=FALSE или expires_at прошёл)
  no_sub        — никогда не покупали подписку
  no_payment    — зарегистрированы, но ни разу не платили
  paid_once     — ровно 1 успешный платёж
"""

import os
import aiohttp
from flask import Blueprint, jsonify, request
from db import run, conn

bp = Blueprint("broadcast", __name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

_AUDIENCE_QUERIES = {
    "all": """
        SELECT user_id FROM users WHERE NOT is_banned
    """,
    "active": """
        SELECT DISTINCT u.user_id FROM users u
        JOIN subscriptions s ON s.user_id = u.user_id
        WHERE NOT u.is_banned AND s.is_active AND s.expires_at > NOW()
    """,
    "expiring": """
        SELECT DISTINCT u.user_id FROM users u
        JOIN subscriptions s ON s.user_id = u.user_id
        WHERE NOT u.is_banned AND s.is_active
          AND s.expires_at BETWEEN NOW() AND NOW() + INTERVAL '3 days'
    """,
    "expired": """
        SELECT DISTINCT u.user_id FROM users u
        JOIN subscriptions s ON s.user_id = u.user_id
        WHERE NOT u.is_banned
          AND (NOT s.is_active OR s.expires_at <= NOW())
          AND NOT EXISTS (
              SELECT 1 FROM subscriptions s2
              WHERE s2.user_id = u.user_id AND s2.is_active AND s2.expires_at > NOW()
          )
    """,
    "no_sub": """
        SELECT u.user_id FROM users u
        WHERE NOT u.is_banned
          AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id = u.user_id)
    """,
    "no_payment": """
        SELECT u.user_id FROM users u
        WHERE NOT u.is_banned
          AND NOT EXISTS (
              SELECT 1 FROM payments p WHERE p.user_id = u.user_id AND p.status = 'succeeded'
          )
    """,
    "paid_once": """
        SELECT u.user_id FROM users u
        WHERE NOT u.is_banned
          AND (
              SELECT COUNT(*) FROM payments p
              WHERE p.user_id = u.user_id AND p.status = 'succeeded'
          ) = 1
    """,
}


@bp.post("/broadcast")
def broadcast():
    data     = request.json or {}
    text     = data.get("text", "").strip()
    audience = data.get("audience", "all")

    if not text:
        return jsonify({"error": "Пустой текст"}), 400
    if audience not in _AUDIENCE_QUERIES:
        return jsonify({"error": f"Неизвестная аудитория: {audience}"}), 400

    async def _():
        c = await conn()
        try:
            targets = await c.fetch(_AUDIENCE_QUERIES[audience])
        finally:
            await c.close()

        sent = failed = 0
        async with aiohttp.ClientSession() as http:
            for t in targets:
                try:
                    async with http.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": t["user_id"], "text": text, "parse_mode": "HTML"},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as r:
                        if r.status == 200:
                            sent += 1
                        else:
                            failed += 1
                except Exception:
                    failed += 1

        return {"sent": sent, "failed": failed, "total": len(targets)}

    return jsonify(run(_()))


@bp.get("/broadcast/count")
def broadcast_count():
    """Возвращает количество получателей для выбранной аудитории (предпросмотр)."""
    audience = request.args.get("audience", "all")
    if audience not in _AUDIENCE_QUERIES:
        return jsonify({"error": "Неизвестная аудитория"}), 400

    async def _():
        c = await conn()
        try:
            count = await c.fetchval(
                f"SELECT COUNT(*) FROM ({_AUDIENCE_QUERIES[audience]}) t"
            )
        finally:
            await c.close()
        return {"count": count}

    return jsonify(run(_()))
