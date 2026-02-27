"""
handlers/buy.py — оформление и проверка оплаты.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from yookassa import Payment as YkPayment

from bot.database.payments import update_payment_status
from bot.database.subscriptions import get_active_subscription, save_payment_method
from bot.keyboards.user import pay_kb, back_to_menu_kb
from bot.messages import buy_text, payment_success_text, payment_fail_text
from bot.services.payment import create_payment_link
from bot.services.subscription import create_paid_subscription
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()

# user_id → yukassa_payment_id
_pending: dict[int, str] = {}


async def _process_check_payment(callback: CallbackQuery, user_id: int, payment_id: str) -> None:
    """
    Общая логика проверки статуса платежа ЮКассы.
    """
    try:
        yk_payment = YkPayment.find_one(payment_id)
    except Exception as exc:
        logger.error("YK payment check error: %s", exc)
        await edit_photo_page(
            callback,
            page="buy",
            caption=payment_fail_text(),
            reply_markup=back_to_menu_kb(),
        )
        return

    if yk_payment.status == "succeeded":
        _pending.pop(user_id, None)

        # Берём id метода оплаты.
        # ВАЖНО: для СБП ЮКасса может вернуть saved=False при первом find_one
        # (метод сохраняется асинхронно), но id уже есть.
        # Сохраняем id сейчас; вебхук обновит флаг saved=True и подтвердит.
        pm = yk_payment.payment_method
        method_id = pm.id if (pm and pm.id) else None

        await update_payment_status(payment_id, "succeeded")

        try:
            # method_id передаём только если метод реально сохранён (saved=True).
            # Если saved=False — передаём None; вебхук позже запишет id в БД.
            saved_method_id = method_id if (pm and getattr(pm, "saved", False)) else None
            await create_paid_subscription(user_id, payment_method_id=saved_method_id)

            # payment_method_id сохраняется только через вебхук (saved=True).
            # Сохранять id при saved=False нельзя — ЮКасса вернёт ошибку при автосписании.

            await edit_photo_page(
                callback,
                page="menu",
                caption=payment_success_text(),
                reply_markup=back_to_menu_kb(),
            )
        except Exception as exc:
            logger.error("Subscription creation after payment failed: %s", exc)
            await callback.message.answer(
                "<tg-emoji emoji-id=\"5411197345968701560\">✅</tg-emoji> Оплата принята, но произошла ошибка при создании подписки.\n"
                "Напиши в поддержку — разберёмся.",
            )

    elif yk_payment.status in ("canceled", "cancelled"):
        _pending.pop(user_id, None)
        await update_payment_status(payment_id, "canceled")
        await edit_photo_page(
            callback,
            page="buy",
            caption=payment_fail_text(),
            reply_markup=back_to_menu_kb(),
        )

    else:
        await callback.answer("Оплата ещё не подтверждена. Подождите немного.", show_alert=True)


@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    try:
        payment_id, url = await create_payment_link(user_id)
    except Exception as exc:
        logger.error("Payment creation error for %s: %s", user_id, exc)
        await callback.answer("Не удалось создать платёж. Попробуй позже.", show_alert=True)
        return

    _pending[user_id] = payment_id

    if url is None:
        # Прямое списание через сохранённый метод — сразу проверяем статус.
        await callback.answer()
        await _process_check_payment(callback, user_id, payment_id)
    else:
        await edit_photo_page(
            callback,
            page="buy",
            caption=buy_text(),
            reply_markup=pay_kb(url),
        )
        await callback.answer()


@router.callback_query(F.data == "check_payment")
async def cb_check_payment(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payment_id = _pending.get(user_id)

    if not payment_id:
        await callback.answer("Нет активного платежа. Начни заново.", show_alert=True)
        return

    await _process_check_payment(callback, user_id, payment_id)
