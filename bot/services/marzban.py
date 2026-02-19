"""
services/marzban.py — клиент для работы с Marzban API.

Все обращения к Marzban идут через этот модуль.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from bot.config import (
    MARZBAN_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
    MARZBAN_INBOUND_TAG,
    MARZBAN_FLOW,
)

logger = logging.getLogger(__name__)

_TOKEN: str | None = None
_TOKEN_EXPIRES: datetime = datetime.min


class MarzbanClient:
    """Тонкий клиент к Marzban REST API с автообновлением токена."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    # ── Сессия ────────────────────────────────────────────────────────────────

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(base_url=MARZBAN_URL)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Авторизация ───────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        global _TOKEN, _TOKEN_EXPIRES
        if _TOKEN and datetime.utcnow() < _TOKEN_EXPIRES:
            return _TOKEN

        session = self._get_session()
        async with session.post(
            "/api/admin/token",
            data={"username": MARZBAN_USERNAME, "password": MARZBAN_PASSWORD},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        _TOKEN = data["access_token"]
        _TOKEN_EXPIRES = datetime.utcnow() + timedelta(minutes=50)
        return _TOKEN

    async def _headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    # ── Пользователи ──────────────────────────────────────────────────────────

    async def create_user(self, username: str, days: int) -> dict[str, Any]:
        """Создаёт пользователя в Marzban и возвращает данные."""
        expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
        payload = {
            "username": username,
            "proxies": {
                "vless": {
                    "flow": MARZBAN_FLOW,
                    "id": None,
                }
            },
            "inbounds": {"vless": [MARZBAN_INBOUND_TAG]},
            "expire": expire_ts,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }
        session = self._get_session()
        async with session.post(
            "/api/user", json=payload, headers=await self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def extend_user(self, username: str, additional_days: int) -> None:
        """Продлевает подписку пользователя на additional_days дней."""
        session = self._get_session()
        headers = await self._headers()

        async with session.get(f"/api/user/{username}", headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()

        current_expire = data.get("expire") or int(datetime.utcnow().timestamp())
        new_expire = max(current_expire, int(datetime.utcnow().timestamp()))
        new_expire += additional_days * 86400

        async with session.put(
            f"/api/user/{username}",
            json={"expire": new_expire, "status": "active"},
            headers=headers,
        ) as resp:
            resp.raise_for_status()

    async def get_subscription_url(self, username: str) -> str:
        """
        Возвращает полную ссылку подписки из Marzban API.
        Marzban может вернуть относительный путь — добавляем базовый URL.
        """
        session = self._get_session()
        async with session.get(
            f"/api/user/{username}", headers=await self._headers()
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        path = data["subscription_url"]
        # Если Marzban вернул относительный путь — добавляем базу
        if path.startswith("/"):
            return f"{MARZBAN_URL.rstrip('/')}{path}"
        return path

    async def delete_user(self, username: str) -> None:
        """Удаляет пользователя из Marzban."""
        session = self._get_session()
        async with session.delete(
            f"/api/user/{username}", headers=await self._headers()
        ) as resp:
            if resp.status not in (200, 404):
                resp.raise_for_status()


# Глобальный экземпляр — используется во всём проекте
marzban = MarzbanClient()
