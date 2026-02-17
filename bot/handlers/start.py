"""
handlers/start.py — команда /start, главное меню, навигация.
"""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from bot.database.users import register_user, get_user
from bot.keyboards.user import main_menu_kb
from bot.config import PLAN_NAME, PLAN_PRICE, PLAN_DAYS

router = Router(name="start")


def _welcome_text(first_name: str) -> str:
    return (
        f"👋 Привет, {first_name}!\n\n"
        f"Здесь можно купить подписку на <b>{PLAN_NAME}</b>.\n"
        f"<b>{PLAN_PRICE} ₽ / {PLAN_DAYS} дней</b> — безлимитный трафик, "
        f"протокол VLESS.\n\n"
        "Выберите действие:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Регистрирует пользователя и показывает главное меню."""
    await register_user(message.from_user)
    await message.answer(
        _welcome_text(message.from_user.first_name),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    """Возврат в главное меню из любой точки."""
    user = await get_user(callback.from_user.id)
    name = user["first_name"] if user else callback.from_user.first_name
    await callback.message.edit_text(
        _welcome_text(name),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
