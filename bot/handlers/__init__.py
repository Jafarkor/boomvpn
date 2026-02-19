"""
handlers/__init__.py — регистрация всех роутеров.
"""

from aiogram import Dispatcher

from bot.handlers.start import router as start_router
from bot.handlers.menu import router as menu_router
from bot.handlers.subscription import router as subscription_router
from bot.handlers.buy import router as buy_router
from bot.handlers.admin import router as admin_router


def register_all_handlers(dp: Dispatcher) -> None:
    """Подключает все роутеры к диспетчеру в нужном порядке."""
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(subscription_router)
    dp.include_router(buy_router)
    dp.include_router(admin_router)
