"""
services/subscription.py — создание и продление подписок.

PasarGuard и БД всегда обновляются вместе в одном вызове.
"""

import logging

from bot.config import PLAN_DAYS, GIFT_DAYS
from bot.database.subscriptions import (
    create_subscription,
    extend_subscription,
    get_active_subscription,
)
from bot.services.pasarguard import pasarguard

logger = logging.getLogger(__name__)


def _panel_username(user_id: int) -> str:
    """Детерминированный логин в PasarGuard по Telegram user_id."""
    return f"tg_{user_id}"


async def _ensure_panel_user(username: str, days: int) -> None:
    """
    Создаёт пользователя в PasarGuard или продлевает срок если уже существует.

    ValueError (409 — пользователь уже есть) перехватываем и продлеваем.
    Все остальные ошибки пробрасываем наверх.
    """
    try:
        await pasarguard.create_user(username, days=days)
    except ValueError:
        logger.info("PasarGuard user '%s' exists, extending instead", username)
        await pasarguard.extend_user(username, days)


async def create_gift_subscription(user_id: int) -> str:
    """
    Создаёт подарочную подписку на GIFT_DAYS дней.

    Возвращает ссылку подписки.
    """
    username = _panel_username(user_id)

    await _ensure_panel_user(username, days=GIFT_DAYS)
    await create_subscription(
        user_id=user_id,
        panel_username=username,
        days=GIFT_DAYS,
        auto_renew=False,
    )

    url = await pasarguard.get_subscription_url(username)
    logger.info("Gift subscription created for user %s (%d days)", user_id, GIFT_DAYS)
    return url


async def create_paid_subscription(
    user_id: int, payment_method_id: str | None = None
) -> str:
    """
    Создаёт или продлевает платную подписку на PLAN_DAYS дней.
    Возвращает ссылку подписки.
    """
    username = _panel_username(user_id)
    existing = await get_active_subscription(user_id)

    if existing:
        await extend_subscription(existing["id"], days=PLAN_DAYS)
        await pasarguard.extend_user(username, PLAN_DAYS)
    else:
        await _ensure_panel_user(username, days=PLAN_DAYS)
        await create_subscription(
            user_id=user_id,
            panel_username=username,
            payment_method_id=payment_method_id,
            auto_renew=payment_method_id is not None,
        )

    url = await pasarguard.get_subscription_url(username)
    logger.info("Paid subscription for user %s (%d days)", user_id, PLAN_DAYS)
    return url
