"""
handlers/start.py — обработка команды /start.

Поток для нового пользователя:
  1. Приветствие с сообщением о подарочной подписке
  2. Создание реальной подписки в Marzban
  3. Инструкция по подключению
  4. Начисление бонуса пригласившему (если есть)

Поток для вернувшегося пользователя:
  → Приветствие и кнопка в меню
"""

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database.users import get_user, register_user
from bot.keyboards.user import instruction_kb, back_to_menu_kb
from bot.messages import welcome_new, welcome_back, INSTRUCTION_TEXT
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
        # Гонка записей — пользователь уже существует
        await message.answer(welcome_back(tg_user.first_name), reply_markup=back_to_menu_kb())
        return

    await message.answer(welcome_new(tg_user.first_name))

    try:
        await create_gift_subscription(tg_user.id)
    except Exception as exc:
        logger.error("Gift subscription failed for %s: %s", tg_user.id, exc)

    await message.answer(INSTRUCTION_TEXT, reply_markup=instruction_kb(), disable_web_page_preview=True)

    if referrer_id and referrer_id != tg_user.id:
        try:
            await handle_referral(referrer_id, tg_user.id, bot=message.bot)
        except Exception as exc:
            logger.error("Referral handling error: %s", exc)
