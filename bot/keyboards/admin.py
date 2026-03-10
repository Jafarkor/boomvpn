"""
keyboards/admin.py — клавиатуры для администраторов.
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика",       callback_data="adm_stats")
    kb.button(text="👥 Пользователи",     callback_data="adm_users")
    kb.button(text="📢 Рассылка",         callback_data="adm_broadcast")
    kb.button(text="🚫 Забанить",         callback_data="adm_ban")
    kb.button(text="✅ Разбанить",        callback_data="adm_unban")
    kb.button(text="🎁 Начислить подписку", callback_data="adm_grant")
    kb.adjust(2)
    return kb.as_markup()


def confirm_broadcast_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отправить",  callback_data="adm_broadcast_confirm")
    kb.button(text="❌ Отмена",    callback_data="adm_cancel")
    kb.adjust(2)
    return kb.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="adm_menu")
    return kb.as_markup()
