"""
handlers/subscription.py — ссылка подписки, инструкция, настройки, автопродление.

Все экраны отображаются как фото с caption (через edit_photo_page),
чтобы при возврате в меню можно было редактировать одно сообщение.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.subscriptions import get_active_subscription, toggle_auto_renew
from bot.keyboards.user import settings_kb, back_to_menu_kb, instruction_kb
from bot.messages import settings_text, sub_url_text, instruction_text
from bot.services.marzban import marzban
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "get_sub_url")
async def cb_get_sub_url(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    url = await marzban.get_subscription_url(sub["marzban_username"])
    await edit_photo_page(
        callback,
        page="sub_url",
        caption=sub_url_text(url),
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "instruction")
async def cb_instruction(callback: CallbackQuery) -> None:
    await edit_photo_page(
        callback,
        page="instruction",
        caption=instruction_text(),
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
