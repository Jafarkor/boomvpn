import asyncpg
from bot.config import PG_DSN

# Глобальный пул — инициализируется в create_pool(), закрывается в close_pool()
pool: asyncpg.Pool | None = None


async def create_pool() -> None:
    """Создаёт пул соединений. Вызывается один раз при старте."""
    global pool
    pool = await asyncpg.create_pool(dsn=PG_DSN, min_size=2, max_size=10)


async def close_pool() -> None:
    """Закрывает пул соединений. Вызывается при остановке."""
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    """Возвращает пул, гарантируя что он инициализирован."""
    if pool is None:
        raise RuntimeError("Database pool is not initialized. Call create_pool() first.")
    return pool