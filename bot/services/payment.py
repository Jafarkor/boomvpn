"""
services/payment.py — работа с ЮKassa.

Создаёт платёжные ссылки и обрабатывает автосписания.
"""

import logging
import uuid
from typing import Any

from yookassa import Configuration, Payment as YkPayment

from bot.config import YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY, PLAN_PRICE, PLAN_NAME, WEBHOOK_HOST
from bot.database.payments import create_payment, update_payment_status, link_payment_to_subscription
from bot.database.subscriptions import extend_subscription
from bot.services.pasarguard import pasarguard

logger = logging.getLogger(__name__)

Configuration.account_id = YUKASSA_SHOP_ID
Configuration.secret_key = YUKASSA_SECRET_KEY

RETURN_URL = f"{WEBHOOK_HOST}/payment/success"


async def create_payment_link(user_id: int) -> tuple[str, str | None]:
    """
    Создаёт платёж в ЮKassa.

    Логика выбора сценария:
    1. Есть сохранённый payment_method_id → прямое списание (без редиректа).
       Возвращает (payment_id, None).
    2. Есть активная подписка, но нет payment_method_id (метод не был сохранён
       при первой оплате) → новый СБП-платёж БЕЗ save_payment_method, чтобы
       ЮKасса не выдавала ошибку "счёт уже привязан".
       Возвращает (payment_id, confirmation_url).
    3. Нет активной подписки (первая оплата) → СБП с save_payment_method=True.
       Возвращает (payment_id, confirmation_url).
    """
    from bot.database.subscriptions import get_active_subscription  # local import to avoid circular

    existing_sub = await get_active_subscription(user_id)
    saved_method_id = existing_sub.get("yukassa_payment_method_id") if existing_sub else None

    idempotency_key = str(uuid.uuid4())

    if saved_method_id:
        # ── Сценарий 1: прямое списание через сохранённый СБП-метод ──────────
        payment = YkPayment.create(
            {
                "amount": {"value": f"{PLAN_PRICE}.00", "currency": "RUB"},
                "capture": True,
                "payment_method_id": saved_method_id,
                "description": f"{PLAN_NAME} (продление) — {user_id}",
                "metadata": {"user_id": str(user_id)},
            },
            idempotency_key,
        )
        await create_payment(user_id, payment.id)
        return payment.id, None

    elif existing_sub:
        # ── Сценарий 2: продление без привязки ───────────────────────────────
        # У пользователя уже есть подписка, но payment_method_id не сохранился
        # (вебхук не пришёл вовремя / банк не поддерживал автоплатёж).
        # Делаем обычный СБП-платёж БЕЗ save_payment_method, чтобы ЮКасса
        # не жаловалась на «счёт уже привязан».
        payment = YkPayment.create(
            {
                "amount": {"value": f"{PLAN_PRICE}.00", "currency": "RUB"},
                "payment_method_data": {"type": "sbp"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": RETURN_URL,
                },
                "capture": True,
                "save_payment_method": False,
                "description": f"{PLAN_NAME} (продление) — {user_id}",
                "metadata": {"user_id": str(user_id)},
            },
            idempotency_key,
        )
        await create_payment(user_id, payment.id)
        return payment.id, payment.confirmation.confirmation_url

    else:
        # ── Сценарий 3: первая оплата — редирект + сохраняем метод ───────────
        payment = YkPayment.create(
            {
                "amount": {"value": f"{PLAN_PRICE}.00", "currency": "RUB"},
                "payment_method_data": {"type": "sbp"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": RETURN_URL,
                },
                "capture": True,
                "save_payment_method": True,
                "description": f"{PLAN_NAME} — {user_id}",
                "metadata": {"user_id": str(user_id)},
            },
            idempotency_key,
        )
        await create_payment(user_id, payment.id)
        return payment.id, payment.confirmation.confirmation_url


async def charge_auto_renew(sub: dict[str, Any], bot: Any) -> bool:
    """
    Списывает оплату за автопродление.
    Возвращает True при успехе.
    """
    if not sub.get("yukassa_payment_method_id"):
        return False

    try:
        idempotency_key = str(uuid.uuid4())
        payment = YkPayment.create(
            {
                "amount": {"value": f"{PLAN_PRICE}.00", "currency": "RUB"},
                "capture": True,
                "payment_method_id": sub["yukassa_payment_method_id"],
                "description": f"Автопродление VPN — sub {sub['id']}",
                "metadata": {"user_id": str(sub["user_id"]), "sub_id": str(sub["id"])},
            },
            idempotency_key,
        )

        if payment.status == "succeeded":
            await update_payment_status(payment.id, "succeeded")
            await extend_subscription(sub["id"])
            await pasarguard.extend_user(sub["panel_username"], 30)

            try:
                await bot.send_message(
                    sub["user_id"],
                    "✅ Подписка автоматически продлена на 30 дней.",
                )
            except Exception:
                pass

            return True

    except Exception as exc:
        logger.error("Auto-renew payment failed for sub %s: %s", sub["id"], exc)

    return False
