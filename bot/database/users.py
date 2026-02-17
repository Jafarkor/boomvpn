"""
database/users.py — CRUD-операции для таблицы users.
"""

from datetime import datetime
from aiogram.types import User as TgUser
from bot.database.manager import db


async def get_user(user_id: int) -> dict | None:
    """Возвращает пользователя по telegram user_id или None."""
    async with db:
        return await db.select_data(
            table_name="users",
            where_dict={"user_id": user_id},
            one_dict=True,
        )


async def register_user(tg_user: TgUser) -> None:
    """Регистрирует нового пользователя (игнорирует повторную запись)."""
    async with db:
        await db.insert_data_with_update(
            table_name="users",
            records_data={
                "user_id":       tg_user.id,
                "username":      tg_user.username,
                "first_name":    tg_user.first_name or "User",
                "is_banned":     False,
                "registered_at": datetime.utcnow(),
            },
            conflict_column="user_id",
            update_on_conflict=False,  # не перезаписывать при повторном /start
        )


async def set_ban(user_id: int, banned: bool) -> None:
    """Устанавливает статус бана пользователя."""
    async with db:
        await db.update_data(
            table_name="users",
            where_dict={"user_id": user_id},
            update_dict={"is_banned": banned},
        )


async def get_all_users() -> list[dict]:
    """Возвращает всех пользователей (для рассылки, статистики)."""
    async with db:
        return await db.select_data(table_name="users")


async def count_users() -> int:
    """Количество зарегистрированных пользователей."""
    users = await get_all_users()
    return len(users)
