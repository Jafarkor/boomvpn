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
    kb.button(text="Купить подписку",
              callback_data="buy",
              icon_custom_emoji_id="5445353829304387411",)
    kb.adjust(1)
    return kb.as_markup()


def menu_kb_with_sub() -> InlineKeyboardMarkup:
    """Меню когда подписка активна."""
    kb = InlineKeyboardBuilder()

    kb.button(
        text="Подключить VPN",
        callback_data="instruction",
        icon_custom_emoji_id="5172425562634847208",
    )
    kb.button(
        text="Настройки",
        callback_data="settings",
        icon_custom_emoji_id="5258096772776991776",
    )

    kb.adjust(1)
    return kb.as_markup()


# ── Настройки подписки ────────────────────────────────────────────────────────

def settings_kb(auto_renew: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    auto_label = "Авто: вкл  →  выключить" if auto_renew else "Авто: выкл  →  включить"
    kb.button(text=auto_label,
              icon_custom_emoji_id="5258419835922030550",
              callback_data="toggle_renew")
    kb.button(text="Продлить вручную",
              icon_custom_emoji_id="5445353829304387411",
              callback_data="buy")
    kb.button(text="← Назад",
              callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


# ── Покупка ───────────────────────────────────────────────────────────────────

def pay_kb(payment_url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить через СБП",
              url=payment_url,
              icon_custom_emoji_id="5445353829304387411")
    kb.button(text="Проверить оплату",
              callback_data="check_payment",
              icon_custom_emoji_id="5411197345968701560")
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
