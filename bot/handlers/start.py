"""
handlers/start.py — обработка команды /start.

Поток:
  Новый пользователь → приветствие → подарочная подписка → инструкция
  Существующий      → приветствие с возвращением → /menu
"""

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database.users import get_user, register_user, get_referral_count
from bot.keyboards.user import instruction_kb, back_to_menu_kb
from bot.messages import welcome_new, welcome_back, INSTRUCTION_TEXT
from bot.services.referral import handle_referral
from bot.services.subscription import create_gift_subscription

logger = logging.getLogger(__name__)
router = Router()


def _parse_referrer(command_args: str | None) -> int | None:
    """Извлекает referrer_id из параметра /start ref_12345."""
    if not command_args:
        return None
    if command_args.startswith("ref_"):
        try:
            return int(command_args[4:])
        except ValueError:
            pass
    return None


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_user = message.from_user
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    referrer_id = _parse_referrer(args)

    # Проверяем, существует ли пользователь
    existing = await get_user(tg_user.id)

    if existing:
        # Возвращающийся пользователь
        await message.answer(
            welcome_back(tg_user.first_name),
            reply_markup=back_to_menu_kb(),
        )
        return

    # Новый пользователь — регистрируем
    is_new = await register_user(tg_user, referred_by=referrer_id)

    if not is_new:
        # Гонка — пользователь уже был создан параллельно
        await message.answer(
            welcome_back(tg_user.first_name),
            reply_markup=back_to_menu_kb(),
        )
        return

    # Шаг 1: Приветствие
    await message.answer(welcome_new(tg_user.first_name))

    # Шаг 2: Создаём подарочную подписку
    try:
        await create_gift_subscription(tg_user.id)
    except Exception as exc:
        logger.error("Failed to create gift subscription for %s: %s", tg_user.id, exc)

    # Шаг 3: Инструкция
    await message.answer(
        INSTRUCTION_TEXT,
        reply_markup=instruction_kb(),
    )

    # Шаг 4: Начисляем бонус пригласившему
    if referrer_id and referrer_id != tg_user.id:
        try:
            await handle_referral(referrer_id, tg_user.id)
        except Exception as exc:
            logger.error("Referral handling error: %s", exc)
