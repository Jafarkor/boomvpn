"""
services/referral.py — бизнес-логика реферальной системы.

Правила:
  • Новый пользователь получает 7 дней в подарок при регистрации.
  • Пригласивший получает +7 дней: если подписка активна — продлевается,
    если нет — дни копятся в bonus_days и применяются при следующей покупке.
"""

import logging

from bot.config import REFERRAL_BONUS_DAYS
from bot.database.referrals import record_referral, mark_rewarded
from bot.database.subscriptions import get_active_subscription, extend_subscription
from bot.database.users import add_bonus_days
from bot.services.marzban import marzban

logger = logging.getLogger(__name__)


async def handle_referral(referrer_id: int, referred_id: int) -> None:
    """
    Вызывается после успешной регистрации нового пользователя.
    Фиксирует реферала и начисляет бонус пригласившему.
    """
    await record_referral(referrer_id, referred_id)

    try:
        sub = await get_active_subscription(referrer_id)
        if sub:
            await extend_subscription(sub["id"], days=REFERRAL_BONUS_DAYS)
            await marzban.extend_user(sub["marzban_username"], REFERRAL_BONUS_DAYS)
            logger.info(
                "Referral reward: extended sub %s by %d days for user %s",
                sub["id"], REFERRAL_BONUS_DAYS, referrer_id,
            )
        else:
            await add_bonus_days(referrer_id, REFERRAL_BONUS_DAYS)
            logger.info(
                "Referral reward: added %d bonus_days to user %s",
                REFERRAL_BONUS_DAYS, referrer_id,
            )

        await mark_rewarded(referred_id)

    except Exception as exc:
        logger.error("Failed to process referral reward for %s: %s", referrer_id, exc)
