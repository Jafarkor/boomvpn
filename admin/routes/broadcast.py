"""routes/broadcast.py — /api/broadcast"""

import os
import aiohttp
from flask import Blueprint, jsonify, request
from db import run, conn

bp = Blueprint("broadcast", __name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


@bp.post("/broadcast")
def broadcast():
    data        = request.json or {}
    text        = data.get("text", "").strip()
    only_active = data.get("only_active", False)

    if not text:
        return jsonify({"error": "Пустой текст"}), 400

    async def _():
        c = await conn()
        try:
            if only_active:
                query = """
                    SELECT DISTINCT u.user_id FROM users u
                    JOIN subscriptions s ON s.user_id=u.user_id
                    WHERE NOT u.is_banned AND s.is_active AND s.expires_at > NOW()
                """
            else:
                query = "SELECT user_id FROM users WHERE NOT is_banned"
            targets = await c.fetch(query)
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
                        sent += 1 if r.status == 200 else 0
                        failed += 0 if r.status == 200 else 1
                except Exception:
                    failed += 1
        return {"sent": sent, "failed": failed}

    return jsonify(run(_()))
