"""
services/referral.py — бизнес-логика реферальной системы.

Правила:
  • Пригласивший получает +REFERRAL_BONUS_DAYS дней реальной подписки:
      - есть активная подписка → продлевается
      - подписки нет → создаётся новая
"""

import logging

from aiogram import Bot

from bot.config import REFERRAL_BONUS_DAYS
from bot.database.referrals import record_referral, mark_rewarded
from bot.database.subscriptions import (
    get_active_subscription,
    create_subscription,
    extend_subscription,
)
from bot.messages import referral_reward_text
from bot.services.pasarguard import pasarguard

logger = logging.getLogger(__name__)


def _panel_username(user_id: int) -> str:
    return f"tg_{user_id}"


async def _grant_subscription(referrer_id: int) -> None:
    """Выдаёт или продлевает реальную подписку рефереру."""
    sub = await get_active_subscription(referrer_id)

    if sub:
        await extend_subscription(sub["id"], days=REFERRAL_BONUS_DAYS)
        await pasarguard.extend_user(sub["panel_username"], REFERRAL_BONUS_DAYS)
        logger.info("Referral: extended sub %s by %d days for user %s",
                    sub["id"], REFERRAL_BONUS_DAYS, referrer_id)
    else:
        username = _panel_username(referrer_id)
        try:
            await pasarguard.create_user(username, days=REFERRAL_BONUS_DAYS)
        except ValueError:
            # Пользователь уже есть в PasarGuard (409) — только продлеваем срок.
            await pasarguard.extend_user(username, REFERRAL_BONUS_DAYS)

        await create_subscription(
            user_id=referrer_id,
            panel_username=username,
            payment_method_id=None,
            days=REFERRAL_BONUS_DAYS,
            auto_renew=False,
        )
        logger.info("Referral: created %d-day subscription for user %s",
                    REFERRAL_BONUS_DAYS, referrer_id)


async def handle_referral(referrer_id: int, referred_id: int, bot: Bot) -> None:
    """
    Вызывается после регистрации нового пользователя.
    Фиксирует реферала, выдаёт подписку рефереру и отправляет ему уведомление.
    """
    await record_referral(referrer_id, referred_id)

    try:
        await _grant_subscription(referrer_id)
        await mark_rewarded(referred_id)

        await bot.send_message(
            referrer_id,
            referral_reward_text(REFERRAL_BONUS_DAYS),
        )
    except Exception as exc:
        logger.error("Failed to process referral reward for %s: %s", referrer_id, exc)
