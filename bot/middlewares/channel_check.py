"""
middlewares/channel_check.py — middleware проверки подписки на канал.

Правильная реализация для aiogram 3:
  - Регистрируется как dp.update.outer_middleware() — срабатывает на КАЖДЫЙ апдейт
  - Bot берётся из data["bot"] (официальный способ по документации aiogram)
  - Event всегда Update — message/callback_query извлекаются вручную
  - Redis-кэш с TTL: 60 сек для подписанных, 10 сек для неподписанных
    → быстро (Redis sub-ms), точно (кэш истекает, Telegram переспрашивается)

Пропускает без проверки:
  - /start (хендлер сам управляет подпиской)
  - callback "check_channel_sub" (иначе зациклится)
  - Апдейты без пользователя
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.keyboards.user import channel_sub_kb
from bot.utils.channel import is_subscribed

logger = logging.getLogger(__name__)

# Ключ Redis: sub_ok:{user_id}
# Значение: b"1" = подписан, b"0" = не подписан
_CACHE_OK_TTL = 60   # секунд — кэшируем факт подписки
_CACHE_NO_TTL = 10   # секунд — кэшируем факт отписки (быстро обнаруживаем)

_SKIP_COMMANDS = ("/start",)
_SKIP_CALLBACKS = ("check_channel_sub",)


class ChannelSubscriptionMiddleware(BaseMiddleware):
    """
    Outer-middleware: проверяет подписку на канал перед любым хендлером.
    Использует Redis-кэш чтобы не дёргать Telegram API на каждое сообщение.
    """

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,           # всегда Update при dp.update.outer_middleware
        data: dict[str, Any],
    ) -> Any:
        bot = data["bot"]        # правильный способ получить Bot в middleware aiogram 3

        # ── Извлекаем пользователя и проверяем, нужно ли пропустить ──────────
        user_id: int | None = None
        reply_target = None       # объект для отправки ответа

        if event.message and event.message.from_user:
            msg = event.message
            user_id = msg.from_user.id
            # /start обрабатывает подписку сам
            if msg.text and any(msg.text.startswith(c) for c in _SKIP_COMMANDS):
                return await handler(event, data)
            reply_target = msg

        elif event.callback_query and event.callback_query.from_user:
            cb = event.callback_query
            user_id = cb.from_user.id
            # check_channel_sub сам проверяет подписку — не блокировать
            if cb.data in _SKIP_CALLBACKS:
                return await handler(event, data)
            reply_target = cb.message

        else:
            # Неизвестный тип апдейта (inline, poll и т.п.) — пропускаем
            return await handler(event, data)

        if user_id is None or reply_target is None:
            return await handler(event, data)

        # ── Проверяем кэш в Redis ─────────────────────────────────────────────
        redis = data.get("redis")
        cache_key = f"sub_ok:{user_id}"
        subscribed: bool | None = None

        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached == b"1":
                    subscribed = True
                elif cached == b"0":
                    subscribed = False
                # None = кэша нет, идём к Telegram
            except Exception as e:
                logger.warning("Redis cache read error: %s", e)

        # ── Если кэша нет — спрашиваем Telegram ──────────────────────────────
        if subscribed is None:
            subscribed = await is_subscribed(user_id, bot)
            if redis:
                try:
                    ttl = _CACHE_OK_TTL if subscribed else _CACHE_NO_TTL
                    await redis.setex(cache_key, ttl, "1" if subscribed else "0")
                except Exception as e:
                    logger.warning("Redis cache write error: %s", e)

        # ── Подписан — пропускаем ─────────────────────────────────────────────
        if subscribed:
            return await handler(event, data)

        # ── Не подписан — блокируем и предлагаем подписаться ─────────────────
        text = "<tg-emoji emoji-id=\"5429309601013056582\">💙</tg-emoji> Для доступа к боту необходимо подписаться на канал:"
        try:
            if event.callback_query:
                await event.callback_query.answer()
            await reply_target.answer(text, reply_markup=channel_sub_kb())
        except Exception as e:
            logger.error("Failed to send subscription prompt to user %s: %s", user_id, e)
        # НЕ вызываем handler — обработка заблокирована
