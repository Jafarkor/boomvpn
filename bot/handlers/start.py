"""
handlers/start.py — обработка команды /start и /support

Поток для нового пользователя:
  1. Регистрация в БД
  2. Создание подписки в Marzban + БД
  3. Приветствие с уведомлением о подписке
  4. Главное меню
  5. Бонус пригласившему (если есть реферер)

Поток для вернувшегося:
  → Приветствие с кнопкой в меню
"""

import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from bot.database.subscriptions import get_active_subscription
from bot.database.users import get_user, register_user, get_referral_count
from bot.keyboards.user import back_to_menu_kb, menu_kb_no_sub, menu_kb_with_sub, support_kb
from bot.messages import welcome_new, welcome_new_no_sub, welcome_back, menu_text
from bot.services.referral import handle_referral
from bot.services.subscription import create_gift_subscription
from bot.utils.media import send_photo_page

logger = logging.getLogger(__name__)
router = Router()


def _parse_referrer(args: str | None) -> int | None:
    """Извлекает referrer_id из deep-link параметра /start ref_12345."""
    if args and args.startswith("ref_"):
        try:
            return int(args[4:])
        except ValueError:
            pass
    return None


def _ref_link(bot_username: str, user_id: int) -> str:
    return f"t.me/{bot_username}?start=ref_{user_id}"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_user = message.from_user
    args = message.text.split(maxsplit=1)[1] if " " in message.text else None
    referrer_id = _parse_referrer(args)

    existing = await get_user(tg_user.id)
    if existing:
        await message.answer(welcome_back(tg_user.first_name), reply_markup=back_to_menu_kb())
        return

    is_new = await register_user(tg_user, referred_by=referrer_id)
    if not is_new:
        await message.answer(welcome_back(tg_user.first_name), reply_markup=back_to_menu_kb())
        return

    # Создаём подписку ДО отправки приветствия
    try:
        await create_gift_subscription(tg_user.id)
        logger.info("Gift subscription OK for user %s", tg_user.id)
        await message.answer(welcome_new(tg_user.first_name))
    except Exception as exc:
        logger.error("Gift subscription failed for user %s: %s", tg_user.id, exc)
        await message.answer(welcome_new_no_sub(tg_user.first_name))

    # Показываем главное меню
    bot_info = await message.bot.get_me()
    sub = await get_active_subscription(tg_user.id)
    ref_count = await get_referral_count(tg_user.id)
    caption = menu_text(
        sub=sub,
        ref_link=_ref_link(bot_info.username, tg_user.id),
        ref_count=ref_count,
    )
    kb = menu_kb_with_sub() if sub else menu_kb_no_sub()
    await send_photo_page(message, "menu", caption, kb)

    if referrer_id and referrer_id != tg_user.id:
        try:
            await handle_referral(referrer_id, tg_user.id, bot=message.bot)
        except Exception as exc:
            logger.error("Referral handling error: %s", exc)


@router.message(Command("support"))
async def support(message: Message) -> None:
    await send_photo_page(
        message=message,
        page="Support",
        caption="Возникли проблемы или есть какие то вопросы?\n\nНапишите в поддержку  <tg-emoji emoji-id=\"5339267587337370029\">😉</tg-emoji>",
        reply_markup=support_kb())