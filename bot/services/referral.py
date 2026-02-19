"""
services/referral.py — бизнес-логика реферальной системы.

Правила:
  • Новый пользователь получает 7 дней реальной подписки при регистрации.
  • Пригласивший получает +7 дней реальной подписки:
      - есть активная подписка → продлевается на 7 дней
      - подписки нет → создаётся новая на 7 дней
"""

import logging

from bot.config import REFERRAL_BONUS_DAYS
from bot.database.referrals import record_referral, mark_rewarded
from bot.database.subscriptions import get_active_subscription, create_subscription
from bot.services.marzban import marzban
from bot.database.subscriptions import extend_subscription

logger = logging.getLogger(__name__)

_MARZBAN_USERNAME = lambda uid: f"tg_{uid}"


async def handle_referral(referrer_id: int, referred_id: int) -> None:
    """
    Вызывается после успешной регистрации нового пользователя.
    Фиксирует реферала и начисляет реальную подписку пригласившему.
    """
    await record_referral(referrer_id, referred_id)

    try:
        sub = await get_active_subscription(referrer_id)

        if sub:
            # Продлеваем существующую подписку
            await extend_subscription(sub["id"], days=REFERRAL_BONUS_DAYS)
            await marzban.extend_user(sub["marzban_username"], REFERRAL_BONUS_DAYS)
            logger.info(
                "Referral reward: extended sub %s by %d days for user %s",
                sub["id"], REFERRAL_BONUS_DAYS, referrer_id,
            )
        else:
            # Подписки нет — создаём новую на REFERRAL_BONUS_DAYS дней
            username = _MARZBAN_USERNAME(referrer_id)
            try:
                await marzban.create_user(username, days=REFERRAL_BONUS_DAYS)
            except Exception:
                # Пользователь уже есть в Marzban — просто продлеваем
                await marzban.extend_user(username, REFERRAL_BONUS_DAYS)

            await create_subscription(
                user_id=referrer_id,
                marzban_username=username,
                payment_method_id=None,
                days=REFERRAL_BONUS_DAYS,
            )
            logger.info(
                "Referral reward: created %d-day subscription for user %s",
                REFERRAL_BONUS_DAYS, referrer_id,
            )

        await mark_rewarded(referred_id)

    except Exception as exc:
        logger.error("Failed to process referral reward for %s: %s", referrer_id, exc)
