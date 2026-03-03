"""
services/scheduler.py — планировщик задач (APScheduler).

Задачи:
  • auto_renew_check      — каждый час: автопродление истекающих подписок.
  • reminder_expiring     — каждый час: напоминание за ~24 ч до конца
                            (только тем, у кого нет автопродления / метода оплаты).
  • reminder_just_expired — каждый час: уведомление в момент окончания.
  • reminder_weekly       — каждый час: напоминание через 1 и 2 недели после окончания.

Принцип идемпотентности (без изменения БД):
  Каждая задача проверяет строгое временно́е окно шириной 1 час.
  При запуске раз в час каждая подписка попадёт в окно ровно один раз.
"""

import logging
from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database.subscriptions import (
    get_expiring_subscriptions,
    deactivate_subscription,
    get_subscriptions_expiring_soon,
    get_subscriptions_just_expired,
    get_subscriptions_expired_weeks_ago,
)
from bot.keyboards.user import reminder_kb
from bot.messages import (
    reminder_expiring_soon_text,
    reminder_just_expired_text,
    reminder_week_1_text,
    reminder_week_2_text,
)
from bot.services.pasarguard import pasarguard
from bot.services.payment import charge_auto_renew

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Сколько недель слать еженедельные напоминания после окончания
_REMINDER_WEEKS = (1, 2)


def setup_scheduler(bot: Bot) -> None:
    """Инициализирует и запускает планировщик."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")

    common = dict(
        trigger="interval",
        hours=1,
        next_run_time=datetime.now(tz=timezone.utc),
    )

    _scheduler.add_job(
        _auto_renew_task,
        **common,
        id="auto_renew",
        kwargs={"bot": bot},
    )
    _scheduler.add_job(
        _reminder_expiring_task,
        **common,
        id="reminder_expiring",
        kwargs={"bot": bot},
    )
    _scheduler.add_job(
        _reminder_just_expired_task,
        **common,
        id="reminder_just_expired",
        kwargs={"bot": bot},
    )
    _scheduler.add_job(
        _reminder_weekly_task,
        **common,
        id="reminder_weekly",
        kwargs={"bot": bot},
    )

    _scheduler.start()
    logger.info("Scheduler started")


# ── Вспомогательная функция отправки ─────────────────────────────────────────

async def _send_reminder(bot: Bot, user_id: int, text: str) -> None:
    """Отправляет напоминание пользователю; подавляет любые ошибки доставки."""
    try:
        await bot.send_message(user_id, text, reply_markup=reminder_kb(), parse_mode="HTML")
    except Exception as exc:
        logger.warning("Reminder not delivered to user %s: %s", user_id, exc)


# ── Задачи ────────────────────────────────────────────────────────────────────

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


async def _reminder_expiring_task(bot: Bot) -> None:
    """
    Напоминание за ~24 часа до окончания.
    Получают только те, у кого автопродление невозможно:
      — auto_renew выключен, или
      — нет сохранённого метода оплаты (ни разу не платили через ЮKassa).
    """
    subscriptions = await get_subscriptions_expiring_soon()
    logger.info("Reminder (expiring soon): %d users", len(subscriptions))

    for sub in subscriptions:
        await _send_reminder(bot, sub["user_id"], reminder_expiring_soon_text())


async def _reminder_just_expired_task(bot: Bot) -> None:
    """Уведомление в момент, когда подписка только что истекла (окно 1 час)."""
    subscriptions = await get_subscriptions_just_expired()
    logger.info("Reminder (just expired): %d users", len(subscriptions))

    for sub in subscriptions:
        await _send_reminder(bot, sub["user_id"], reminder_just_expired_text())


async def _reminder_weekly_task(bot: Bot) -> None:
    """
    Еженедельные напоминания после окончания подписки.
    Отправляется на 1-й и 2-й неделях.
    """
    texts = {
        1: reminder_week_1_text,
        2: reminder_week_2_text,
    }
    for week in _REMINDER_WEEKS:
        subscriptions = await get_subscriptions_expired_weeks_ago(weeks=week)
        logger.info("Reminder (week %d after expiry): %d users", week, len(subscriptions))

        text = texts[week]()
        for sub in subscriptions:
            await _send_reminder(bot, sub["user_id"], text)
