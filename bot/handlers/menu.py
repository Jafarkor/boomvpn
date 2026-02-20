"""
handlers/menu.py — главное меню (/menu и callback "menu").
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputFile, InputMediaPhoto, FSInputFile

from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_referral_count
from bot.keyboards.user import menu_kb_no_sub, menu_kb_with_sub
from bot.messages import menu_text

logger = logging.getLogger(__name__)
router = Router()


def _ref_link(bot_username: str, user_id: int) -> str:
    return f"t.me/{bot_username}?start=ref_{user_id}"


async def _build_menu(user_id: int, bot_username: str) -> tuple[str, object]:
    """Собирает текст и клавиатуру главного меню."""
    sub = await get_active_subscription(user_id)
    ref_count = await get_referral_count(user_id)
    text = menu_text(
        sub=sub,
        ref_link=_ref_link(bot_username, user_id),
        ref_count=ref_count,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
    return text, kb


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    bot_info = await message.bot.get_me()
    sub = await get_active_subscription(message.from_user.id)
    ref_count = await get_referral_count(message.from_user.id)

    text = menu_text(
        sub=sub,
        ref_link=_ref_link(bot_info.username, message.from_user.id),
        ref_count=ref_count,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
    photo = FSInputFile("bot/media/menu.jpg")
    await message.answer_photo(photo=photo, caption=text, reply_markup=kb)


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    bot_info = await callback.bot.get_me()
    sub = await get_active_subscription(callback.from_user.id)
    ref_count = await get_referral_count(callback.from_user.id)

    text = menu_text(
        sub=sub,
        ref_link=_ref_link(bot_info.username, callback.from_user.id),
        ref_count=ref_count,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
    photo = FSInputFile("bot/media/menu.jpg")
    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo, caption=text),
        reply_markup=kb)
    await callback.answer()
