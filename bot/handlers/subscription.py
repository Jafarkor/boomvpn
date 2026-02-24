"""
handlers/subscription.py — ссылка подписки, инструкция, настройки, автопродление.

Все экраны отображаются как фото с caption (через edit_photo_page).
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.subscriptions import get_active_subscription, toggle_auto_renew
from bot.keyboards.user import settings_kb, back_to_menu_kb
from bot.messages import settings_text, instruction_text
from bot.services.pasarguard import pasarguard
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "instruction")
async def cb_instruction(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    url = ""
    if sub:
        url = await pasarguard.get_subscription_url(sub["panel_username"])

    await edit_photo_page(
        callback,
        page="instruction",
        caption=instruction_text(url),
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    await edit_photo_page(
        callback,
        page="settings",
        caption=settings_text(sub),
        reply_markup=settings_kb(sub.get("auto_renew", False)),
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_renew")
async def cb_toggle_renew(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    new_state = not sub.get("auto_renew", False)
    await toggle_auto_renew(sub["id"], new_state)
    sub["auto_renew"] = new_state

    await edit_photo_page(
        callback,
        page="settings",
        caption=settings_text(sub),
        reply_markup=settings_kb(new_state),
    )
    await callback.answer("Автопродление " + ("включено ✅" if new_state else "выключено ❌"))
