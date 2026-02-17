"""
database/init_db.py — создание таблиц при старте приложения.

Вызывается один раз при запуске бота.
Таблицы создаются с IF NOT EXISTS (asyncpg-lite делает это автоматически).
"""

from sqlalchemy import BigInteger, String, Boolean, Integer, DateTime, Numeric
from bot.database.manager import db


async def create_tables() -> None:
    """Создаёт все необходимые таблицы, если они ещё не существуют."""
    async with db:
        # ── users ─────────────────────────────────────────────────────────────
        await db.create_table(
            table_name="users",
            columns=[
                {"name": "user_id",      "type": BigInteger, "options": {"primary_key": True, "autoincrement": False}},
                {"name": "username",     "type": String,     "options": {"nullable": True}},
                {"name": "first_name",   "type": String,     "options": {}},
                {"name": "is_banned",    "type": Boolean,    "options": {"default": False}},
                {"name": "registered_at","type": DateTime,   "options": {}},
            ],
        )

        # ── subscriptions ─────────────────────────────────────────────────────
        # Одна активная подписка на пользователя (is_active=True)
        await db.create_table(
            table_name="subscriptions",
            columns=[
                {"name": "id",                     "type": Integer,  "options": {"primary_key": True}},
                {"name": "user_id",                "type": BigInteger,"options": {}},
                {"name": "marzban_username",       "type": String,   "options": {}},
                {"name": "expires_at",             "type": DateTime,  "options": {}},
                {"name": "is_active",              "type": Boolean,   "options": {"default": True}},
                # ID сохранённого метода оплаты ЮKassa для рекуррента
                {"name": "yukassa_payment_method_id", "type": String, "options": {"nullable": True}},
                # Флаг согласия пользователя на автопродление
                {"name": "auto_renew",             "type": Boolean,   "options": {"default": True}},
            ],
        )

        # ── payments ──────────────────────────────────────────────────────────
        await db.create_table(
            table_name="payments",
            columns=[
                {"name": "id",                "type": Integer,  "options": {"primary_key": True}},
                {"name": "user_id",           "type": BigInteger,"options": {}},
                {"name": "yukassa_payment_id","type": String,   "options": {"unique": True}},
                {"name": "amount",            "type": Numeric,  "options": {}},
                # pending | succeeded | canceled
                {"name": "status",            "type": String,   "options": {"default": "pending"}},
                {"name": "created_at",        "type": DateTime,  "options": {}},
                # К какой подписке относится (nullable — до активации)
                {"name": "subscription_id",   "type": Integer,  "options": {"nullable": True}},
            ],
        )
