"""
keyboards/user.py — клавиатуры для пользователей.

Используем InlineKeyboardMarkup. Минималистичный UI — только необходимые кнопки.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню."""
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Личный кабинет", callback_data="cabinet")
    kb.button(text="💳 Купить подписку",  callback_data="buy")
    kb.adjust(1)
    return kb.as_markup()


def cabinet_kb(has_subscription: bool, auto_renew: bool | None = None) -> InlineKeyboardMarkup:
    """Клавиатура личного кабинета."""
    kb = InlineKeyboardBuilder()

    if has_subscription:
        kb.button(text="📋 Получить конфиг",  callback_data="get_config")
        kb.button(text="🔗 Ссылка подписки",  callback_data="get_sub_url")
        # Переключатель автопродления
        if auto_renew:
            kb.button(text="🔄 Авто-продление: ВКЛ", callback_data="toggle_renew")
        else:
            kb.button(text="⏸ Авто-продление: ВЫКЛ", callback_data="toggle_renew")
        kb.button(text="💳 Продлить вручную", callback_data="buy")
    else:
        kb.button(text="💳 Купить подписку", callback_data="buy")

    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def pay_kb(payment_url: str) -> InlineKeyboardMarkup:
    """Кнопка перехода на страницу оплаты."""
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить через СБП", url=payment_url)
    kb.button(text="✅ Проверить оплату",   callback_data="check_payment")
    kb.button(text="◀️ Отмена",             callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def back_to_cabinet_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ В кабинет", callback_data="cabinet")
    return kb.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ В меню", callback_data="main_menu")
    return kb.as_markup()
