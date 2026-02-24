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

BASE_URL: str = config("BASE_URL", default=WEBHOOK_HOST)

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

GIFT_DAYS: int = config("GIFT_DAYS", cast=int, default=7)
REFERRAL_BONUS_DAYS: int = config("REFERRAL_BONUS_DAYS", cast=int, default=7)

# ── PasarGuard ────────────────────────────────────────────────────────────────

PASARGUARD_URL: str = config("PASARGUARD_URL")
PASARGUARD_USERNAME: str = config("PASARGUARD_USERNAME")
PASARGUARD_PASSWORD: str = config("PASARGUARD_PASSWORD")
PASARGUARD_INBOUND_TAG: str = config("PASARGUARD_INBOUND_TAG", default="vless-tcp")
PASARGUARD_FLOW: str = config("PASARGUARD_FLOW", default="xtls-rprx-vision")
