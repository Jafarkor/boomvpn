from bot.database.manager import get_pool


async def create_tables() -> None:
    """Создаёт все необходимые таблицы, если они ещё не существуют."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       BIGINT      PRIMARY KEY,
                username      TEXT,
                first_name    TEXT        NOT NULL,
                is_banned     BOOLEAN     NOT NULL DEFAULT FALSE,
                registered_at TIMESTAMP   NOT NULL
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id                        SERIAL      PRIMARY KEY,
                user_id                   BIGINT      NOT NULL,
                marzban_username          TEXT        NOT NULL,
                expires_at                TIMESTAMP   NOT NULL,
                is_active                 BOOLEAN     NOT NULL DEFAULT TRUE,
                yukassa_payment_method_id TEXT,
                auto_renew                BOOLEAN     NOT NULL DEFAULT TRUE
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id                  SERIAL      PRIMARY KEY,
                user_id             BIGINT      NOT NULL,
                yukassa_payment_id  TEXT        NOT NULL UNIQUE,
                amount              NUMERIC     NOT NULL,
                status              TEXT        NOT NULL DEFAULT 'pending',
                created_at          TIMESTAMP   NOT NULL,
                subscription_id     INT
            )
        """)