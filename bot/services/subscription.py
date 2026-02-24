"""
services/subscription.py — создание и продление подписок.

PasarGuard и БД всегда обновляются вместе в одном вызове.

ИСПРАВЛЕНИЕ: subscription_url теперь запрашивается из PasarGuard только один раз —
при создании подписки — и сохраняется в БД. При последующих обращениях (нажатие
"Подключить VPN", продление) URL берётся из БД. Это гарантирует, что пользователь
всегда видит одну и ту же ссылку, даже если PasarGuard изменил токен после PUT-запроса.
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

    # Запрашиваем URL один раз и сохраняем в БД
    url = await pasarguard.get_subscription_url(username)

    await create_subscription(
        user_id=user_id,
        panel_username=username,
        days=GIFT_DAYS,
        auto_renew=False,
        subscription_url=url,
    )

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
        # При продлении возвращаем сохранённый URL — не перезапрашиваем из панели,
        # т.к. PUT может изменить токен в subscription_url
        url = existing.get("subscription_url") or await pasarguard.get_subscription_url(username)
    else:
        await _ensure_panel_user(username, days=PLAN_DAYS)
        # Запрашиваем URL один раз и сохраняем в БД
        url = await pasarguard.get_subscription_url(username)
        await create_subscription(
            user_id=user_id,
            panel_username=username,
            payment_method_id=payment_method_id,
            auto_renew=payment_method_id is not None,
            subscription_url=url,
        )

    logger.info("Paid subscription for user %s (%d days)", user_id, PLAN_DAYS)
    return url


async def get_subscription_url(user_id: int) -> str | None:
    """
    Возвращает сохранённую ссылку подписки для пользователя.
    Если в БД нет — запрашивает из PasarGuard (fallback для старых записей).
    """
    sub = await get_active_subscription(user_id)
    if not sub:
        return None

    url = sub.get("subscription_url")
    if url:
        return url

    # Fallback для подписок, созданных до добавления колонки subscription_url
    logger.warning(
        "subscription_url missing in DB for user %s, fetching from PasarGuard", user_id
    )
    return await pasarguard.get_subscription_url(sub["panel_username"])
