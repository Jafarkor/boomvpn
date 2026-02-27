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
from bot.services.pasarguard import pasarguard
from bot.services.payment import charge_auto_renew
import datetime

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
        next_run_time=datetime.datetime.now(),
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
                await pasarguard.extend_user(sub["panel_username"], 0)  # заморозка
        except Exception as exc:
            logger.error("Auto-renew failed for sub %s: %s", sub["id"], exc)
