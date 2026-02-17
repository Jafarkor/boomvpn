"""
config.py — централизованная конфигурация проекта.
Все переменные окружения читаются здесь и только здесь.
"""

from decouple import config, Csv

# ── Telegram ──────────────────────────────────────────────────────────────────

BOT_TOKEN: str = config("BOT_TOKEN")
ADMIN_IDS: list[int] = [int(i) for i in config("ADMIN_IDS", cast=Csv())]

# ── Webhook ───────────────────────────────────────────────────────────────────

WEBHOOK_HOST: str = config("WEBHOOK_HOST")
WEBHOOK_PATH: str = config("WEBHOOK_PATH", default="/webhook/bot")
YUKASSA_WEBHOOK_PATH: str = config("YUKASSA_WEBHOOK_PATH", default="/webhook/yukassa")

WEBHOOK_URL: str = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ── PostgreSQL ────────────────────────────────────────────────────────────────

PG_DSN: str = config("PG_DSN")
DB_DELETION_PASSWORD: str = config("DB_DELETION_PASSWORD")

# ── Redis ─────────────────────────────────────────────────────────────────────

REDIS_URL: str = config("REDIS_URL", default="redis://redis:6379/0")

# ── ЮKassa ───────────────────────────────────────────────────────────────────

YUKASSA_SHOP_ID: str = config("YUKASSA_SHOP_ID")
YUKASSA_SECRET_KEY: str = config("YUKASSA_SECRET_KEY")

# ── Тариф ─────────────────────────────────────────────────────────────────────

PLAN_PRICE: int = config("PLAN_PRICE", cast=int, default=299)
PLAN_DAYS: int = config("PLAN_DAYS", cast=int, default=30)
PLAN_NAME: str = config("PLAN_NAME", default="VPN Pro")

# ── Marzban ───────────────────────────────────────────────────────────────────

MARZBAN_URL: str = config("MARZBAN_URL")
MARZBAN_USERNAME: str = config("MARZBAN_USERNAME")
MARZBAN_PASSWORD: str = config("MARZBAN_PASSWORD")
MARZBAN_INBOUND_TAG: str = config("MARZBAN_INBOUND_TAG", default="vless-tcp")
