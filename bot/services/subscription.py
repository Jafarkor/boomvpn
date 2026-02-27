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
    reactivate_subscription,
    get_active_subscription,
    get_any_subscription,
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
    Создаёт, продлевает или реактивирует платную подписку на PLAN_DAYS дней.
    Возвращает ссылку подписки.

    Логика:
    - Есть активная подписка → продлить (extend).
    - Есть неактивная подписка → реактивировать (reactivate), PasarGuard-пользователь уже существует.
    - Нет ни одной подписки → создать с нуля (create).

    Подписка создаётся ОДИН РАЗ в жизни пользователя.
    При последующих покупках всегда переиспользуется существующая запись и существующий
    PasarGuard-пользователь — ссылка VPN у пользователя остаётся прежней.
    """
    username = _panel_username(user_id)
    existing = await get_active_subscription(user_id)

    if existing:
        # ── Продление активной подписки ───────────────────────────────────────
        try:
            await pasarguard.extend_user(username, PLAN_DAYS)
        except Exception as pg_exc:
            logger.error(
                "PasarGuard extend_user FAILED for user %s (panel: %s): %s — "
                "DB will be updated anyway. Check PasarGuard manually.",
                user_id, username, pg_exc,
            )

        await extend_subscription(existing["id"], days=PLAN_DAYS)

        url = existing.get("subscription_url")
        if not url:
            try:
                url = await pasarguard.get_subscription_url(username)
                async with get_pool().acquire() as conn:
                    await conn.execute(
                        "UPDATE subscriptions SET subscription_url = $1 WHERE id = $2",
                        url, existing["id"],
                    )
            except Exception:
                url = ""

    else:
        any_sub = await get_any_subscription(user_id)

        if any_sub:
            # ── Реактивация существующей (истёкшей) подписки ─────────────────
            # PasarGuard-пользователь уже создан — просто продлеваем его.
            # Ссылка VPN у пользователя остаётся прежней.
            try:
                await pasarguard.extend_user(username, PLAN_DAYS)
            except Exception as pg_exc:
                logger.error(
                    "PasarGuard extend_user FAILED during reactivation for user %s: %s",
                    user_id, pg_exc,
                )

            await reactivate_subscription(
                any_sub["id"],
                payment_method_id=payment_method_id,
                days=PLAN_DAYS,
            )

            # URL берём из старой записи; если нет — запрашиваем из PasarGuard
            url = any_sub.get("subscription_url")
            if not url:
                try:
                    url = await pasarguard.get_subscription_url(username)
                    async with get_pool().acquire() as conn:
                        await conn.execute(
                            "UPDATE subscriptions SET subscription_url = $1 WHERE id = $2",
                            url, any_sub["id"],
                        )
                except Exception:
                    url = ""

            logger.info("Reactivated subscription %s for user %s", any_sub["id"], user_id)

        else:
            # ── Первая покупка — создаём с нуля ──────────────────────────────
            await pasarguard.ensure_user(username, days=PLAN_DAYS)
            url = await pasarguard.get_subscription_url(username)

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
