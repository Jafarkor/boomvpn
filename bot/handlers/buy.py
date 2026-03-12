"""
handlers/buy.py — оформление и фоновая проверка оплаты.

Логика кнопки "Проверить оплату":
  1. Сообщение с кнопками удаляется.
  2. Пользователю отправляется: "Подписка активируется сама, ждите 5–10 минут."
  3. В фоне запускается asyncio-задача, которая проверяет статус платежа
     раз в 20 секунд на протяжении до 15 минут.
  4. Как только ЮKassa вернёт succeeded/paid=True — подписка активируется
     и пользователь получает уведомление.
  5. Если за 15 минут оплата не подтвердилась — сообщение об ошибке.

Защиты:
  - Нельзя запустить две проверки одновременно (_polling_tasks).
  - Нажатие "← Назад" → "Купить подписку" не создаёт новый платёж,
    пока есть незавершённый.
  - payment_id хранится в БД (не в памяти) — переживает рестарт бота.
"""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from yookassa import Payment as YkPayment

from bot.database.payments import (
    update_payment_status,
    get_pending_payment_for_user,
    save_pending_payment_for_user,
    clear_pending_payment_for_user,
)
from bot.keyboards.user import pay_kb, back_to_menu_kb
from bot.messages import buy_text, payment_success_text, payment_fail_text
from bot.services.payment import create_payment_link
from bot.services.subscription import create_paid_subscription
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()

# Параметры фонового поллинга
POLL_INTERVAL_SEC = 20        # интервал между запросами к ЮKassa
POLL_TIMEOUT_SEC  = 15 * 60  # максимальное время ожидания (15 минут)

# user_id → asyncio.Task (защита от двух параллельных задач на одного юзера)
_polling_tasks: dict[int, asyncio.Task] = {}


# ── Вспомогательные функции ───────────────────────────────────────────────────

async def _fetch_yk_payment(payment_id: str):
    """Запускает синхронный YkPayment.find_one в thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, YkPayment.find_one, payment_id)


def _is_success(yk_payment) -> bool:
    """True если платёж реально прошёл (succeeded ИЛИ paid=True при pending)."""
    if yk_payment.status == "succeeded":
        return True
    # ЮKassa для СБП иногда возвращает paid=True раньше, чем статус succeeded
    if getattr(yk_payment, "paid", False) and yk_payment.status == "pending":
        return True
    return False


def _is_canceled(yk_payment) -> bool:
    return yk_payment.status in ("canceled", "cancelled")


async def _activate_subscription(user_id: int, yk_payment) -> None:
    """Активирует подписку после подтверждения оплаты."""
    pm = yk_payment.payment_method
    method_id = pm.id if (pm and pm.id) else None
    saved_method_id = method_id if (pm and getattr(pm, "saved", False)) else None

    await update_payment_status(yk_payment.id, "succeeded")
    await create_paid_subscription(user_id, payment_method_id=saved_method_id)
    await clear_pending_payment_for_user(user_id)


# ── Фоновая задача поллинга ───────────────────────────────────────────────────

async def _poll_payment(user_id: int, payment_id: str, bot: Bot) -> None:
    """
    Фоновая задача: опрашивает ЮKassa каждые POLL_INTERVAL_SEC секунд.
    Завершается при успехе, отмене или по таймауту POLL_TIMEOUT_SEC.
    """
    elapsed = 0

    while elapsed < POLL_TIMEOUT_SEC:
        await asyncio.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

        try:
            yk_payment = await _fetch_yk_payment(payment_id)
        except Exception as exc:
            logger.error("Poll error for user %s payment %s: %s", user_id, payment_id, exc)
            continue  # сеть упала — пробуем на следующем интервале

        if _is_success(yk_payment):
            try:
                await _activate_subscription(user_id, yk_payment)
                await bot.send_message(
                    user_id,
                    "✅ <b>Оплата подтверждена!</b>\n\n"
                    "Подписка активирована. Открой /menu чтобы получить ссылку на VPN.",
                )
                logger.info(
                    "Payment %s confirmed for user %s (elapsed %ds)",
                    payment_id, user_id, elapsed,
                )
            except Exception as exc:
                logger.error("Subscription activation failed for user %s: %s", user_id, exc)
                await bot.send_message(
                    user_id,
                    "✅ Оплата принята, но произошла ошибка при активации подписки.\n"
                    "Напиши в поддержку — разберёмся.",
                )
            _polling_tasks.pop(user_id, None)
            return

        if _is_canceled(yk_payment):
            await update_payment_status(payment_id, "canceled")
            await clear_pending_payment_for_user(user_id)
            await bot.send_message(
                user_id,
                "❌ <b>Платёж отменён.</b>\n\n"
                "Попробуй оплатить снова — нажми /menu.",
            )
            logger.info("Payment %s canceled for user %s", payment_id, user_id)
            _polling_tasks.pop(user_id, None)
            return

        logger.debug(
            "Payment %s still pending for user %s (elapsed %ds/%ds)",
            payment_id, user_id, elapsed, POLL_TIMEOUT_SEC,
        )

    # Таймаут исчерпан — оплата так и не подтвердилась
    await clear_pending_payment_for_user(user_id)
    _polling_tasks.pop(user_id, None)
    await bot.send_message(
        user_id,
        "❌ <b>Оплата не подтверждена.</b>\n\n"
        "Банк не прислал подтверждение в течение 15 минут.\n"
        "Если деньги были списаны — напиши в поддержку.\n"
        "Попробовать снова: /menu",
    )
    logger.warning("Payment %s timed out for user %s", payment_id, user_id)


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    # Если уже идёт фоновая проверка — не создаём новый платёж
    if user_id in _polling_tasks and not _polling_tasks[user_id].done():
        await callback.answer(
            "Уже проверяем ваш платёж в фоне. Ожидайте уведомления.",
            show_alert=True,
        )
        return

    # Если есть незавершённый платёж в БД (бот перезапустился или юзер нажал "← Назад")
    # — запускаем фоновую проверку по нему, не создаём новый
    existing_payment_id = await get_pending_payment_for_user(user_id)
    if existing_payment_id:
        await callback.answer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "⏳ Найден незавершённый платёж. Проверяю в фоне — "
            "подписка активируется автоматически в течение 5–10 минут.",
        )
        task = asyncio.create_task(
            _poll_payment(user_id, existing_payment_id, callback.bot)
        )
        _polling_tasks[user_id] = task
        return

    try:
        payment_id, url = await create_payment_link(user_id)
    except Exception as exc:
        logger.error("Payment creation error for %s: %s", user_id, exc)
        await callback.answer("Не удалось создать платёж. Попробуй позже.", show_alert=True)
        return

    await save_pending_payment_for_user(user_id, payment_id)

    if url is None:
        # Прямое списание — сразу запускаем фоновую проверку
        await callback.answer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "⏳ Списываем оплату... Подписка активируется автоматически.",
        )
        task = asyncio.create_task(_poll_payment(user_id, payment_id, callback.bot))
        _polling_tasks[user_id] = task
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

    # Если фоновая задача уже крутится — просто подтверждаем
    if user_id in _polling_tasks and not _polling_tasks[user_id].done():
        await callback.answer(
            "Уже проверяем! Подписка активируется автоматически — ждите уведомления.",
            show_alert=True,
        )
        return

    payment_id = await get_pending_payment_for_user(user_id)
    if not payment_id:
        await callback.answer("Нет активного платежа. Начните заново.", show_alert=True)
        return

    # Удаляем сообщение с кнопками и сообщаем что ждать
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "⏳ <b>Проверяем оплату...</b>\n\n"
        "Подписка активируется автоматически. Обычно это занимает до 1 минуты.\n"
        "Мы пришлём уведомление, как только всё подтвердится.",
    )
    await callback.answer()

    # Запускаем фоновый поллинг
    task = asyncio.create_task(_poll_payment(user_id, payment_id, callback.bot))
    _polling_tasks[user_id] = task