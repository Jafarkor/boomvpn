"""
keyboards/user.py — клавиатуры пользователя.

Принцип: минимум кнопок, максимум ясности.
Стрелка назад: ← (Unicode U+2190, не эмодзи).
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── Главное меню ──────────────────────────────────────────────────────────────

def menu_kb_no_sub() -> InlineKeyboardMarkup:
    """Меню когда подписка неактивна."""
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Купить подписку", callback_data="buy")
    kb.adjust(1)
    return kb.as_markup()


def menu_kb_with_sub() -> InlineKeyboardMarkup:
    """Меню когда подписка активна."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Ссылка подписки",  callback_data="get_sub_url")
    kb.button(text="📖 Инструкция",       callback_data="instruction")
    kb.button(text="⚙️ Настройки",        callback_data="settings")
    kb.adjust(1)
    return kb.as_markup()


# ── Настройки подписки ────────────────────────────────────────────────────────

def settings_kb(auto_renew: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    auto_label = "🔄 Авто: вкл  →  выключить" if auto_renew else "🔄 Авто: выкл  →  включить"
    kb.button(text=auto_label,             callback_data="toggle_renew")
    kb.button(text="💳 Продлить вручную",  callback_data="buy")
    kb.button(text="← Назад",             callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


# ── Покупка ───────────────────────────────────────────────────────────────────

def pay_kb(payment_url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить через СБП", url=payment_url)
    kb.button(text="✅ Проверить оплату",    callback_data="check_payment")
    kb.button(text="✕ Отмена",              callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


# ── Инструкция ────────────────────────────────────────────────────────────────

def instruction_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть меню →", callback_data="menu")
    return kb.as_markup()


# ── Навигация ─────────────────────────────────────────────────────────────────

def back_to_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="← В меню", callback_data="menu")
    return kb.as_markup()
