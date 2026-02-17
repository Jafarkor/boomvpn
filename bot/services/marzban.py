"""
services/marzban.py — клиент Marzban REST API.

Документация Marzban: https://github.com/Gozargah/Marzban
Все методы используют один aiohttp.ClientSession на время жизни объекта.
"""

import aiohttp
import secrets
import string
from datetime import datetime, timedelta

from bot.config import (
    MARZBAN_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
    MARZBAN_INBOUND_TAG,
    PLAN_DAYS,
)


def _random_username(prefix: str = "vpn", length: int = 8) -> str:
    """Генерирует уникальное имя пользователя для Marzban."""
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{suffix}"


class MarzbanClient:
    """Тонкая обёртка над Marzban HTTP API."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    # ── Сессия ────────────────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(base_url=MARZBAN_URL)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Авторизация ───────────────────────────────────────────────────────────

    async def _authenticate(self) -> str:
        """Получает JWT-токен через логин/пароль."""
        session = await self._get_session()
        async with session.post(
            "/api/admin/token",
            data={"username": MARZBAN_USERNAME, "password": MARZBAN_PASSWORD},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            self._token = data["access_token"]
            return self._token

    async def _headers(self) -> dict:
        """Возвращает заголовки с актуальным токеном."""
        token = self._token or await self._authenticate()
        return {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Выполняет запрос, при 401 обновляет токен и повторяет."""
        session = await self._get_session()
        headers = await self._headers()
        async with session.request(method, path, headers=headers, **kwargs) as resp:
            if resp.status == 401:
                # Токен протух — перелогиниваемся
                self._token = None
                headers = await self._headers()
                async with session.request(method, path, headers=headers, **kwargs) as r:
                    r.raise_for_status()
                    return await r.json()
            resp.raise_for_status()
            return await resp.json()

    # ── Публичные методы ──────────────────────────────────────────────────────

    async def create_user(self, user_id: int) -> dict:
        """
        Создаёт пользователя в Marzban.
        Возвращает dict с полями: username, links (список VLESS-ссылок).
        """
        username = _random_username(prefix=f"u{user_id}")
        expire_ts = int(
            (datetime.utcnow() + timedelta(days=PLAN_DAYS)).timestamp()
        )
        payload = {
            "username": username,
            "proxies": {"vless": {"flow": ""}},
            "inbounds": {"vless": [MARZBAN_INBOUND_TAG]},
            "expire": expire_ts,
            "data_limit": 0,          # 0 = без лимита трафика
            "data_limit_reset_strategy": "no_reset",
        }
        return await self._request("POST", "/api/user", json=payload)

    async def get_user(self, username: str) -> dict | None:
        """Получает информацию о пользователе из Marzban."""
        try:
            return await self._request("GET", f"/api/user/{username}")
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                return None
            raise

    async def extend_user(self, username: str, extra_days: int = PLAN_DAYS) -> None:
        """Продлевает срок действия пользователя в Marzban."""
        user = await self.get_user(username)
        if not user:
            return
        current = user.get("expire") or int(datetime.utcnow().timestamp())
        base = max(current, int(datetime.utcnow().timestamp()))
        new_expire = base + extra_days * 86400
        await self._request(
            "PUT",
            f"/api/user/{username}",
            json={"expire": new_expire},
        )

    async def delete_user(self, username: str) -> None:
        """Удаляет пользователя из Marzban."""
        await self._request("DELETE", f"/api/user/{username}")

    async def get_vless_link(self, username: str) -> str | None:
        """Возвращает первую VLESS-ссылку пользователя или None."""
        user = await self.get_user(username)
        if not user:
            return None
        links: list[str] = user.get("links", [])
        return next((l for l in links if l.startswith("vless://")), None)

    async def get_subscription_url(self, username: str) -> str | None:
        """Возвращает subscription_url для импорта в клиент (если доступен)."""
        user = await self.get_user(username)
        return user.get("subscription_url") if user else None


# Глобальный клиент — создаётся один раз
marzban = MarzbanClient()
