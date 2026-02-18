"""
routes/users.py — пользователи и управление подписками.

Endpoints:
  GET  /api/users                     — список с поиском и пагинацией
  GET  /api/users/<uid>               — детали пользователя
  POST /api/users/<uid>/ban           — бан / разбан
  POST /api/users/<uid>/sub/grant     — выдать подписку (Marzban + DB)
  POST /api/users/<uid>/sub/extend    — продлить подписку (Marzban + DB)
  POST /api/users/<uid>/sub/disable   — отключить подписку (Marzban + DB)
"""

import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from db import run, conn, row, rows
import marzban as mz

bp = Blueprint("users", __name__)

PLAN_DAYS: int = int(os.environ.get("PLAN_DAYS", "30"))
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

# ── Единый SQL: пользователи + последняя подписка + суммарные платежи ─────────
_USERS_SQL = """
SELECT
    u.user_id, u.username, u.first_name, u.is_banned, u.registered_at,
    s.id        AS sub_id,
    s.marzban_username,
    s.expires_at,
    s.is_active AS sub_active,
    s.auto_renew,
    COALESCE(p.total_spent, 0) AS total_spent,
    COALESCE(p.pay_count, 0)   AS pay_count
FROM users u
LEFT JOIN LATERAL (
    SELECT id, marzban_username, expires_at, is_active, auto_renew
    FROM subscriptions WHERE user_id = u.user_id
    ORDER BY id DESC LIMIT 1
) s ON true
LEFT JOIN LATERAL (
    SELECT SUM(amount) total_spent, COUNT(*) pay_count
    FROM payments WHERE user_id = u.user_id AND status = 'succeeded'
) p ON true
"""


# ── List ───────────────────────────────────────────────────────────────────────

@bp.get("/users")
def list_users():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 25)))
    search   = request.args.get("search", "").strip()
    status   = request.args.get("status", "")   # all | banned | active_sub | no_sub
    offset   = (page - 1) * per_page

    async def _():
        c = await conn()
        try:
            filters, params = _build_filters(search, status)
            where = f"WHERE {' AND '.join(filters)}" if filters else ""
            n = len(params)

            total = await c.fetchval(f"SELECT COUNT(*) FROM users u {where}", *params)
            data  = await c.fetch(
                f"{_USERS_SQL} {where} ORDER BY u.registered_at DESC LIMIT ${n+1} OFFSET ${n+2}",
                *params, per_page, offset,
            )
        finally:
            await c.close()
        return {"total": total, "page": page, "per_page": per_page, "users": rows(data)}

    return jsonify(run(_()))


def _build_filters(search: str, status: str):
    filters, params = [], []
    if search:
        i = len(params) + 1
        filters.append(f"(u.username ILIKE ${i} OR u.first_name ILIKE ${i} OR u.user_id::text = ${i+1})")
        params += [f"%{search}%", search]
    if status == "banned":
        filters.append("u.is_banned")
    elif status == "active_sub":
        filters.append("s.is_active AND s.expires_at > NOW()")
    elif status == "no_sub":
        filters.append("s.id IS NULL OR NOT s.is_active OR s.expires_at <= NOW()")
    return filters, params


# ── Detail ─────────────────────────────────────────────────────────────────────

@bp.get("/users/<int:uid>")
def user_detail(uid):
    async def _():
        c = await conn()
        try:
            u    = await c.fetchrow(f"{_USERS_SQL} WHERE u.user_id = $1", uid)
            subs = await c.fetch("SELECT * FROM subscriptions WHERE user_id=$1 ORDER BY id DESC", uid)
            pays = await c.fetch("SELECT * FROM payments WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20", uid)
        finally:
            await c.close()
        if not u:
            return None
        return {"user": row(u), "subscriptions": rows(subs), "payments": rows(pays)}

    result = run(_())
    if result is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


# ── Ban ────────────────────────────────────────────────────────────────────────

@bp.post("/users/<int:uid>/ban")
def ban_user(uid):
    banned = (request.json or {}).get("banned", True)

    async def _():
        c = await conn()
        try:
            await c.execute("UPDATE users SET is_banned=$1 WHERE user_id=$2", banned, uid)
        finally:
            await c.close()

    run(_())
    return jsonify({"ok": True, "banned": banned})


# ── Grant subscription ─────────────────────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/grant")
def grant_sub(uid):
    """Создаёт пользователя в Marzban и добавляет подписку в БД."""
    async def _():
        # 1. Marzban
        mz_user = await mz.create_user(uid)
        mz_username = mz_user["username"]
        link = next((l for l in mz_user.get("links", []) if l.startswith("vless://")), None)

        # 2. DB
        expires_at = datetime.utcnow() + timedelta(days=PLAN_DAYS)
        c = await conn()
        try:
            sub_id = await c.fetchval("""
                INSERT INTO subscriptions (user_id, marzban_username, expires_at, is_active, auto_renew)
                VALUES ($1, $2, $3, TRUE, TRUE) RETURNING id
            """, uid, mz_username, expires_at)
        finally:
            await c.close()

        return {"ok": True, "sub_id": sub_id, "marzban_username": mz_username, "link": link}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Extend subscription ────────────────────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/extend")
def extend_sub(uid):
    """Продлевает активную подписку пользователя на PLAN_DAYS дней."""
    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow("""
                SELECT id, marzban_username FROM subscriptions
                WHERE user_id=$1 ORDER BY id DESC LIMIT 1
            """, uid)
            if not sub:
                return {"error": "Подписка не найдена"}

            # Marzban
            await mz.extend_user(sub["marzban_username"])

            # DB
            await c.execute("""
                UPDATE subscriptions
                SET expires_at = GREATEST(expires_at, NOW()) + $1::interval,
                    is_active  = TRUE
                WHERE id = $2
            """, f"{PLAN_DAYS} days", sub["id"])
        finally:
            await c.close()
        return {"ok": True}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Disable subscription ───────────────────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/disable")
def disable_sub(uid):
    """Деактивирует подписку (опционально удаляет из Marzban)."""
    delete_from_marzban = (request.json or {}).get("delete_marzban", False)

    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow("""
                SELECT id, marzban_username FROM subscriptions
                WHERE user_id=$1 AND is_active=TRUE ORDER BY id DESC LIMIT 1
            """, uid)
            if not sub:
                return {"error": "Активная подписка не найдена"}

            await c.execute("UPDATE subscriptions SET is_active=FALSE WHERE id=$1", sub["id"])
        finally:
            await c.close()

        if delete_from_marzban:
            try:
                await mz.delete_user(sub["marzban_username"])
            except Exception:
                pass  # не ломаем ответ если Marzban недоступен

        return {"ok": True}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
