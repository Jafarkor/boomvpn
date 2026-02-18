"""routes/payments.py — /api/payments"""

from flask import Blueprint, jsonify, request
from db import run, conn, rows

bp = Blueprint("payments", __name__)


@bp.get("/payments")
def list_payments():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 25)))
    status   = request.args.get("status", "")
    offset   = (page - 1) * per_page

    async def _():
        c = await conn()
        try:
            params  = [status] if status else []
            where   = "WHERE p.status=$1" if status else ""
            n       = len(params)
            total   = await c.fetchval(f"SELECT COUNT(*) FROM payments p {where}", *params)
            data    = await c.fetch(f"""
                SELECT p.*, u.username, u.first_name
                FROM payments p LEFT JOIN users u ON u.user_id = p.user_id
                {where} ORDER BY p.created_at DESC LIMIT ${n+1} OFFSET ${n+2}
            """, *params, per_page, offset)
        finally:
            await c.close()
        return {"total": total, "page": page, "per_page": per_page, "payments": rows(data)}

    return jsonify(run(_()))
