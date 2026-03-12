"""
handlers/buy.py — оформление и проверка оплаты.

ИСПРАВЛЕНИЯ:
1. _process_check_payment теперь делает несколько попыток (retry) с паузой,
   т.к. ЮKassa СБП может возвращать "pending" ещё несколько секунд после
   реальной оплаты.
2. Дополнительно проверяется поле paid=True как ранний признак успеха.
3. _pending сохраняется в БД (get_pending_payment/set_pending_payment),
   чтобы не теряться при перезапуске бота.
"""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from yookassa import Payment as YkPayment

from bot.database.payments import (
    update_payment_status,
    get_pending_payment_for_user,
    save_pending_payment_for_user,
    clear_pending_payment_for_user,
)
from bot.database.subscriptions import get_active_subscription, save_payment_method
from bot.keyboards.user import pay_kb, back_to_menu_kb
from bot.messages import buy_text, payment_success_text, payment_fail_text
from bot.services.payment import create_payment_link
from bot.services.subscription import create_paid_subscription
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()

# user_id → идёт проверка платежа (защита от параллельных нажатий)
# Это in-memory, но только для защиты от двойных кликов — не критично при рестарте.
_in_progress: set[int] = set()

# Параметры retry при проверке статуса СБП-платежа.
# ЮKassa может задержать обновление статуса на несколько секунд после оплаты.
RETRY_ATTEMPTS = 5       # количество попыток
RETRY_DELAY_SEC = 3.0    # пауза между попытками (секунды)


async def _fetch_yk_payment(payment_id: str):
    """Запускает синхронный YkPayment.find_one в thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, YkPayment.find_one, payment_id)


async def _process_check_payment(callback: CallbackQuery, user_id: int, payment_id: str) -> None:
    """
    Проверяет статус платежа ЮKassa.

    Делает несколько попыток с задержкой, потому что СБП-платёж может
    фактически пройти в банке, но ЮKassa ещё не обновила статус в API.
    """
    yk_payment = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            yk_payment = await _fetch_yk_payment(payment_id)
        except Exception as exc:
            logger.error("YK payment check error (attempt %d/%d): %s", attempt, RETRY_ATTEMPTS, exc)
            if attempt == RETRY_ATTEMPTS:
                await edit_photo_page(
                    callback,
                    page="buy",
                    caption=payment_fail_text(),
                    reply_markup=back_to_menu_kb(),
                )
                return
            await asyncio.sleep(RETRY_DELAY_SEC)
            continue

        # ЮKassa для СБП иногда возвращает paid=True раньше, чем статус succeeded.
        # Используем это как дополнительный признак успеха.
        is_succeeded = yk_payment.status == "succeeded"
        is_paid_early = getattr(yk_payment, "paid", False) and yk_payment.status == "pending"
        is_canceled = yk_payment.status in ("canceled", "cancelled")

        if is_succeeded or is_paid_early:
            break  # платёж прошёл — выходим из цикла retry

        if is_canceled:
            break  # платёж отменён — тоже выходим

        # Статус ещё pending — ждём и повторяем
        if attempt < RETRY_ATTEMPTS:
            logger.info(
                "Payment %s still pending (attempt %d/%d), retrying in %.1fs...",
                payment_id, attempt, RETRY_ATTEMPTS, RETRY_DELAY_SEC,
            )
            await asyncio.sleep(RETRY_DELAY_SEC)
        else:
            logger.info("Payment %s still pending after %d attempts.", payment_id, RETRY_ATTEMPTS)

    if yk_payment is None:
        return  # ошибки уже обработаны выше

    is_succeeded = yk_payment.status == "succeeded"
    is_paid_early = getattr(yk_payment, "paid", False) and yk_payment.status == "pending"
    is_canceled = yk_payment.status in ("canceled", "cancelled")

    if is_succeeded or is_paid_early:
        await clear_pending_payment_for_user(user_id)

        pm = yk_payment.payment_method
        method_id = pm.id if (pm and pm.id) else None

        await update_payment_status(payment_id, "succeeded")

        try:
            # Передаём method_id только если saved=True.
            # При is_paid_early (paid=True, status=pending) saved может быть False —
            # это нормально, вебхук запишет method_id позже.
            saved_method_id = method_id if (pm and getattr(pm, "saved", False)) else None
            await create_paid_subscription(user_id, payment_method_id=saved_method_id)

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

    elif is_canceled:
        await clear_pending_payment_for_user(user_id)
        await update_payment_status(payment_id, "canceled")
        await edit_photo_page(
            callback,
            page="buy",
            caption=payment_fail_text(),
            reply_markup=back_to_menu_kb(),
        )

    else:
        # После всех попыток статус всё ещё pending — сообщаем пользователю подождать.
        # Вебхук от ЮKassa придёт позже и активирует подписку автоматически.
        await callback.answer(
            "Оплата ещё обрабатывается банком. Подождите 1–2 минуты и проверьте снова.",
            show_alert=True,
        )


@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    try:
        payment_id, url = await create_payment_link(user_id)
    except Exception as exc:
        logger.error("Payment creation error for %s: %s", user_id, exc)
        await callback.answer("Не удалось создать платёж. Попробуй позже.", show_alert=True)
        return

    # Сохраняем payment_id в БД — не потеряется при перезапуске
    await save_pending_payment_for_user(user_id, payment_id)

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

    # Защита от повторных нажатий: пока идёт проверка — игнорируем дубли.
    if user_id in _in_progress:
        await callback.answer("Уже проверяем, подождите...", show_alert=True)
        return

    # Берём payment_id из БД (не из памяти — переживёт рестарт бота)
    payment_id = await get_pending_payment_for_user(user_id)
    if not payment_id:
        await callback.answer("Нет активного платежа. Начни заново.", show_alert=True)
        return

    _in_progress.add(user_id)
    try:
        await _process_check_payment(callback, user_id, payment_id)
    finally:
        _in_progress.discard(user_id)