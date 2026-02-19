from datetime import datetime
from bot.database.manager import get_pool


async def record_referral(referrer_id: int, referred_id: int) -> None:
    """Записывает реферальную связь (идемпотентно)."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO referrals (referrer_id, referred_id, created_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (referred_id) DO NOTHING
        """, referrer_id, referred_id, datetime.utcnow())


async def mark_rewarded(referred_id: int) -> None:
    """Помечает реферала как вознаграждённого."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE referrals SET rewarded = TRUE WHERE referred_id = $1",
            referred_id,
        )


async def get_referral(referred_id: int) -> dict | None:
    """Получает реферальную запись по ID приглашённого."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM referrals WHERE referred_id = $1", referred_id
        )
    return dict(row) if row else None
