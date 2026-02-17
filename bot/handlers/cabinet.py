"""
handlers/cabinet.py — личный кабинет пользователя.

Показывает статус подписки, даёт VLESS-конфиг и ссылку подписки,
управляет автопродлением.
"""

from datetime import datetime
from aiogram import Router
from aiogram.types import CallbackQuery

from bot.database.subscriptions import (
    get_active_subscription,
    toggle_auto_renew,
)
from bot.services.marzban import marzban
from bot.keyboards.user import cabinet_kb, back_to_cabinet_kb

router = Router(name="cabinet")


def _sub_status_text(sub: dict) -> str:
    """Форматирует информацию о подписке."""
    expires = sub["expires_at"]
    days_left = (expires - datetime.utcnow()).days
    status = "✅ Активна" if sub["is_active"] else "❌ Не активна"
    renew = "ВКЛ 🔄" if sub.get("auto_renew") else "ВЫКЛ ⏸"
    return (
        f"<b>Личный кабинет</b>\n\n"
        f"Статус: {status}\n"
        f"Истекает: {expires.strftime('%d.%m.%Y')}\n"
        f"Осталось дней: <b>{max(days_left, 0)}</b>\n"
        f"Авто-продление: {renew}"
    )


@router.callback_query(lambda c: c.data == "cabinet")
async def cb_cabinet(callback: CallbackQuery) -> None:
    """Открывает личный кабинет."""
    sub = await get_active_subscription(callback.from_user.id)

    if sub:
        text = _sub_status_text(sub)
        kb = cabinet_kb(has_subscription=True, auto_renew=sub.get("auto_renew"))
    else:
        text = (
            "<b>Личный кабинет</b>\n\n"
            "У вас нет активной подписки.\n"
            "Нажмите «Купить подписку», чтобы начать."
        )
        kb = cabinet_kb(has_subscription=False)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "get_config")
async def cb_get_config(callback: CallbackQuery) -> None:
    """Отправляет VLESS-ссылку пользователю."""
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Нет активной подписки.", show_alert=True)
        return

    link = await marzban.get_vless_link(sub["marzban_username"])
    if not link:
        await callback.answer("Не удалось получить конфиг. Попробуйте позже.", show_alert=True)
        return

    await callback.message.answer(
        f"<b>Ваш VLESS-конфиг:</b>\n\n"
        f"<code>{link}</code>\n\n"
        "Скопируйте и вставьте в приложение (v2rayNG, Hiddify и др.)",
        reply_markup=back_to_cabinet_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "get_sub_url")
async def cb_get_sub_url(callback: CallbackQuery) -> None:
    """Отправляет subscription URL для автоимпорта конфигов."""
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Нет активной подписки.", show_alert=True)
        return

    url = await marzban.get_subscription_url(sub["marzban_username"])
    if not url:
        await callback.answer("Subscription URL недоступен.", show_alert=True)
        return

    await callback.message.answer(
        f"<b>Ссылка подписки:</b>\n\n"
        f"<code>{url}</code>\n\n"
        "Вставьте в раздел «Подписки» вашего клиента для автообновления конфигов.",
        reply_markup=back_to_cabinet_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "toggle_renew")
async def cb_toggle_renew(callback: CallbackQuery) -> None:
    """Переключает автопродление подписки."""
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Нет активной подписки.", show_alert=True)
        return

    new_state = not sub.get("auto_renew", True)
    await toggle_auto_renew(sub["id"], new_state)

    state_text = "включено 🔄" if new_state else "выключено ⏸"
    await callback.answer(f"Авто-продление {state_text}", show_alert=True)

    # Обновляем экран кабинета
    sub["auto_renew"] = new_state
    await callback.message.edit_text(
        _sub_status_text(sub),
        reply_markup=cabinet_kb(has_subscription=True, auto_renew=new_state),
        parse_mode="HTML",
    )
