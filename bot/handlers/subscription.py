"""
handlers/subscription.py — ссылка подписки, инструкция, настройки, автопродление.

Все экраны отображаются как фото с caption (через edit_photo_page).
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.subscriptions import get_active_subscription, toggle_auto_renew
from bot.keyboards.user import settings_kb, back_to_menu_kb
from bot.messages import settings_text, instruction_text
from bot.middlewares.channel_check import is_subscribed
from bot.config import CHANNEL_USERNAME
from bot.services.subscription import get_subscription_url
from bot.utils.media import edit_photo_page

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "instruction")
async def cb_instruction(callback: CallbackQuery) -> None:
    # ИСПРАВЛЕНО: используем get_subscription_url из services/subscription.py,
    # который берёт URL из БД, а не запрашивает из PasarGuard каждый раз.
    # Это гарантирует стабильность ссылки между нажатиями кнопки.
    url = await get_subscription_url(callback.from_user.id) or ""

    await edit_photo_page(
        callback,
        page="instruction",
        caption=instruction_text(url),
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    await edit_photo_page(
        callback,
        page="settings",
        caption=settings_text(sub),
        reply_markup=settings_kb(sub.get("auto_renew", False)),
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_renew")
async def cb_toggle_renew(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не активна", show_alert=True)
        return

    new_state = not sub.get("auto_renew", False)
    await toggle_auto_renew(sub["id"], new_state)
    sub["auto_renew"] = new_state

    await edit_photo_page(
        callback,
        page="settings",
        caption=settings_text(sub),
        reply_markup=settings_kb(new_state),
    )
    await callback.answer("Автопродление " + ("включено ✅" if new_state else "выключено ❌"))


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery) -> None:
    """Обработчик проверки подписки на канал.
    После успешной подписки:
      - регистрирует нового пользователя и выдаёт 7-дневный бонус (если первый вход)
      - открывает главное меню
    """
    try:
        if not await is_subscribed(callback.from_user.id, callback.bot):
            await callback.answer(
                f"❌ Вы ещё не подписались на канал {CHANNEL_USERNAME}",
                show_alert=True,
            )
            return

        await callback.answer("✅ Спасибо за подписку!")
        await callback.message.delete()

        tg_user = callback.from_user

        # Импортируем здесь, чтобы не создавать циклических зависимостей
        from bot.database.users import get_user, register_user, get_referral_count
        from bot.services.subscription import create_gift_subscription
        from bot.messages import welcome_new, welcome_new_no_sub, menu_text
        from bot.keyboards.user import menu_kb_with_sub, menu_kb_no_sub
        from bot.database.subscriptions import get_active_subscription
        from bot.utils.media import send_photo_page

        # Если пользователь новый — регистрируем и выдаём бонусную подписку
        existing = await get_user(tg_user.id)
        if not existing:
            is_new = await register_user(tg_user, referred_by=None)
            if is_new:
                try:
                    await create_gift_subscription(tg_user.id)
                    logger.info("Gift subscription created for new user %s after channel sub", tg_user.id)
                    await callback.message.answer(welcome_new(tg_user.first_name))
                except Exception as exc:
                    logger.error("Gift subscription failed for user %s: %s", tg_user.id, exc)
                    await callback.message.answer(welcome_new_no_sub(tg_user.first_name))

        # Открываем главное меню
        bot_info = await callback.bot.get_me()
        ref_link = f"t.me/{bot_info.username}?start=ref_{tg_user.id}"
        sub = await get_active_subscription(tg_user.id)
        ref_count = await get_referral_count(tg_user.id)
        caption = menu_text(sub=sub, ref_link=ref_link, ref_count=ref_count)
        kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
        await send_photo_page(callback.message, "menu", caption, kb)

    except Exception as e:
        logger.error(f"Error in subscription check: {e}")
        await callback.answer("Произошла ошибка при проверке подписки.", show_alert=True)
