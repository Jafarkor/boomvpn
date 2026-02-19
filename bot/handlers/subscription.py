"""
handlers/subscription.py — настройки подписки, ссылка, автопродление.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.subscriptions import (
    get_active_subscription,
    toggle_auto_renew,
)
from bot.keyboards.user import settings_kb, back_to_menu_kb
from bot.messages import settings_text, INSTRUCTION_TEXT
from bot.services.marzban import marzban

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    await callback.message.edit_text(
        settings_text(sub),
        reply_markup=settings_kb(sub.get("auto_renew", True)),
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_renew")
async def cb_toggle_renew(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    new_state = not sub.get("auto_renew", True)
    await toggle_auto_renew(sub["id"], new_state)
    sub["auto_renew"] = new_state

    await callback.message.edit_text(
        settings_text(sub),
        reply_markup=settings_kb(new_state),
    )
    status = "включено" if new_state else "выключено"
    await callback.answer(f"Автопродление {status}")


@router.callback_query(F.data == "get_sub_url")
async def cb_get_sub_url(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    url = await marzban.get_subscription_url(sub["marzban_username"])
    await callback.message.answer(
        f"🔗 <b>Ссылка подписки</b>\n\n"
        f"<code>{url}</code>\n\n"
        f"<i>Скопируй и вставь в своё приложение.</i>",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "instruction")
async def cb_instruction(callback: CallbackQuery) -> None:
    await callback.message.answer(
        INSTRUCTION_TEXT,
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
