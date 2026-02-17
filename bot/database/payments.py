from datetime import datetime
from bot.database.manager import get_pool
from bot.config import PLAN_PRICE


async def create_payment(
    user_id: int,
    yukassa_payment_id: str,
    subscription_id: int | None = None,
) -> None:
    """Сохраняет новый платёж со статусом pending."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO payments
                (user_id, yukassa_payment_id, amount, status, created_at, subscription_id)
            VALUES ($1, $2, $3, 'pending', $4, $5)
            ON CONFLICT (yukassa_payment_id) DO NOTHING
        """,
            user_id, yukassa_payment_id, PLAN_PRICE, datetime.utcnow(), subscription_id,
        )


async def get_payment_by_yukassa_id(yukassa_payment_id: str) -> dict | None:
    """Ищет платёж по ID из ЮKassa."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM payments WHERE yukassa_payment_id = $1",
            yukassa_payment_id,
        )
    return dict(row) if row else None


async def update_payment_status(yukassa_payment_id: str, status: str) -> None:
    """Обновляет статус платежа: pending → succeeded | canceled."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE payments SET status = $1 WHERE yukassa_payment_id = $2",
            status, yukassa_payment_id,
        )


async def link_payment_to_subscription(
    yukassa_payment_id: str,
    subscription_id: int,
) -> None:
    """Привязывает платёж к подписке."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE payments SET subscription_id = $1 WHERE yukassa_payment_id = $2",
            subscription_id, yukassa_payment_id,
        )


async def get_user_payments(user_id: int) -> list[dict]:
    """История платежей пользователя."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return [dict(r) for r in rows]