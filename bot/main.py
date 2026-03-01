import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from redis.asyncio import Redis

from bot.config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PATH,
    REDIS_URL,
)
from bot.database import create_pool, close_pool, create_tables
from bot.handlers import register_all_handlers
from bot.middlewares import ThrottlingMiddleware, BanCheckMiddleware
from bot.webhooks import register_yukassa_webhook, register_redirect_routes
from bot.services.scheduler import setup_scheduler
from bot.services.pasarguard import pasarguard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, redis: Redis) -> None:
    """Выполняется при старте: создаём пул, таблицы и регистрируем вебхук."""
    await create_pool()
    await create_tables()
    await bot.set_webhook(WEBHOOK_URL)
    setup_scheduler(bot)
    logger.info("Webhook set to %s", WEBHOOK_URL)


async def on_shutdown(bot: Bot) -> None:
    """Выполняется при остановке: очищаем ресурсы."""
    await bot.delete_webhook()
    await pasarguard.close()
    await close_pool()
    logger.info("Bot shutdown complete")


def build_app() -> web.Application:
    """Собирает и возвращает готовое aiohttp-приложение."""

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis = Redis.from_url(REDIS_URL, decode_responses=False)

    # ── Бот и диспетчер ────────────────────────────────────────────────────────
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)

    # Передаём redis во все хендлеры через data
    dp["redis"] = redis

    # ── Middleware ─────────────────────────────────────────────────────────────
    dp.update.middleware(ThrottlingMiddleware(redis=redis))
    dp.update.middleware(BanCheckMiddleware())

    # ── Хендлеры ──────────────────────────────────────────────────────────────
    register_all_handlers(dp)

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ── aiohttp-приложение ────────────────────────────────────────────────────
    app = web.Application()

    # Telegram webhook
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # ЮKassa webhook
    register_yukassa_webhook(app, bot)

    # Умные редиректы для инструкции
    register_redirect_routes(app)

    return app


def main() -> None:
    app = build_app()
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()