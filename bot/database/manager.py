"""
database/manager.py — синглтон DatabaseManager из asyncpg-lite.

Используем один объект на весь процесс.
Все операции с БД идут через async with db:
"""

from asyncpg_lite import DatabaseManager
from bot.config import PG_DSN, DB_DELETION_PASSWORD

# Единственный объект менеджера — создаётся один раз при импорте
db = DatabaseManager(
    db_url=PG_DSN,
    deletion_password=DB_DELETION_PASSWORD,
    echo=False,
)
