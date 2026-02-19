"""
services/scheduler.py — планировщик задач (APScheduler).

Задачи:
  • auto_renew_check — каждый час проверяет истекающие подписки
    и списывает оплату через ЮKassa.
"""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database.subscriptions import get_expiring_subscriptions, deactivate_subscription
from bot.services.marzban import marzban
from bot.services.payment import charge_auto_renew

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def setup_scheduler(bot: Bot) -> None:
    """Инициализирует и запускает планировщик."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _auto_renew_task,
        trigger="interval",
        hours=1,
        id="auto_renew",
        kwargs={"bot": bot},
    )
    _scheduler.start()
    logger.info("Scheduler started")


async def _auto_renew_task(bot: Bot) -> None:
    """Продлевает подписки с автопродлением у которых осталось < 24 ч."""
    subscriptions = await get_expiring_subscriptions(within_hours=24)
    logger.info("Auto-renew check: %d subscriptions to process", len(subscriptions))

    for sub in subscriptions:
        try:
            success = await charge_auto_renew(sub, bot=bot)
            if not success:
                await deactivate_subscription(sub["id"])
                await marzban.extend_user(sub["marzban_username"], 0)  # заморозка
        except Exception as exc:
            logger.error("Auto-renew failed for sub %s: %s", sub["id"], exc)
