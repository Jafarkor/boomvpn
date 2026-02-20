"""
handlers/menu.py — главное меню (/menu и callback "menu").

Меню отображается как фото с caption.
При возврате через callback используем edit_photo_page — без нового сообщения.
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_referral_count
from bot.keyboards.user import menu_kb_no_sub, menu_kb_with_sub
from bot.messages import menu_text
from bot.utils.media import send_photo_page, edit_photo_page

logger = logging.getLogger(__name__)
router = Router()

PAGE = "menu"


def _ref_link(bot_username: str, user_id: int) -> str:
    return f"t.me/{bot_username}?start=ref_{user_id}"


async def _build(user_id: int, bot_username: str) -> tuple[str, object]:
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
    caption, kb = await _build(message.from_user.id, bot_info.username)
    await send_photo_page(message, PAGE, caption, kb)


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    bot_info = await callback.bot.get_me()
    caption, kb = await _build(callback.from_user.id, bot_info.username)
    await edit_photo_page(callback, PAGE, caption, kb)
    await callback.answer()
