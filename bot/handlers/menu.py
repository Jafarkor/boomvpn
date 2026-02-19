"""
handlers/menu.py — главное меню (/menu и callback "menu").
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import PLAN_PRICE
from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_user, get_referral_count
from bot.keyboards.user import menu_kb_no_sub, menu_kb_with_sub
from bot.messages import menu_text

logger = logging.getLogger(__name__)
router = Router()


def _build_ref_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


async def _send_menu(target: Message | CallbackQuery, user_id: int, bot_username: str) -> None:
    """Универсальная функция — отправляет или редактирует меню."""
    sub = await get_active_subscription(user_id)
    ref_count = await get_referral_count(user_id)
    db_user = await get_user(user_id)
    bonus_days = db_user.get("bonus_days", 0) if db_user else 0

    name = (
        target.from_user.first_name
        if isinstance(target, Message)
        else target.from_user.first_name
    )
    ref_link = _build_ref_link(bot_username, user_id)

    text = menu_text(
        name=name,
        sub=sub,
        ref_link=ref_link,
        ref_count=ref_count,
        bonus_days=bonus_days,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    bot_info = await message.bot.get_me()
    await _send_menu(message, message.from_user.id, bot_info.username)


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    bot_info = await callback.bot.get_me()
    await _send_menu(callback, callback.from_user.id, bot_info.username)
