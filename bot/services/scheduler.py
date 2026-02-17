"""
services/scheduler.py — APScheduler для фоновых задач.

Задачи:
  1. check_expiring — каждые 6 часов ищет подписки, истекающие через 24 ч,
     и запускает автопродление.
  2. deactivate_expired — каждый час отключает истёкшие подписки в Marzban.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from bot.database.subscriptions import (
    get_expiring_subscriptions,
    extend_subscription,
    deactivate_subscription,
    get_active_subscription,
)
from bot.database.payments import create_payment, update_payment_status
from bot.services.yukassa import create_recurring_payment
from bot.services.marzban import marzban

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def _renew_subscription(sub: dict, bot: Bot) -> None:
    """Пытается продлить одну подписку через рекуррентный платёж."""
    user_id = sub["user_id"]
    method_id = sub["yukassa_payment_method_id"]

    try:
        payment_data = create_recurring_payment(user_id, method_id)
        payment_id = payment_data["id"]
        await create_payment(user_id, payment_id, sub["id"])

        # ЮKassa для рекуррентных платежей часто сразу succeeded
        if payment_data["status"] == "succeeded":
            await _on_payment_success(payment_id, sub, bot)
        else:
            # Статус придёт вебхуком — ждём
            logger.info("Recurring payment %s for user %s pending", payment_id, user_id)
    except Exception as e:
        logger.error("Failed to renew sub %s: %s", sub["id"], e)
        await bot.send_message(
            user_id,
            "⚠️ Не удалось продлить подписку автоматически.\n"
            "Пожалуйста, продлите её вручную через /start → Личный кабинет.",
        )


async def _on_payment_success(payment_id: str, sub: dict, bot: Bot) -> None:
    """Обновляет БД и Marzban после успешного рекуррентного платежа."""
    await update_payment_status(payment_id, "succeeded")
    await extend_subscription(sub["id"])
    await marzban.extend_user(sub["marzban_username"])
    try:
        await bot.send_message(sub["user_id"], "✅ Подписка автоматически продлена!")
    except Exception:
        pass  # Пользователь мог заблокировать бота


async def _deactivate_expired(bot: Bot) -> None:
    """Деактивирует истёкшие подписки."""
    # Берём все активные с auto_renew=False или без метода оплаты
    from bot.database.manager import db

    async with db:
        all_active = await db.select_data(
            table_name="subscriptions",
            where_dict={"is_active": True},
        )

    now = datetime.utcnow()
    for sub in all_active:
        if sub["expires_at"] < now:
            await deactivate_subscription(sub["id"])
            await marzban.delete_user(sub["marzban_username"])
            try:
                await bot.send_message(
                    sub["user_id"],
                    "❌ Ваша подписка истекла. Для продления нажмите /start.",
                )
            except Exception:
                pass


def setup_scheduler(bot: Bot) -> None:
    """Регистрирует задачи и запускает планировщик."""

    async def job_renew():
        subs = await get_expiring_subscriptions(within_hours=24)
        for sub in subs:
            await _renew_subscription(sub, bot)

    async def job_deactivate():
        await _deactivate_expired(bot)

    scheduler.add_job(job_renew,     "interval", hours=6,   id="renew")
    scheduler.add_job(job_deactivate,"interval", hours=1,   id="deactivate")
    scheduler.start()
    logger.info("Scheduler started")
