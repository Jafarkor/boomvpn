from aiogram import Dispatcher
from bot.handlers.start   import router as start_router
from bot.handlers.cabinet import router as cabinet_router
from bot.handlers.payment import router as payment_router
from bot.handlers.admin   import router as admin_router


def register_all_handlers(dp: Dispatcher) -> None:
    """Регистрирует все роутеры в диспетчере."""
    dp.include_router(admin_router)    # Первым — у него самые строгие фильтры
    dp.include_router(start_router)
    dp.include_router(cabinet_router)
    dp.include_router(payment_router)
