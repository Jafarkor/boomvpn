"""
handlers/channel.py — обработка проверки подписки на Telegram-канал.

Callback "check_channel_sub":
  - Если подписался → удаляем сообщение с кнопками → показываем главное меню
  - Если не подписался → show_alert с подсказкой
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.config import CHANNEL_USERNAME
from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_referral_count
from bot.keyboards.user import menu_kb_no_sub, menu_kb_with_sub
from bot.messages import menu_text
from bot.utils.channel import is_subscribed
from bot.utils.media import send_photo_page

logger = logging.getLogger(__name__)
router = Router()


def _ref_link(bot_username: str, user_id: int) -> str:
    return f"t.me/{bot_username}?start=ref_{user_id}"


@router.callback_query(F.data == "check_channel_sub")
async def cb_check_channel_sub(callback: CallbackQuery) -> None:
    """Проверяет подписку; при успехе — удаляет сообщение и открывает главное меню."""
    user_id = callback.from_user.id

    if not await is_subscribed(user_id, callback.bot):
        await callback.answer(
            f"❌ Вы ещё не подписались на канал {CHANNEL_USERNAME}.\n"
            "Подпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        return

    # Подписан — убираем сообщение с кнопками подписки
    await callback.answer("✅ Отлично! Добро пожаловать!")
    try:
        await callback.message.delete()
    except Exception:
        pass  # сообщение уже удалено или слишком старое

    # Показываем главное меню
    bot_info = await callback.bot.get_me()
    sub = await get_active_subscription(user_id)
    ref_count = await get_referral_count(user_id)
    caption = menu_text(
        sub=sub,
        ref_link=_ref_link(bot_info.username, user_id),
        ref_count=ref_count,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
    await send_photo_page(callback.message, "menu", caption, kb)
