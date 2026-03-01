"""
middlewares/channel_check.py — middleware проверки подписки на канал.

Пропускает:
  - Команды /start (start-хендлер сам обрабатывает подписку)
  - Callback "check_channel_sub" (иначе зациклится)
  - Апдейты от незарегистрированных пользователей (их обработает /start)

Для всех остальных апдейтов: если пользователь не подписан → отправляем
сообщение с кнопками подписки и прерываем дальнейшую обработку.
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from bot.database.users import get_user
from bot.keyboards.user import channel_sub_kb
from bot.utils.channel import is_subscribed

logger = logging.getLogger(__name__)

# Апдейты, которые пропускаем без проверки
_SKIP_CALLBACKS = {"check_channel_sub"}
_SKIP_COMMANDS = {"/start"}


class ChannelSubscriptionMiddleware(BaseMiddleware):
    """Проверяет подписку на канал перед любым действием пользователя."""

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        # Определяем тип апдейта и user_id
        user_id: int | None = None
        skip = False

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            # Пропускаем /start — он сам управляет подпиской
            if event.text and any(event.text.startswith(cmd) for cmd in _SKIP_COMMANDS):
                skip = True

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            if event.data in _SKIP_CALLBACKS:
                skip = True

        if skip or user_id is None:
            return await handler(event, data)

        # Незарегистрированных пользователей пропускаем — пусть сначала сделают /start
        user = await get_user(user_id)
        if not user:
            return await handler(event, data)

        # Проверяем подписку
        bot = data.get("bot") or (event.bot if hasattr(event, "bot") else None)
        if bot and not await is_subscribed(user_id, bot):
            text = "📢 Для доступа к боту необходимо подписаться на наш официальный канал:"
            if isinstance(event, Message):
                await event.answer(text, reply_markup=channel_sub_kb())
            elif isinstance(event, CallbackQuery):
                await event.answer()
                await event.message.answer(text, reply_markup=channel_sub_kb())
            return  # Прерываем обработку

        return await handler(event, data)
