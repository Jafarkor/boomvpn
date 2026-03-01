"""
middlewares/channel_check.py — проверка обязательной подписки на канал.

Блокирует любые апдейты от пользователей, не подписанных на канал,
и показывает им сообщение с кнопкой подписки.
Admins (из ADMIN_IDS) пропускаются без проверки.
"""

import logging
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.enums import ChatMemberStatus
from aiogram.types import TelegramObject, Message, CallbackQuery

from bot.config import CHANNEL_USERNAME, ADMIN_IDS
from bot.keyboards.user import channel_subscription_kb

logger = logging.getLogger(__name__)


async def is_subscribed(user_id: int, bot) -> bool:
    """Проверяет подписку пользователя на канал."""
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        logger.info(f"Subscription check for user {user_id}: status = {member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        return False


class ChannelSubscriptionMiddleware(BaseMiddleware):
    """Требует подписки на канал для использования бота."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        bot = data.get("bot")

        if not user or not bot:
            return await handler(event, data)

        # Admins проходят без проверки
        if user.id in ADMIN_IDS:
            return await handler(event, data)

        # Callback "check_subscription" обрабатывается отдельно — пропускаем
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        # Проверяем подписку
        if not await is_subscribed(user.id, bot):
            # Для команды /start новым пользователям показываем сообщение о бонусе
            is_start_command = (
                isinstance(event, Message)
                and event.text is not None
                and event.text.startswith("/start")
            )
            if is_start_command:
                text = (
                    f"👋 Привет, {user.first_name}!\n\n"
                    "🎁 <b>Подпишись на наш официальный канал и получи 7 дней VPN бесплатно!</b>\n\n"
                    f"После подписки нажми кнопку ниже — бонус активируется автоматически."
                )
            else:
                text = (
                    "💙 Чтобы пользоваться ботом, необходимо подписаться "
                    f"на наш официальный канал {CHANNEL_USERNAME}"
                )
            if isinstance(event, Message):
                await event.answer(text, reply_markup=channel_subscription_kb(), parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=channel_subscription_kb(), parse_mode="HTML")
                await event.answer()
            return None  # блокируем дальнейшую обработку

        return await handler(event, data)
