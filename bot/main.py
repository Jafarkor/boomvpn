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
from bot.database import create_tables
from bot.handlers import register_all_handlers
from bot.middlewares import ThrottlingMiddleware, BanCheckMiddleware
from bot.webhooks import register_yukassa_webhook
from bot.services.scheduler import setup_scheduler
from bot.services.marzban import marzban

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, redis: Redis) -> None:
    """Выполняется при старте: создаём таблицы, регистрируем вебхук и запускаем задачи."""
    # 1. Создаем таблицы в БД
    await create_tables()

    # 2. Устанавливаем вебхук Telegram
    await bot.set_webhook(WEBHOOK_URL)

    # 3. Запускаем планировщик (теперь внутри цикла событий)
    setup_scheduler(bot)

    logger.info("Webhook set to %s. Scheduler started.", WEBHOOK_URL)


async def on_shutdown(bot: Bot) -> None:
    """Выполняется при остановке: очищаем ресурсы."""
    await bot.delete_webhook()
    await marzban.close()
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
    # Передаем зависимости в on_startup
    dp.startup.register(lambda: on_startup(bot, redis))
    dp.shutdown.register(lambda: on_shutdown(bot))

    # ── aiohttp-приложение ────────────────────────────────────────────────────
    app = web.Application()

    # Telegram webhook
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # ЮKassa webhook
    register_yukassa_webhook(app, bot)

    return app


def main() -> None:
    app = build_app()
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()