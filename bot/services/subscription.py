"""
services/subscription.py — создание и продление подписок.

PasarGuard и БД всегда обновляются вместе в одном вызове.

subscription_url запрашивается из PasarGuard только один раз — при создании подписки —
и сохраняется в БД. При последующих обращениях URL берётся из БД.

ВАЖНО: порядок операций при создании новой подписки:
  1. Сначала PasarGuard (create/extend)
  2. Потом DB (create_subscription)
Это гарантирует что если PasarGuard падает — DB не обновляется,
и следующая попытка оплаты пройдёт корректно.

При продлении существующей подписки порядок:
  1. PasarGuard extend
  2. DB extend
Если PasarGuard падает при продлении — логируем ошибку, но НЕ бросаем исключение,
чтобы пользователь не видел "ошибку создания подписки" когда DB уже обновлена.
"""

import logging

from bot.config import PLAN_DAYS, GIFT_DAYS
from bot.database.manager import get_pool
from bot.database.subscriptions import (
    create_subscription,
    extend_subscription,
    get_active_subscription,
)
from bot.services.pasarguard import pasarguard

logger = logging.getLogger(__name__)


def _panel_username(user_id: int) -> str:
    """Детерминированный логин в PasarGuard по Telegram user_id: tg_{user_id}."""
    return f"tg_{user_id}"


async def create_gift_subscription(user_id: int) -> str:
    """
    Создаёт подарочную подписку на GIFT_DAYS дней.
    Возвращает ссылку подписки.
    """
    username = _panel_username(user_id)

    # 1. PasarGuard (сначала!)
    await pasarguard.ensure_user(username, days=GIFT_DAYS)
    url = await pasarguard.get_subscription_url(username)

    # 2. DB
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

    Для новой подписки: сначала PasarGuard, потом DB.
    Для продления: сначала PasarGuard, потом DB. Если PasarGuard падает при
    продлении — ошибка логируется, но подписка считается успешной (DB уже актуальна).
    """
    username = _panel_username(user_id)
    existing = await get_active_subscription(user_id)

    if existing:
        # ── Продление существующей подписки ───────────────────────────────────
        # 1. PasarGuard
        try:
            await pasarguard.extend_user(username, PLAN_DAYS)
        except Exception as pg_exc:
            # PasarGuard упал, но DB будет обновлена — логируем и продолжаем.
            # Пользователь получит подписку в DB; PasarGuard нужно проверить вручную.
            logger.error(
                "PasarGuard extend_user FAILED for user %s (panel: %s): %s — "
                "DB will be updated anyway. Check PasarGuard manually.",
                user_id, username, pg_exc,
            )

        # 2. DB
        await extend_subscription(existing["id"], days=PLAN_DAYS)

        # Возвращаем сохранённый URL; если нет — запрашиваем из PasarGuard
        url = existing.get("subscription_url")
        if not url:
            try:
                url = await pasarguard.get_subscription_url(username)
                # Сохраняем на будущее
                async with get_pool().acquire() as conn:
                    await conn.execute(
                        "UPDATE subscriptions SET subscription_url = $1 WHERE id = $2",
                        url, existing["id"],
                    )
            except Exception:
                url = ""

    else:
        # ── Новая подписка ────────────────────────────────────────────────────
        # 1. PasarGuard (сначала! если упадёт — DB не трогаем)
        await pasarguard.ensure_user(username, days=PLAN_DAYS)
        url = await pasarguard.get_subscription_url(username)

        # 2. DB
        await create_subscription(
            user_id=user_id,
            panel_username=username,
            payment_method_id=payment_method_id,
            auto_renew=payment_method_id is not None,
            subscription_url=url,
        )

    logger.info("Paid subscription processed for user %s (%d days)", user_id, PLAN_DAYS)
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

    # Fallback для подписок без subscription_url в DB
    logger.warning(
        "subscription_url missing in DB for user %s, fetching from PasarGuard", user_id
    )
    return await pasarguard.get_subscription_url(sub["panel_username"])
