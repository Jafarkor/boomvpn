"""
utils/channel.py — проверка подписки пользователя на Telegram-канал.
"""

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from bot.config import CHANNEL_USERNAME

logger = logging.getLogger(__name__)


async def is_subscribed(user_id: int, bot: Bot) -> bool:
    """Возвращает True, если пользователь подписан на CHANNEL_USERNAME."""
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        logger.debug("Subscription check user=%s status=%s", user_id, member.status)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except Exception as exc:
        logger.error("is_subscribed error user=%s: %s", user_id, exc)
        return False
