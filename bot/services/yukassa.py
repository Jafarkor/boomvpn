"""
services/yukassa.py — работа с ЮKassa API.

Используем официальный SDK yookassa.
Рекуррент реализован через сохранение payment_method_id
после первого успешного платежа.
"""

import uuid
from yookassa import Configuration, Payment
from yookassa.domain.models import PaymentMethodType

from bot.config import (
    YUKASSA_SHOP_ID,
    YUKASSA_SECRET_KEY,
    YUKASSA_WEBHOOK_PATH,
    WEBHOOK_HOST,
    PLAN_PRICE,
    PLAN_NAME,
)

# Инициализируем SDK при импорте модуля
Configuration.configure(
    account_id=YUKASSA_SHOP_ID,
    secret_key=YUKASSA_SECRET_KEY,
)

# URL, куда ЮKassa будет слать уведомления
_RETURN_URL = f"{WEBHOOK_HOST}/payment-done"


def _idempotency_key() -> str:
    """Уникальный ключ идемпотентности для каждого запроса."""
    return str(uuid.uuid4())


def create_first_payment(user_id: int, description: str | None = None) -> dict:
    """
    Создаёт первый платёж с сохранением метода оплаты (рекуррент).
    Пользователь платит через СБП.
    Возвращает dict с ключами: id, confirmation_url.
    """
    payment = Payment.create(
        {
            "amount": {
                "value": str(PLAN_PRICE),
                "currency": "RUB",
            },
            "payment_method_data": {
                "type": PaymentMethodType.SBP,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": _RETURN_URL,
            },
            # Флаг — сохранить метод для будущих списаний
            "save_payment_method": True,
            "capture": True,
            "description": description or f"{PLAN_NAME} — первая оплата",
            "metadata": {"user_id": str(user_id)},
        },
        _idempotency_key(),
    )
    return {
        "id":               payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
        "status":           payment.status,
    }


def create_recurring_payment(
    user_id: int,
    payment_method_id: str,
) -> dict:
    """
    Создаёт рекуррентный платёж по сохранённому методу.
    Не требует действий от пользователя (автосписание).
    """
    payment = Payment.create(
        {
            "amount": {
                "value": str(PLAN_PRICE),
                "currency": "RUB",
            },
            "payment_method_id": payment_method_id,
            "capture": True,
            "description": f"{PLAN_NAME} — автопродление",
            "metadata": {"user_id": str(user_id), "recurring": "true"},
        },
        _idempotency_key(),
    )
    return {
        "id":     payment.id,
        "status": payment.status,
    }


def get_payment(payment_id: str) -> dict:
    """
    Получает актуальный статус платежа из ЮKassa.
    Возвращает dict с полями: id, status, payment_method_id, saved.
    """
    payment = Payment.find_one(payment_id)
    method = payment.payment_method
    return {
        "id":                payment.id,
        "status":            payment.status,
        # ID метода оплаты (заполняется, если save_payment_method=True)
        "payment_method_id": method.id if method else None,
        # Флаг — метод действительно сохранён (прошёл верификацию)
        "saved":             method.saved if method else False,
    }
