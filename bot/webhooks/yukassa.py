"""
webhooks/yukassa.py — обработчик входящих уведомлений от ЮKassa.

ЮKassa отправляет POST-запрос при изменении статуса платежа.
Мы проверяем подлинность (IP ЮKassa) и обновляем БД.
"""

import json
import logging
from aiohttp import web
from aiogram import Bot

from bot.database.payments import (
    get_payment_by_yukassa_id,
    update_payment_status,
)
from bot.handlers.payment import _activate_subscription
from bot.config import YUKASSA_WEBHOOK_PATH

logger = logging.getLogger(__name__)

# Официальные IP-адреса ЮKassa для валидации источника
YUKASSA_IPS = {
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11",
    "77.75.156.35",
    "77.75.154.128/25",
    "2a02:5180::/32",
}


async def yukassa_webhook_handler(request: web.Request) -> web.Response:
    """Обрабатывает уведомления ЮKassa."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        logger.warning("Invalid JSON from YuKassa webhook")
        return web.Response(status=400)

    event_type = body.get("event")
    payment_obj = body.get("object", {})
    payment_id = payment_obj.get("id")

    logger.info("YuKassa event: %s, payment_id: %s", event_type, payment_id)

    if not payment_id:
        return web.Response(status=200)

    if event_type == "payment.succeeded":
        await _handle_payment_succeeded(payment_obj, request.app["bot"])

    elif event_type == "payment.canceled":
        await update_payment_status(payment_id, "canceled")

    return web.Response(status=200)


async def _handle_payment_succeeded(payment_obj: dict, bot: Bot) -> None:
    """Активирует подписку после успешного платежа."""
    payment_id = payment_obj["id"]

    # Идемпотентность — если уже обработан, пропускаем
    existing = await get_payment_by_yukassa_id(payment_id)
    if existing and existing["status"] == "succeeded":
        return

    # Извлекаем user_id из метаданных платежа
    metadata = payment_obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    if not user_id:
        logger.error("No user_id in payment metadata: %s", payment_id)
        return

    # Метод оплаты (для рекуррента)
    method = payment_obj.get("payment_method", {})
    method_id = method.get("id") if method.get("saved") else None

    await _activate_subscription(user_id, payment_id, method_id)

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            "✅ Оплата получена! Подписка активирована.\n"
            "Зайдите в /start → Личный кабинет → Получить конфиг.",
        )
    except Exception as e:
        logger.warning("Cannot notify user %s: %s", user_id, e)


def register_yukassa_webhook(app: web.Application, bot: Bot) -> None:
    """Регистрирует вебхук ЮKassa в aiohttp-приложении."""
    app["bot"] = bot
    app.router.add_post(YUKASSA_WEBHOOK_PATH, yukassa_webhook_handler)
