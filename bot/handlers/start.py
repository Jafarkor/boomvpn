"""
handlers/start.py — обработка команды /start.

Поток для нового пользователя:
  1. Регистрация в БД
  2. Создание подписки в Marzban (блокирующий вызов)
  3. Приветствие — отправляется ТОЛЬКО после успешного создания подписки
  4. Инструкция по подключению
  5. Бонус пригласившему (если есть реферер)

Поток для вернувшегося:
  → Приветствие с кнопкой в меню
"""

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database.users import get_user, register_user
from bot.keyboards.user import instruction_kb, back_to_menu_kb
from bot.messages import welcome_new, welcome_new_no_sub, welcome_back, INSTRUCTION_TEXT
from bot.services.referral import handle_referral
from bot.services.subscription import create_gift_subscription

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

    # Создаём подписку ДО отправки приветствия.
    # Пользователь видит сообщение о подписке только если она реально создана.
    sub_ok = False
    try:
        await create_gift_subscription(tg_user.id)
        sub_ok = True
    except Exception as exc:
        logger.error("Gift subscription failed for user %s: %s", tg_user.id, exc)

    if sub_ok:
        await message.answer(welcome_new(tg_user.first_name))
    else:
        await message.answer(welcome_new_no_sub(tg_user.first_name))

    await message.answer(INSTRUCTION_TEXT, reply_markup=instruction_kb())

    if referrer_id and referrer_id != tg_user.id:
        try:
            await handle_referral(referrer_id, tg_user.id, bot=message.bot)
        except Exception as exc:
            logger.error("Referral handling error: %s", exc)
