from datetime import datetime
from aiogram.types import User as TgUser
from bot.database.manager import get_pool


def _row(record) -> dict | None:
    """Конвертирует asyncpg.Record в dict или возвращает None."""
    return dict(record) if record else None


async def get_user(user_id: int) -> dict | None:
    """Возвращает пользователя по telegram user_id или None."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
    return _row(row)


async def register_user(tg_user: TgUser, referred_by: int | None = None) -> bool:
    """
    Регистрирует нового пользователя.
    Возвращает True если пользователь был создан, False если уже существовал.
    """
    async with get_pool().acquire() as conn:
        result = await conn.execute("""
            INSERT INTO users (user_id, username, first_name, is_banned, registered_at, referred_by)
            VALUES ($1, $2, $3, FALSE, $4, $5)
            ON CONFLICT (user_id) DO NOTHING
        """,
            tg_user.id,
            tg_user.username,
            tg_user.first_name or "User",
            datetime.utcnow(),
            referred_by,
        )
    # asyncpg возвращает "INSERT 0 1" при вставке, "INSERT 0 0" при конфликте
    return result == "INSERT 0 1"


async def set_ban(user_id: int, banned: bool) -> None:
    """Устанавливает статус бана пользователя."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_banned = $1 WHERE user_id = $2",
            banned, user_id,
        )


async def get_all_users() -> list[dict]:
    """Возвращает всех пользователей."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
    return [dict(r) for r in rows]


async def count_users() -> int:
    """Количество зарегистрированных пользователей."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def add_bonus_days(user_id: int, days: int) -> None:
    """Начисляет пользователю бонусные дни (накапливаются)."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE users SET bonus_days = bonus_days + $1 WHERE user_id = $2",
            days, user_id,
        )


async def consume_bonus_days(user_id: int) -> int:
    """
    Обнуляет бонусные дни пользователя и возвращает их количество.
    Используется при создании/продлении подписки.
    """
    async with get_pool().acquire() as conn:
        days = await conn.fetchval(
            "UPDATE users SET bonus_days = 0 WHERE user_id = $1 RETURNING bonus_days",
            user_id,
        )
    return days or 0


async def get_referral_count(user_id: int) -> int:
    """Количество пользователей, приглашённых данным юзером."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1",
            user_id,
        ) or 0