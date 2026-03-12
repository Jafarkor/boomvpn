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


# ──────────────────────────────────────────────────────────────────────────────
# ДОБАВИТЬ в конец bot/database/payments.py
# ──────────────────────────────────────────────────────────────────────────────
#
# Эти 3 функции заменяют in-memory словарь _pending из handlers/buy.py.
# Благодаря хранению в БД payment_id не теряется при перезапуске бота.
#
# Также нужно выполнить миграцию (один раз):
#   ALTER TABLE payments
#     ADD COLUMN IF NOT EXISTS is_pending_check BOOLEAN NOT NULL DEFAULT FALSE;
# ──────────────────────────────────────────────────────────────────────────────


async def get_pending_payment_for_user(user_id: int) -> str | None:
    """
    Возвращает yukassa_payment_id последнего незавершённого (pending) платежа
    пользователя, который ожидает ручной проверки из бота.
    """
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT yukassa_payment_id
            FROM payments
            WHERE user_id = $1
              AND status = 'pending'
              AND is_pending_check = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
    return row["yukassa_payment_id"] if row else None


async def save_pending_payment_for_user(user_id: int, yukassa_payment_id: str) -> None:
    """
    Помечает платёж как ожидающий ручной проверки.
    Сбрасывает флаг у предыдущих незавершённых платежей этого пользователя.
    """
    async with get_pool().acquire() as conn:
        # Сбрасываем старые флаги
        await conn.execute(
            """
            UPDATE payments
            SET is_pending_check = FALSE
            WHERE user_id = $1 AND status = 'pending'
            """,
            user_id,
        )
        # Устанавливаем флаг на новый платёж
        await conn.execute(
            """
            UPDATE payments
            SET is_pending_check = TRUE
            WHERE yukassa_payment_id = $1
            """,
            yukassa_payment_id,
        )


async def clear_pending_payment_for_user(user_id: int) -> None:
    """Снимает флаг ожидания после успешной/отменённой проверки."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            UPDATE payments
            SET is_pending_check = FALSE
            WHERE user_id = $1 AND is_pending_check = TRUE
            """,
            user_id,
        )