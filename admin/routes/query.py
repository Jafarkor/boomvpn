"""routes/query.py — /api/query (только SELECT)"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, jsonify, request
from db import run, conn

bp = Blueprint("query", __name__)


def _safe(v):
    if isinstance(v, datetime): return v.isoformat()
    if isinstance(v, Decimal):  return float(v)
    if isinstance(v, bytes):    return v.hex()
    return v


@bp.post("/query")
def sql_query():
    sql = (request.json or {}).get("sql", "").strip()
    if not sql:
        return jsonify({"error": "Пустой запрос"}), 400
    if not sql.upper().lstrip().startswith("SELECT"):
        return jsonify({"error": "Разрешены только SELECT-запросы"}), 400

    async def _():
        c = await conn()
        try:
            records = await c.fetch(sql)
        except Exception as e:
            return {"error": str(e)}
        finally:
            await c.close()

        if not records:
            return {"columns": [], "rows": [], "count": 0}

        cols = list(records[0].keys())
        data = [[_safe(r[col]) for col in cols] for r in records[:500]]
        return {"columns": cols, "rows": data, "count": len(data)}

    return jsonify(run(_()))
