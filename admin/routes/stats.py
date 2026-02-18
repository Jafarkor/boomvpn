"""routes/stats.py — /api/stats"""

from flask import Blueprint, jsonify
from db import run, conn, rows

bp = Blueprint("stats", __name__)


@bp.get("/stats")
def get_stats():
    async def _():
        c = await conn()
        try:
            total_users   = await c.fetchval("SELECT COUNT(*) FROM users")
            banned        = await c.fetchval("SELECT COUNT(*) FROM users WHERE is_banned")
            new_today     = await c.fetchval("SELECT COUNT(*) FROM users WHERE registered_at >= NOW() - INTERVAL '24h'")
            active_subs   = await c.fetchval("SELECT COUNT(*) FROM subscriptions WHERE is_active AND expires_at > NOW()")
            expiring      = await c.fetchval("SELECT COUNT(*) FROM subscriptions WHERE is_active AND expires_at BETWEEN NOW() AND NOW() + INTERVAL '3 days'")
            revenue_total = await c.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='succeeded'")
            revenue_month = await c.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='succeeded' AND created_at >= NOW()-INTERVAL '30 days'")
            revenue_chart = await c.fetch("""
                SELECT DATE(created_at) day, SUM(amount) total FROM payments
                WHERE status='succeeded' AND created_at >= NOW()-INTERVAL '14 days'
                GROUP BY day ORDER BY day
            """)
            reg_chart = await c.fetch("""
                SELECT DATE(registered_at) day, COUNT(*) total FROM users
                WHERE registered_at >= NOW()-INTERVAL '14 days'
                GROUP BY day ORDER BY day
            """)
        finally:
            await c.close()

        return {
            "total_users": total_users, "banned": banned, "new_today": new_today,
            "active_subs": active_subs, "expiring": expiring,
            "revenue_total": float(revenue_total), "revenue_month": float(revenue_month),
            "revenue_chart": rows(revenue_chart), "reg_chart": rows(reg_chart),
        }

    return jsonify(run(_()))
