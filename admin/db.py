"""
db.py — asyncpg helpers для Flask (sync → async bridge).
"""

import os
import asyncio
import asyncpg
from datetime import datetime
from decimal import Decimal

PG_DSN: str = os.environ.get("PG_DSN", "")


def run(coro):
    """Запускает корутину в новом event loop (Flask is sync)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def conn():
    """Открывает соединение с БД."""
    return await asyncpg.connect(dsn=PG_DSN)


def to_json(val):
    """Конвертирует asyncpg-типы в JSON-совместимые."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return val


def row(record) -> dict:
    return {k: to_json(v) for k, v in dict(record).items()}


def rows(records) -> list[dict]:
    return [row(r) for r in records]
