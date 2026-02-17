"""
handlers/admin.py — панель администратора.

Доступ только пользователям из ADMIN_IDS.
FSM-состояния для ввода текста рассылки и user_id при бане.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.config import ADMIN_IDS, PLAN_PRICE
from bot.database.users import get_all_users, set_ban, count_users
from bot.database.subscriptions import get_active_subscription
from bot.keyboards.admin import admin_menu_kb, confirm_broadcast_kb, admin_back_kb

logger = logging.getLogger(__name__)
router = Router(name="admin")

# Фильтр — только для администраторов
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminStates(StatesGroup):
    broadcast_text = State()    # ввод текста рассылки
    ban_user_id    = State()    # ввод user_id для бана
    unban_user_id  = State()    # ввод user_id для разбана


# ── Главное меню ──────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Открывает панель администратора."""
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "adm_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🛠 <b>Панель администратора</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Статистика ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm_stats")
async def cb_stats(callback: CallbackQuery) -> None:
    """Выводит основную статистику."""
    total = await count_users()
    users = await get_all_users()
    banned = sum(1 for u in users if u.get("is_banned"))

    # Считаем активные подписки
    active_count = 0
    for u in users:
        sub = await get_active_subscription(u["user_id"])
        if sub:
            active_count += 1

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"Пользователей: <b>{total}</b>\n"
        f"Активных подписок: <b>{active_count}</b>\n"
        f"Заблокировано: <b>{banned}</b>\n"
        f"Выручка за цикл: <b>~{active_count * PLAN_PRICE} ₽</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


# ── Список пользователей ──────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm_users")
async def cb_users(callback: CallbackQuery) -> None:
    """Краткий список последних 20 пользователей."""
    users = await get_all_users()
    if not users:
        await callback.answer("Пользователей нет.", show_alert=True)
        return

    lines = []
    for u in users[-20:]:
        tag = f"@{u['username']}" if u.get("username") else "—"
        ban = " 🚫" if u.get("is_banned") else ""
        lines.append(f"<code>{u['user_id']}</code> {tag}{ban}")

    text = "👥 <b>Последние пользователи</b>\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


# ── Рассылка ──────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm_broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text(
        "📢 Введите текст рассылки (HTML-разметка поддерживается):",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.broadcast_text)
async def on_broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(broadcast_text=message.html_text)
    await message.answer(
        f"Превью:\n\n{message.html_text}\n\nОтправить всем?",
        reply_markup=confirm_broadcast_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "adm_broadcast_confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    users = await get_all_users()
    sent, failed = 0, 0

    for u in users:
        if u.get("is_banned"):
            continue
        try:
            await callback.bot.send_message(u["user_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {sent} | Ошибок: {failed}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "adm_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb_admin_menu(callback, state)


# ── Бан / Разбан ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm_ban")
async def cb_ban_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.ban_user_id)
    await callback.message.edit_text("Введите user_id для блокировки:", reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.ban_user_id)
async def on_ban_user_id(message: Message, state: FSMContext) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат. Введите числовой user_id:")
        return
    await set_ban(uid, True)
    await state.clear()
    await message.answer(f"🚫 Пользователь {uid} заблокирован.", reply_markup=admin_back_kb())


@router.callback_query(lambda c: c.data == "adm_unban")
async def cb_unban_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.unban_user_id)
    await callback.message.edit_text("Введите user_id для разблокировки:", reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.unban_user_id)
async def on_unban_user_id(message: Message, state: FSMContext) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат. Введите числовой user_id:")
        return
    await set_ban(uid, False)
    await state.clear()
    await message.answer(f"✅ Пользователь {uid} разблокирован.", reply_markup=admin_back_kb())
