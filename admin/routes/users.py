"""
routes/users.py — пользователи и управление подписками.
"""

import os
from datetime import datetime, timedelta, date
from flask import Blueprint, jsonify, request
from db import run, conn, row, rows
import pasarguard as pg

bp = Blueprint("users", __name__)

PLAN_DAYS: int = int(os.environ.get("PLAN_DAYS", "30"))

_BASE = """
SELECT
    u.user_id, u.username, u.first_name, u.is_banned, u.registered_at,
    s.id         AS sub_id,
    s.panel_username,
    s.expires_at,
    s.is_active  AS sub_active,
    s.auto_renew,
    COALESCE(p.total_spent, 0) AS total_spent,
    COALESCE(p.pay_count, 0)   AS pay_count
FROM users u
LEFT JOIN LATERAL (
    SELECT id, panel_username, expires_at, is_active, auto_renew
    FROM subscriptions WHERE user_id = u.user_id
    ORDER BY id DESC LIMIT 1
) s ON true
LEFT JOIN LATERAL (
    SELECT SUM(amount) total_spent, COUNT(*) pay_count
    FROM payments WHERE user_id = u.user_id AND status = 'succeeded'
) p ON true
"""


def _parse_date(s: str) -> date | None:
    """Конвертирует 'YYYY-MM-DD' → date. asyncpg требует объект date, не строку."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None


# ── List ───────────────────────────────────────────────────────────

_VALID_SORTS = {
    "registered_at": "u.registered_at",
    "total_spent":   "COALESCE(p.total_spent, 0)",
    "expires_at":    "s.expires_at",
}

@bp.get("/users")
def list_users():
    page       = max(1, int(request.args.get("page", 1)))
    per_page   = min(100, int(request.args.get("per_page", 25)))
    search     = request.args.get("search", "").strip()
    sub_status = request.args.get("sub_status", "")
    banned     = request.args.get("banned", "")
    reg_from   = _parse_date(request.args.get("reg_from", ""))
    reg_to     = _parse_date(request.args.get("reg_to", ""))
    sub_from   = _parse_date(request.args.get("sub_from", ""))
    sub_to     = _parse_date(request.args.get("sub_to", ""))
    sort       = request.args.get("sort", "registered_at")
    sort_dir   = "ASC" if request.args.get("sort_dir", "desc").lower() == "asc" else "DESC"
    offset     = (page - 1) * per_page

    sort_col   = _VALID_SORTS.get(sort, "u.registered_at")
    order_sql  = f"ORDER BY {sort_col} {sort_dir} NULLS LAST"

    async def _():
        c = await conn()
        try:
            filters, params = _build_filters(
                search, sub_status, banned, reg_from, reg_to, sub_from, sub_to
            )
            where = f"WHERE {' AND '.join(filters)}" if filters else ""
            n     = len(params)
            # Fix: wrap _BASE so WHERE can reference lateral-join aliases (s, p)
            total = await c.fetchval(
                f"SELECT COUNT(*) FROM ({_BASE} {where}) _cnt", *params
            )
            data  = await c.fetch(
                f"{_BASE} {where} {order_sql} LIMIT ${n+1} OFFSET ${n+2}",
                *params, per_page, offset,
            )
        finally:
            await c.close()
        return {"total": total, "page": page, "per_page": per_page, "users": rows(data)}

    return jsonify(run(_()))


def _build_filters(search, sub_status, banned, reg_from, reg_to, sub_from, sub_to):
    filters, params = [], []

    if search:
        i = len(params) + 1
        filters.append(
            f"(u.username ILIKE ${i} OR u.first_name ILIKE ${i} OR u.user_id::text = ${i+1})"
        )
        params += [f"%{search}%", search]

    if banned == "true":
        filters.append("u.is_banned = TRUE")
    elif banned == "false":
        filters.append("u.is_banned = FALSE")

    _SUB = {
        "active":   "s.is_active = TRUE AND s.expires_at > NOW()",
        "expiring": "s.is_active = TRUE AND s.expires_at BETWEEN NOW() AND NOW() + INTERVAL '3 days'",
        "expired":  "(s.is_active = FALSE OR s.expires_at <= NOW())",
        "no_sub":   "s.id IS NULL",
    }
    if sub_status in _SUB:
        filters.append(_SUB[sub_status])

    if reg_from:
        i = len(params) + 1
        filters.append(f"u.registered_at >= ${i}")
        params.append(reg_from)

    if reg_to:
        i = len(params) + 1
        filters.append(f"u.registered_at < (${i} + INTERVAL '1 day')")
        params.append(reg_to)

    if sub_from or sub_to:
        sub_clause = _date_range_clause(params, "px.created_at", sub_from, sub_to)
        filters.append(
            "EXISTS (SELECT 1 FROM payments px "
            f"WHERE px.user_id = u.user_id AND px.status = 'succeeded'{sub_clause})"
        )

    return filters, params


def _date_range_clause(params: list, col: str, from_val, to_val) -> str:
    clause = ""
    if from_val:
        i = len(params) + 1
        clause += f" AND {col} >= ${i}"
        params.append(from_val)
    if to_val:
        i = len(params) + 1
        clause += f" AND {col} < (${i} + INTERVAL '1 day')"
        params.append(to_val)
    return clause


# ── Detail ─────────────────────────────────────────────────────────

@bp.get("/users/<int:uid>")
def user_detail(uid):
    async def _():
        c = await conn()
        try:
            u    = await c.fetchrow(f"{_BASE} WHERE u.user_id = $1", uid)
            subs = await c.fetch("SELECT * FROM subscriptions WHERE user_id=$1 ORDER BY id DESC", uid)
            pays = await c.fetch(
                "SELECT * FROM payments WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20", uid
            )
        finally:
            await c.close()
        if not u:
            return None
        return {"user": row(u), "subscriptions": rows(subs), "payments": rows(pays)}

    result = run(_())
    if result is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


# ── Ban ────────────────────────────────────────────────────────────

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


# ── Grant subscription ─────────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/grant")
def grant_sub(uid):
    async def _():
        c = await conn()
        try:
            # Ищем любую подписку (активную или нет) — для переиспользования
            any_sub = await c.fetchrow(
                "SELECT id, panel_username, subscription_url, is_active "
                "FROM subscriptions WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
                uid,
            )
        finally:
            await c.close()

        if any_sub:
            # Пользователь уже существует — продлеваем / реактивируем
            # panel_username берём из БД, но если там вдруг старое значение — используем tg_{uid}
            panel_uname = any_sub["panel_username"] or pg.panel_username(uid)
            await pg.extend_user(panel_uname, PLAN_DAYS)

            # Получаем свежий subscription_url из PasarGuard (на случай если в БД пусто)
            pg_user = await pg.get_user(panel_uname)
            sub_url = any_sub["subscription_url"] or ""
            if not sub_url and pg_user:
                sub_url = pg_user.get("subscription_url") or ""
                if sub_url.startswith("/"):
                    sub_url = f"{pg.PASARGUARD_URL.rstrip('/')}{sub_url}"

            expires_at = datetime.utcnow() + timedelta(days=PLAN_DAYS)
            c = await conn()
            try:
                await c.execute("""
                    UPDATE subscriptions
                    SET expires_at = GREATEST(expires_at, NOW()) + $1::interval,
                        is_active  = TRUE,
                        subscription_url = COALESCE(NULLIF(subscription_url, ''), $2)
                    WHERE id = $3
                """, timedelta(days=PLAN_DAYS), sub_url or None, any_sub["id"])
            finally:
                await c.close()

            return {"ok": True, "sub_id": any_sub["id"], "panel_username": panel_uname,
                    "subscription_url": sub_url, "action": "extended"}

        else:
            # Первое начисление — создаём с нуля
            pg_user = await pg.ensure_user(uid)
            panel_uname = pg_user["username"]
            sub_url = pg_user.get("subscription_url") or ""
            if sub_url.startswith("/"):
                sub_url = f"{pg.PASARGUARD_URL.rstrip('/')}{sub_url}"
            expires_at = datetime.utcnow() + timedelta(days=PLAN_DAYS)

            c = await conn()
            try:
                sub_id = await c.fetchval("""
                    INSERT INTO subscriptions
                        (user_id, panel_username, expires_at, is_active, auto_renew, subscription_url)
                    VALUES ($1, $2, $3, TRUE, FALSE, $4) RETURNING id
                """, uid, panel_uname, expires_at, sub_url or None)
            finally:
                await c.close()

            return {"ok": True, "sub_id": sub_id, "panel_username": panel_uname,
                    "subscription_url": sub_url, "action": "created"}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Extend subscription ────────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/extend")
def extend_sub(uid):
    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow(
                "SELECT id, panel_username FROM subscriptions "
                "WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
                uid,
            )
            if not sub:
                return {"error": "Подписка не найдена"}
            await pg.extend_user(sub["panel_username"])
            await c.execute("""
                UPDATE subscriptions
                SET expires_at = GREATEST(expires_at, NOW()) + $1::interval,
                    is_active  = TRUE
                WHERE id = $2
            """, timedelta(days=PLAN_DAYS), sub["id"])
        finally:
            await c.close()
        return {"ok": True}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Adjust subscription (reduce/extend/set exact date) ────────────

@bp.post("/users/<int:uid>/sub/adjust")
def adjust_sub(uid):
    """
    Устанавливает новую дату истечения подписки.
    Принимает одно из двух:
      { "days": <int>  }          — смещение относительно текущей даты (может быть <0)
      { "exact_ts": <unix int> }  — точный Unix timestamp новой даты
    """
    body = request.json or {}

    if "exact_ts" in body:
        new_ts = int(body["exact_ts"])
    elif "days" in body:
        days   = int(body["days"])
        # Считаем от текущей expires_at, чтобы точно учесть текущий остаток
        new_ts = None  # вычислим в БД
        delta_days = days
    else:
        return jsonify({"error": "Укажите 'exact_ts' или 'days'"}), 400

    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow(
                "SELECT id, panel_username, expires_at FROM subscriptions "
                "WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
                uid,
            )
            if not sub:
                return {"error": "Подписка не найдена"}

            # Вычисляем итоговый timestamp
            if "exact_ts" in body:
                ts = new_ts
            else:
                from_dt = sub["expires_at"] if sub["expires_at"] else __import__('datetime').datetime.utcnow()
                ts = int(from_dt.timestamp()) + delta_days * 86400

            # Обновляем PasarGuard
            await pg.set_expire_user(sub["panel_username"], ts)

            # Обновляем БД
            from datetime import datetime as _dt
            new_expires = _dt.utcfromtimestamp(ts)
            await c.execute(
                "UPDATE subscriptions SET expires_at=$1, is_active=TRUE WHERE id=$2",
                new_expires, sub["id"],
            )
        finally:
            await c.close()
        return {"ok": True, "new_expires_ts": ts}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Delete user ────────────────────────────────────────────────────

@bp.delete("/users/<int:uid>")
def delete_user(uid):
    delete_from_panel = (request.json or {}).get("delete_panel", False)

    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow(
                "SELECT panel_username FROM subscriptions "
                "WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
                uid,
            )
            await c.execute("DELETE FROM payments WHERE user_id=$1", uid)
            await c.execute("DELETE FROM subscriptions WHERE user_id=$1", uid)
            deleted = await c.fetchval(
                "DELETE FROM users WHERE user_id=$1 RETURNING user_id", uid
            )
        finally:
            await c.close()

        if not deleted:
            return {"error": "Пользователь не найден"}

        if delete_from_panel and sub and sub["panel_username"]:
            try:
                await pg.delete_user(sub["panel_username"])
            except Exception:
                pass

        return {"ok": True}

    try:
        result = run(_())
        if result.get("error"):
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Disable subscription ───────────────────────────────────────────

@bp.post("/users/<int:uid>/sub/disable")
def disable_sub(uid):
    delete_from_panel = (request.json or {}).get("delete_panel", False)

    async def _():
        c = await conn()
        try:
            sub = await c.fetchrow("""
                SELECT id, panel_username FROM subscriptions
                WHERE user_id=$1 AND is_active=TRUE ORDER BY id DESC LIMIT 1
            """, uid)
            if not sub:
                return {"error": "Активная подписка не найдена"}
            await c.execute("UPDATE subscriptions SET is_active=FALSE WHERE id=$1", sub["id"])
        finally:
            await c.close()

        if delete_from_panel:
            try:
                await pg.delete_user(sub["panel_username"])
            except Exception:
                pass

        return {"ok": True}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Send message to single user ────────────────────────
import aiohttp as _aiohttp

@bp.post("/users/<int:uid>/message")
def send_message(uid):
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "Пустой текст"}), 400

    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        return jsonify({"error": "BOT_TOKEN не настроен"}), 500

    async def _():
        async with _aiohttp.ClientSession() as http:
            async with http.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": uid, "text": text, "parse_mode": "HTML"},
                timeout=_aiohttp.ClientTimeout(total=10),
            ) as r:
                body = await r.json()
                if r.status == 200:
                    return {"ok": True}
                return {"error": body.get("description", "Ошибка Telegram")}

    try:
        return jsonify(run(_()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
