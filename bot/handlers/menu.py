"""
handlers/menu.py — главное меню (/menu и callback "menu").

Меню отправляется как фото с подписью (caption).
При возврате через callback:
  • если предыдущее сообщение — фото → edit_caption (без перезагрузки фото)
  • если текст → удаляем и отправляем новое фото

Оптимизация: после первой загрузки фото сохраняем file_id Telegram
и переиспользуем его — не загружаем файл повторно каждый раз.
"""

import logging
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message, CallbackQuery

from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_referral_count
from bot.keyboards.user import menu_kb_no_sub, menu_kb_with_sub
from bot.messages import menu_text

logger = logging.getLogger(__name__)
router = Router()

# Путь к картинке относительно этого файла: bot/handlers/ → bot/media/
MENU_PHOTO_PATH = Path(__file__).parent.parent / "media" / "menu.png"

# Кэш file_id: Telegram хранит файл на своих серверах после первой загрузки.
# Сохраняем id и переиспользуем — не загружаем файл при каждом вызове меню.
_menu_photo_id: str | None = None


def _ref_link(bot_username: str, user_id: int) -> str:
    return f"t.me/{bot_username}?start=ref_{user_id}"


async def _get_photo() -> str | FSInputFile:
    """Возвращает file_id (если уже загружали) или FSInputFile для первой загрузки."""
    if _menu_photo_id:
        return _menu_photo_id
    return FSInputFile(MENU_PHOTO_PATH)


async def _build_caption_and_kb(user_id: int, bot_username: str) -> tuple[str, object]:
    """Собирает текст меню и клавиатуру."""
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
    global _menu_photo_id

    bot_info = await message.bot.get_me()
    caption, kb = await _build_caption_and_kb(message.from_user.id, bot_info.username)

    sent = await message.answer_photo(
        photo=await _get_photo(),
        caption=caption,
        reply_markup=kb,
    )

    # Сохраняем file_id после первой успешной загрузки
    if not _menu_photo_id and sent.photo:
        _menu_photo_id = sent.photo[-1].file_id


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    global _menu_photo_id

    bot_info = await callback.bot.get_me()
    caption, kb = await _build_caption_and_kb(callback.from_user.id, bot_info.username)

    if callback.message.photo:
        # Текущее сообщение уже фото — просто обновляем подпись
        await callback.message.edit_caption(caption=caption, reply_markup=kb)
    else:
        # Текущее сообщение текстовое (например, настройки) — удаляем и шлём фото
        await callback.message.delete()
        sent = await callback.message.answer_photo(
            photo=await _get_photo(),
            caption=caption,
            reply_markup=kb,
        )
        if not _menu_photo_id and sent.photo:
            _menu_photo_id = sent.photo[-1].file_id

    await callback.answer()