import logging
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from redis.asyncio import Redis
from datetime import timedelta

logger = logging.getLogger(__name__)

RATE_LIMIT = 0.4  # секунд между запросами


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware анти-флуд на базе Redis."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        key = f"throttle:{user.id}"
        # SET NX EX — атомарная операция: установить только если не существует
        result = await self._redis.set(key, "1", px=int(float(RATE_LIMIT) * 1000), nx=True)
        if result is None:
            # Ключ уже существует → пользователь слишком часто шлёт
            logger.debug("Throttled user %s", user.id)
            return None  # прерываем цепочку, апдейт игнорируется

        return await handler(event, data)
