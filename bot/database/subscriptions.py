from datetime import datetime, timedelta
from bot.database.manager import get_pool
from bot.config import PLAN_DAYS


async def get_active_subscription(user_id: int) -> dict | None:
    """Возвращает активную подписку пользователя или None."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM subscriptions
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY id DESC LIMIT 1
        """, user_id)
    return dict(row) if row else None


async def create_subscription(
    user_id: int,
    marzban_username: str,
    payment_method_id: str | None = None,
) -> int:
    """Создаёт новую подписку. Возвращает id созданной записи."""
    expires_at = datetime.utcnow() + timedelta(days=PLAN_DAYS)
    async with get_pool().acquire() as conn:
        sub_id = await conn.fetchval("""
            INSERT INTO subscriptions
                (user_id, marzban_username, expires_at, is_active,
                 yukassa_payment_method_id, auto_renew)
            VALUES ($1, $2, $3, TRUE, $4, TRUE)
            RETURNING id
        """,
            user_id, marzban_username, expires_at, payment_method_id,
        )
    return sub_id


async def extend_subscription(subscription_id: int) -> None:
    """Продлевает подписку на PLAN_DAYS дней от текущего expires_at."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE subscriptions
            SET expires_at = GREATEST(expires_at, NOW()) + $1::interval,
                is_active  = TRUE
            WHERE id = $2
        """,
            f"{PLAN_DAYS} days", subscription_id,
        )


async def save_payment_method(subscription_id: int, method_id: str) -> None:
    """Сохраняет id платёжного метода ЮKassa для автопродления."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE subscriptions SET yukassa_payment_method_id = $1 WHERE id = $2",
            method_id, subscription_id,
        )


async def deactivate_subscription(subscription_id: int) -> None:
    """Деактивирует подписку."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE subscriptions SET is_active = FALSE WHERE id = $1",
            subscription_id,
        )


async def toggle_auto_renew(subscription_id: int, enabled: bool) -> None:
    """Включает/выключает автопродление."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE subscriptions SET auto_renew = $1 WHERE id = $2",
            enabled, subscription_id,
        )


async def get_expiring_subscriptions(within_hours: int = 24) -> list[dict]:
    """
    Возвращает активные подписки с auto_renew=TRUE и сохранённым методом оплаты,
    которые истекают в ближайшие within_hours часов.
    """
    threshold = datetime.utcnow() + timedelta(hours=within_hours)
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM subscriptions
            WHERE is_active = TRUE
              AND auto_renew = TRUE
              AND yukassa_payment_method_id IS NOT NULL
              AND expires_at <= $1
        """, threshold)
    return [dict(r) for r in rows]