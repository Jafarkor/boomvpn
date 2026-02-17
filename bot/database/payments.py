"""
database/payments.py — CRUD для таблицы payments.
"""

from datetime import datetime
from bot.database.manager import db
from bot.config import PLAN_PRICE


async def create_payment(
    user_id: int,
    yukassa_payment_id: str,
    subscription_id: int | None = None,
) -> None:
    """Сохраняет новый платёж со статусом pending."""
    async with db:
        await db.insert_data_with_update(
            table_name="payments",
            records_data={
                "user_id":            user_id,
                "yukassa_payment_id": yukassa_payment_id,
                "amount":             PLAN_PRICE,
                "status":             "pending",
                "created_at":         datetime.utcnow(),
                "subscription_id":    subscription_id,
            },
            conflict_column="yukassa_payment_id",
            update_on_conflict=False,
        )


async def get_payment_by_yukassa_id(yukassa_payment_id: str) -> dict | None:
    """Ищет платёж по ID из ЮKassa."""
    async with db:
        return await db.select_data(
            table_name="payments",
            where_dict={"yukassa_payment_id": yukassa_payment_id},
            one_dict=True,
        )


async def update_payment_status(yukassa_payment_id: str, status: str) -> None:
    """Обновляет статус платежа: pending → succeeded | canceled."""
    async with db:
        await db.update_data(
            table_name="payments",
            where_dict={"yukassa_payment_id": yukassa_payment_id},
            update_dict={"status": status},
        )


async def link_payment_to_subscription(
    yukassa_payment_id: str,
    subscription_id: int,
) -> None:
    """Привязывает платёж к подписке после её создания."""
    async with db:
        await db.update_data(
            table_name="payments",
            where_dict={"yukassa_payment_id": yukassa_payment_id},
            update_dict={"subscription_id": subscription_id},
        )


async def get_user_payments(user_id: int) -> list[dict]:
    """История платежей пользователя."""
    async with db:
        return await db.select_data(
            table_name="payments",
            where_dict={"user_id": user_id},
        )
