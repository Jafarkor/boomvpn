"""
handlers/admin.py — административные команды.

Доступны только пользователям из ADMIN_IDS.
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.config import ADMIN_IDS
from bot.database.users import get_all_users, count_users, set_ban, get_user
from bot.database.subscriptions import get_active_subscription
from bot.keyboards.admin import admin_menu_kb, confirm_broadcast_kb, admin_back_kb

logger = logging.getLogger(__name__)
router = Router()


class AdminFSM(StatesGroup):
    broadcast_text = State()
    ban_id = State()
    unban_id = State()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "adm_menu")
async def cb_adm_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("🛠 <b>Панель администратора</b>", reply_markup=admin_menu_kb())
    await callback.answer()


# ── Статистика ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    total = await count_users()
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\nПользователей: <b>{total}</b>",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


# ── Пользователи ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_users")
async def cb_adm_users(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    users = await get_all_users()
    lines = [f"👥 <b>Пользователи</b> ({len(users)})\n"]
    for u in users[:20]:
        name = u.get("first_name", "—")
        uid = u["user_id"]
        banned = " 🚫" if u.get("is_banned") else ""
        lines.append(f"• {name} (<code>{uid}</code>){banned}")
    if len(users) > 20:
        lines.append(f"\n... и ещё {len(users) - 20}")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


# ── Рассылка ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminFSM.broadcast_text)
    await callback.message.edit_text(
        "📢 Отправь текст рассылки (поддерживается HTML):",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminFSM.broadcast_text)
async def fsm_broadcast_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(text=message.html_text)
    await message.answer(
        f"Предпросмотр:\n\n{message.html_text}\n\nОтправить?",
        reply_markup=confirm_broadcast_kb(),
    )


@router.callback_query(F.data == "adm_broadcast_confirm")
async def cb_adm_broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("text", "")
    await state.clear()

    users = await get_all_users()
    sent = 0
    for u in users:
        try:
            await callback.bot.send_message(u["user_id"], text)
            sent += 1
        except Exception:
            pass

    await callback.message.edit_text(
        f"✅ Рассылка завершена. Доставлено: {sent}/{len(users)}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


# ── Бан / разбан ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_ban")
async def cb_adm_ban(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminFSM.ban_id)
    await callback.message.edit_text("Введи user_id для бана:", reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminFSM.ban_id)
async def fsm_ban_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        await set_ban(uid, True)
        await state.clear()
        await message.answer(f"🚫 Пользователь {uid} заблокирован.", reply_markup=admin_back_kb())
    except ValueError:
        await message.answer("Введи числовой user_id.")


@router.callback_query(F.data == "adm_unban")
async def cb_adm_unban(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminFSM.unban_id)
    await callback.message.edit_text("Введи user_id для разбана:", reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminFSM.unban_id)
async def fsm_unban_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        await set_ban(uid, False)
        await state.clear()
        await message.answer(f"✅ Пользователь {uid} разблокирован.", reply_markup=admin_back_kb())
    except ValueError:
        await message.answer("Введи числовой user_id.")


@router.callback_query(F.data == "adm_cancel")
async def cb_adm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("🛠 <b>Панель администратора</b>", reply_markup=admin_menu_kb())
    await callback.answer()
