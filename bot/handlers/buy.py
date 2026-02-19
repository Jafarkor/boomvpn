"""
handlers/buy.py — оформление и проверка оплаты.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.payments import get_payment_by_yukassa_id, update_payment_status
from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_user
from bot.keyboards.user import pay_kb, back_to_menu_kb
from bot.messages import buy_text, payment_pending_text, payment_success_text, payment_fail_text
from bot.services.payment import create_payment_link
from bot.services.subscription import create_paid_subscription

logger = logging.getLogger(__name__)
router = Router()

# Временное хранилище pending-платежей (user_id → yukassa_payment_id)
# При перезапуске теряется — для продакшна используй Redis
_pending: dict[int, str] = {}


@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    db_user = await get_user(user_id)
    bonus_days = db_user.get("bonus_days", 0) if db_user else 0

    try:
        payment_id, url = await create_payment_link(user_id)
        _pending[user_id] = payment_id
    except Exception as exc:
        logger.error("Payment creation error for %s: %s", user_id, exc)
        await callback.answer("Не удалось создать платёж. Попробуй позже.", show_alert=True)
        return

    await callback.message.edit_text(
        buy_text(bonus_days),
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

    await callback.answer(payment_pending_text())

    try:
        from yookassa import Payment as YkPayment
        yk_payment = YkPayment.find_one(payment_id)
    except Exception as exc:
        logger.error("YK payment check error: %s", exc)
        await callback.message.edit_text(payment_fail_text(), reply_markup=back_to_menu_kb())
        return

    if yk_payment.status == "succeeded":
        _pending.pop(user_id, None)

        method_id = None
        if yk_payment.payment_method and yk_payment.payment_method.saved:
            method_id = yk_payment.payment_method.id

        await update_payment_status(payment_id, "succeeded")

        try:
            _, _ = await create_paid_subscription(user_id, payment_method_id=method_id)
            from bot.config import PLAN_DAYS
            from bot.database.users import get_user as _get
            user = await _get(user_id)
            bonus = 0  # уже применён в create_paid_subscription
            await callback.message.edit_text(
                payment_success_text(PLAN_DAYS),
                reply_markup=back_to_menu_kb(),
            )
        except Exception as exc:
            logger.error("Subscription creation after payment failed: %s", exc)
            await callback.message.edit_text(
                "✅ Оплата принята, но произошла ошибка при создании подписки.\n"
                "Обратитесь в поддержку — всё решим.",
                reply_markup=back_to_menu_kb(),
            )
    elif yk_payment.status in ("canceled", "cancelled"):
        _pending.pop(user_id, None)
        await update_payment_status(payment_id, "canceled")
        await callback.message.edit_text(payment_fail_text(), reply_markup=back_to_menu_kb())
    else:
        # pending — ещё не оплачено
        await callback.answer("Оплата пока не подтверждена. Подожди немного.", show_alert=True)
