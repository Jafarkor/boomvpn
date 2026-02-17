"""
middlewares/ban_check.py — проверка бана пользователя перед обработкой апдейта.
"""

from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.database.users import get_user


class BanCheckMiddleware(BaseMiddleware):
    """Блокирует апдейты от забаненных пользователей."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            db_user = await get_user(user.id)
            if db_user and db_user.get("is_banned"):
                return None  # тихо игнорируем

        return await handler(event, data)
