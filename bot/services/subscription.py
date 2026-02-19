"""
services/subscription.py — бизнес-логика подписок.

Отвечает за создание, продление и отмену подписок.
Marzban + БД всегда обновляются вместе.
"""

import logging
from datetime import datetime, timedelta

from bot.config import PLAN_DAYS, GIFT_DAYS
from bot.database.subscriptions import (
    create_subscription,
    extend_subscription as db_extend,
    get_active_subscription,
)
from bot.services.marzban import marzban

logger = logging.getLogger(__name__)


def _marzban_username(user_id: int) -> str:
    """Генерирует уникальный логин Marzban для пользователя."""
    return f"tg_{user_id}"


async def create_gift_subscription(user_id: int) -> tuple[int, str]:
    """
    Создаёт подарочную подписку на GIFT_DAYS дней.
    Возвращает (subscription_id, subscription_url).
    """
    username = _marzban_username(user_id)
    mz_user = await marzban.create_user(username, days=GIFT_DAYS)
    sub_id = await create_subscription(
        user_id=user_id,
        marzban_username=mz_user["username"],
        payment_method_id=None,
        days=GIFT_DAYS,
    )
    url = await marzban.get_subscription_url(mz_user["username"])
    logger.info("Gift subscription created for user %s, sub_id=%s", user_id, sub_id)
    return sub_id, url


async def create_paid_subscription(
    user_id: int, payment_method_id: str | None = None
) -> tuple[int, str]:
    """
    Создаёт или продлевает платную подписку на PLAN_DAYS дней.
    Возвращает (subscription_id, subscription_url).
    """
    total_days = PLAN_DAYS
    username = _marzban_username(user_id)

    existing = await get_active_subscription(user_id)

    if existing:
        await db_extend(existing["id"], days=total_days)
        await marzban.extend_user(username, total_days)
        sub_id = existing["id"]
    else:
        try:
            mz_user = await marzban.create_user(username, days=total_days)
        except Exception:
            # Пользователь уже есть в Marzban — просто продлеваем
            await marzban.extend_user(username, total_days)
            mz_user = {"username": username}

        sub_id = await create_subscription(
            user_id=user_id,
            marzban_username=mz_user["username"],
            payment_method_id=payment_method_id,
        )

    url = await marzban.get_subscription_url(username)
    logger.info(
        "Paid subscription for user %s: sub_id=%s, days=%d", user_id, sub_id, total_days
    )
    return sub_id, url
