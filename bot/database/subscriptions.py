"""
database/subscriptions.py — CRUD для таблицы subscriptions.
"""

from datetime import datetime, timedelta
from bot.database.manager import db
from bot.config import PLAN_DAYS


async def get_active_subscription(user_id: int) -> dict | None:
    """Возвращает активную подписку пользователя или None."""
    async with db:
        subs = await db.select_data(
            table_name="subscriptions",
            where_dict={"user_id": user_id, "is_active": True},
        )
    # Берём последнюю активную (на случай гонки, должна быть одна)
    return subs[-1] if subs else None


async def create_subscription(
    user_id: int,
    marzban_username: str,
    payment_method_id: str | None = None,
) -> int:
    """
    Создаёт новую подписку.
    Возвращает id созданной записи.
    """
    expires_at = datetime.utcnow() + timedelta(days=PLAN_DAYS)
    async with db:
        # asyncpg-lite не возвращает id после вставки → вставляем и сразу читаем
        await db.insert_data_with_update(
            table_name="subscriptions",
            records_data={
                "user_id":                  user_id,
                "marzban_username":         marzban_username,
                "expires_at":               expires_at,
                "is_active":                True,
                "yukassa_payment_method_id": payment_method_id,
                "auto_renew":               True,
            },
            conflict_column="id",
            update_on_conflict=False,
        )
        # Читаем только что созданную подписку
        subs = await db.select_data(
            table_name="subscriptions",
            where_dict={"user_id": user_id, "marzban_username": marzban_username},
        )
    # Берём последнюю запись (самую свежую)
    return subs[-1]["id"] if subs else -1


async def extend_subscription(subscription_id: int) -> None:
    """Продлевает подписку на PLAN_DAYS дней от текущего expires_at."""
    async with db:
        sub = await db.select_data(
            table_name="subscriptions",
            where_dict={"id": subscription_id},
            one_dict=True,
        )
        if not sub:
            return
        current_expires = sub["expires_at"]
        # Если подписка уже истекла — отсчёт от сегодня
        base = max(current_expires, datetime.utcnow())
        new_expires = base + timedelta(days=PLAN_DAYS)
        await db.update_data(
            table_name="subscriptions",
            where_dict={"id": subscription_id},
            update_dict={"expires_at": new_expires, "is_active": True},
        )


async def save_payment_method(subscription_id: int, method_id: str) -> None:
    """Сохраняет id платёжного метода ЮKassa для автопродления."""
    async with db:
        await db.update_data(
            table_name="subscriptions",
            where_dict={"id": subscription_id},
            update_dict={"yukassa_payment_method_id": method_id},
        )


async def deactivate_subscription(subscription_id: int) -> None:
    """Деактивирует подписку (при отмене или истечении)."""
    async with db:
        await db.update_data(
            table_name="subscriptions",
            where_dict={"id": subscription_id},
            update_dict={"is_active": False},
        )


async def toggle_auto_renew(subscription_id: int, enabled: bool) -> None:
    """Включает/выключает автопродление."""
    async with db:
        await db.update_data(
            table_name="subscriptions",
            where_dict={"id": subscription_id},
            update_dict={"auto_renew": enabled},
        )


async def get_expiring_subscriptions(within_hours: int = 24) -> list[dict]:
    """
    Возвращает активные подписки с auto_renew=True,
    которые истекают в ближайшие within_hours часов.
    Используется планировщиком для автопродления.
    """
    threshold = datetime.utcnow() + timedelta(hours=within_hours)
    async with db:
        all_active = await db.select_data(
            table_name="subscriptions",
            where_dict={"is_active": True, "auto_renew": True},
        )
    return [
        s for s in all_active
        if s["expires_at"] <= threshold and s["yukassa_payment_method_id"]
    ]
