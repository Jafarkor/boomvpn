"""
handlers/payment.py — процесс оплаты.

Флоу:
  1. Пользователь нажимает «Купить» → создаём платёж в ЮKassa → отдаём ссылку.
  2. Пользователь нажимает «Проверить оплату» → запрашиваем статус у ЮKassa.
  3. При успехе — создаём пользователя в Marzban и подписку в БД.

Финальный шаг (succeeded) также обрабатывается вебхуком ЮKassa.
Здесь — ручная проверка как fallback.
"""

import logging
from aiogram import Router
from aiogram.types import CallbackQuery

from bot.config import PLAN_NAME, PLAN_PRICE, PLAN_DAYS
from bot.database.subscriptions import (
    create_subscription,
    get_active_subscription,
    extend_subscription,
)
from bot.database.payments import (
    create_payment,
    get_payment_by_yukassa_id,
    update_payment_status,
    link_payment_to_subscription,
)
from bot.services.yukassa import create_first_payment, get_payment
from bot.services.marzban import marzban
from bot.keyboards.user import pay_kb, back_to_main_kb, cabinet_kb
from redis.asyncio import Redis

logger = logging.getLogger(__name__)
router = Router(name="payment")

# Ключ Redis для хранения yukassa_payment_id пока юзер ждёт
_PAYMENT_KEY = "pay_id:{user_id}"


def _payment_redis_key(user_id: int) -> str:
    return f"pay_id:{user_id}"


@router.callback_query(lambda c: c.data == "buy")
async def cb_buy(callback: CallbackQuery, redis: Redis) -> None:
    """Создаёт платёж и отдаёт пользователю ссылку."""
    user_id = callback.from_user.id

    # Проверяем — нет ли уже активной подписки
    sub = await get_active_subscription(user_id)
    if sub:
        text = (
            f"У вас уже есть активная подписка до "
            f"<b>{sub['expires_at'].strftime('%d.%m.%Y')}</b>.\n"
            "Хотите всё равно продлить?"
        )
    else:
        text = (
            f"<b>Оформление подписки</b>\n\n"
            f"Тариф: {PLAN_NAME}\n"
            f"Сумма: <b>{PLAN_PRICE} ₽</b>\n"
            f"Срок: {PLAN_DAYS} дней\n\n"
            "Оплата через СБП (без комиссии).\n"
            "После оплаты нажмите «Проверить оплату»."
        )

    try:
        payment_data = create_first_payment(user_id)
    except Exception as e:
        logger.error("YuKassa create payment error: %s", e)
        await callback.answer("Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    # Сохраняем payment_id в Redis на 30 минут
    await redis.set(
        _payment_redis_key(user_id),
        payment_data["id"],
        ex=1800,
    )

    # Сохраняем в БД со статусом pending
    await create_payment(user_id, payment_data["id"])

    await callback.message.edit_text(
        text,
        reply_markup=pay_kb(payment_data["confirmation_url"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "check_payment")
async def cb_check_payment(callback: CallbackQuery, redis: Redis) -> None:
    """Пользователь вручную проверяет статус платежа."""
    user_id = callback.from_user.id
    payment_id_bytes = await redis.get(_payment_redis_key(user_id))

    if not payment_id_bytes:
        await callback.answer("Сессия платежа истекла. Создайте новый.", show_alert=True)
        return

    payment_id = payment_id_bytes.decode() if isinstance(payment_id_bytes, bytes) else payment_id_bytes

    try:
        payment_info = get_payment(payment_id)
    except Exception as e:
        logger.error("YuKassa get payment error: %s", e)
        await callback.answer("Не удалось проверить платёж.", show_alert=True)
        return

    status = payment_info["status"]

    if status == "succeeded":
        await _activate_subscription(
            user_id=user_id,
            payment_id=payment_id,
            payment_method_id=payment_info["payment_method_id"] if payment_info["saved"] else None,
        )
        await redis.delete(_payment_redis_key(user_id))
        sub = await get_active_subscription(user_id)
        await callback.message.edit_text(
            "✅ Оплата прошла! Подписка активирована.\n\nПерейдите в личный кабинет для получения конфига.",
            reply_markup=cabinet_kb(has_subscription=True, auto_renew=sub["auto_renew"] if sub else True),
            parse_mode="HTML",
        )
    elif status == "canceled":
        await update_payment_status(payment_id, "canceled")
        await redis.delete(_payment_redis_key(user_id))
        await callback.message.edit_text(
            "❌ Платёж отменён. Попробуйте снова.",
            reply_markup=back_to_main_kb(),
        )
    else:
        await callback.answer("Платёж ещё не завершён. Подождите немного.", show_alert=True)


async def _activate_subscription(
    user_id: int,
    payment_id: str,
    payment_method_id: str | None,
) -> None:
    """
    Создаёт/продлевает подписку после успешной оплаты.
    Вызывается и из обработчика кнопки, и из вебхука ЮKassa.
    """
    # Идемпотентность — проверяем, не обработан ли уже платёж
    existing = await get_payment_by_yukassa_id(payment_id)
    if existing and existing["status"] == "succeeded":
        return  # уже обработан

    await update_payment_status(payment_id, "succeeded")

    # Есть ли уже активная подписка? Тогда продлеваем
    active_sub = await get_active_subscription(user_id)
    if active_sub:
        await extend_subscription(active_sub["id"])
        await marzban.extend_user(active_sub["marzban_username"])
        await link_payment_to_subscription(payment_id, active_sub["id"])
        return

    # Создаём нового пользователя в Marzban
    try:
        marzban_user = await marzban.create_user(user_id)
    except Exception as e:
        logger.error("Marzban create user error: %s", e)
        return

    # Создаём подписку в БД
    sub_id = await create_subscription(
        user_id=user_id,
        marzban_username=marzban_user["username"],
        payment_method_id=payment_method_id,
    )
    await link_payment_to_subscription(payment_id, sub_id)
