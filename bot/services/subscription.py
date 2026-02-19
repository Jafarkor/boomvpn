"""
services/subscription.py — создание и продление подписок.

Marzban и БД всегда обновляются вместе в одном вызове.
"""

import logging

from bot.config import PLAN_DAYS, GIFT_DAYS
from bot.database.subscriptions import (
    create_subscription,
    extend_subscription,
    get_active_subscription,
)
from bot.services.marzban import marzban

logger = logging.getLogger(__name__)


def _marzban_username(user_id: int) -> str:
    """Детерминированный логин в Marzban по Telegram user_id."""
    return f"tg_{user_id}"


async def create_gift_subscription(user_id: int) -> str:
    """
    Создаёт подарочную подписку на GIFT_DAYS дней.
    Возвращает ссылку подписки.
    """
    username = _marzban_username(user_id)
    mz_user = await marzban.create_user(username, days=GIFT_DAYS)
    await create_subscription(
        user_id=user_id,
        marzban_username=mz_user["username"],
        days=GIFT_DAYS,
    )
    url = await marzban.get_subscription_url(mz_user["username"])
    logger.info("Gift subscription created for user %s (%d days)", user_id, GIFT_DAYS)
    return url


async def create_paid_subscription(
    user_id: int, payment_method_id: str | None = None
) -> str:
    """
    Создаёт или продлевает платную подписку на PLAN_DAYS дней.
    Возвращает ссылку подписки.
    """
    username = _marzban_username(user_id)
    existing = await get_active_subscription(user_id)

    if existing:
        await extend_subscription(existing["id"], days=PLAN_DAYS)
        await marzban.extend_user(username, PLAN_DAYS)
    else:
        try:
            mz_user = await marzban.create_user(username, days=PLAN_DAYS)
            username = mz_user["username"]
        except Exception:
            # Пользователь уже есть в Marzban — продлеваем без пересоздания
            await marzban.extend_user(username, PLAN_DAYS)

        await create_subscription(
            user_id=user_id,
            marzban_username=username,
            payment_method_id=payment_method_id,
        )

    url = await marzban.get_subscription_url(username)
    logger.info("Paid subscription for user %s (%d days)", user_id, PLAN_DAYS)
    return url
