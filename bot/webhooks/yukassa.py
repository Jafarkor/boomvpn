"""
webhooks/yukassa.py — обработчик вебхуков ЮKassa.

ЮKassa присылает уведомления о статусе платежей на этот эндпоинт.
"""

import json
import logging

from aiohttp import web
from aiogram import Bot

from bot.config import YUKASSA_WEBHOOK_PATH
from bot.database.payments import get_payment_by_yukassa_id, update_payment_status, link_payment_to_subscription
from bot.services.subscription import create_paid_subscription

logger = logging.getLogger(__name__)


async def yukassa_webhook_handler(request: web.Request) -> web.Response:
    """Принимает POST от ЮKassa и обрабатывает событие."""
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    event_type = body.get("event")
    obj = body.get("object", {})

    if event_type != "payment.succeeded":
        # Нас интересуют только успешные платежи
        return web.Response(status=200)

    payment_id = obj.get("id")
    if not payment_id:
        return web.Response(status=400, text="No payment id")

    payment = await get_payment_by_yukassa_id(payment_id)
    if not payment:
        logger.warning("Unknown payment from YK webhook: %s", payment_id)
        return web.Response(status=200)

    if payment.get("status") == "succeeded":
        # Уже обработан
        return web.Response(status=200)

    user_id = payment["user_id"]
    method_id = obj.get("payment_method", {}).get("id") if obj.get("payment_method", {}).get("saved") else None

    await update_payment_status(payment_id, "succeeded")

    try:
        sub_id, _ = await create_paid_subscription(user_id, payment_method_id=method_id)
        await link_payment_to_subscription(payment_id, sub_id)

        bot: Bot = request.app["bot"]
        await bot.send_message(
            user_id,
            "✅ <b>Оплата подтверждена!</b>\n\nПодписка активирована. Открой /menu чтобы получить ссылку.",
        )
    except Exception as exc:
        logger.error("Failed to process payment %s: %s", payment_id, exc)

    return web.Response(status=200)


def register_yukassa_webhook(app: web.Application, bot: Bot) -> None:
    """Регистрирует маршрут вебхука ЮKassa в aiohttp-приложении."""
    app["bot"] = bot
    app.router.add_post(YUKASSA_WEBHOOK_PATH, yukassa_webhook_handler)
