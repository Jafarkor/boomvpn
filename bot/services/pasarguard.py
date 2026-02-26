"""
services/pasarguard.py — клиент для работы с PasarGuard API.

PasarGuard — форк Marzban с идентичным REST API.
Все обращения к PasarGuard идут через этот модуль.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from bot.config import (
    PASARGUARD_URL,
    PASARGUARD_USERNAME,
    PASARGUARD_PASSWORD,
    PASARGUARD_INBOUND_TAG,
    PASARGUARD_FLOW,
)

logger = logging.getLogger(__name__)

_TOKEN: str | None = None
_TOKEN_EXPIRES: datetime = datetime.min



def _parse_expire(value) -> int:
    """
    PasarGuard может вернуть expire как Unix timestamp (int/float/str)
    или как ISO-строку ('2026-03-04T19:34:50Z'). Конвертируем оба варианта.
    """
    if not value:
        return int(__import__('datetime').datetime.utcnow().timestamp())
    s = str(value).strip()
    # Если строка содержит буквы — скорее всего ISO-формат
    if any(c.isalpha() for c in s):
        from datetime import datetime, timezone
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(s.replace("+00:00", "Z").replace("Z", ""), 
                                       fmt.rstrip("Z").rstrip("%z"))
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                continue
    return int(float(s))

class PasarGuardClient:
    """Тонкий клиент к PasarGuard REST API с автообновлением токена."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    # ── Сессия ────────────────────────────────────────────────────────────────

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(base_url=PASARGUARD_URL)
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
            data={"username": PASARGUARD_USERNAME, "password": PASARGUARD_PASSWORD},
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

    async def get_user(self, username: str) -> dict[str, Any] | None:
        """
        Возвращает данные пользователя по username или None если не найден (404).
        Используется для проверки существования перед созданием/продлением.
        """
        session = self._get_session()
        async with session.get(
            f"/api/user/{username}", headers=await self._headers()
        ) as resp:
            if resp.status == 404:
                return None
            if not resp.ok:
                body = await resp.text()
                logger.error(
                    "PasarGuard: GET /api/user/%s returned %d: %s",
                    username, resp.status, body,
                )
                resp.raise_for_status()
            return await resp.json()

    async def create_user(self, username: str, days: int) -> dict[str, Any]:
        """
        Создаёт пользователя в PasarGuard и возвращает данные.
        Если пользователь уже существует (409) — бросает ValueError.
        """
        expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
        payload = {
            "username": username,
            "proxies": {"vless": {"flow": PASARGUARD_FLOW}},
            "inbounds": {"vless": [PASARGUARD_INBOUND_TAG]},
            "expire": expire_ts,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "group_ids": [1],  # Группа "ALL" — даёт доступ ко всем серверам
        }
        session = self._get_session()
        async with session.post(
            "/api/user", json=payload, headers=await self._headers()
        ) as resp:
            if resp.status == 409:
                raise ValueError(f"User '{username}' already exists in PasarGuard")
            if not resp.ok:
                body = await resp.text()
                logger.error(
                    "PasarGuard: POST /api/user returned %d for '%s': %s",
                    resp.status, username, body,
                )
                resp.raise_for_status()
            data = await resp.json()
            logger.info("PasarGuard: created user '%s' for %d days", username, days)
            return data

    async def ensure_user(self, username: str, days: int) -> None:
        """
        Создаёт пользователя если не существует, продлевает если уже есть.
        Стратегия GET-first: проверяем наличие через GET перед созданием,
        чтобы не зависеть от конкретного HTTP-кода ошибки дубликата
        (PasarGuard может вернуть 400/409/422).
        """
        data = await self.get_user(username)
        if data is not None:
            logger.info("PasarGuard: user '%s' exists, extending by %d days", username, days)
            await self.extend_user(username, days)
        else:
            await self.create_user(username, days=days)

    async def extend_user(self, username: str, additional_days: int) -> None:
        """
        Продлевает подписку пользователя на additional_days дней.

        Если пользователь не найден — создаёт его (fallback при рассинхроне DB/панели).
        
        """
        data = await self.get_user(username)
        if data is None:
            logger.warning(
                "PasarGuard: user '%s' not found during extend, creating instead", username
            )
            await self.create_user(username, days=additional_days)
            return

        current_expire = _parse_expire(data.get("expire"))
        new_expire = max(current_expire, int(datetime.utcnow().timestamp()))
        new_expire += additional_days * 86400

        # Явно проверяем наличие ключа "vless" — пустой dict ({}) truthy,
        # поэтому `data.get(...) or fallback` не работает.
        existing_proxies = data.get("proxies") or {}
        existing_inbounds = data.get("inbounds") or {}

        proxies = (
            existing_proxies
            if existing_proxies.get("vless")
            else {"vless": {"flow": PASARGUARD_FLOW}}
        )
        inbounds = (
            existing_inbounds
            if existing_inbounds.get("vless")
            else {"vless": [PASARGUARD_INBOUND_TAG]}
        )

        payload = {
            "proxies": proxies,
            "inbounds": inbounds,
            "expire": new_expire,
            "data_limit": data.get("data_limit", 0),
            "data_limit_reset_strategy": data.get("data_limit_reset_strategy", "no_reset"),
            "status": "active",
            "group_ids": [1],
        }

        session = self._get_session()
        async with session.put(
            f"/api/user/{username}",
            json=payload,
            headers=await self._headers(),
        ) as resp:
            if not resp.ok:
                body = await resp.text()
                logger.error(
                    "PasarGuard: PUT /api/user/%s returned %d: %s",
                    username, resp.status, body,
                )
                resp.raise_for_status()
            logger.info(
                "PasarGuard: extended user '%s' by %d days (new expire ts: %d)",
                username, additional_days, new_expire,
            )

    async def get_subscription_url(self, username: str) -> str:
        """
        Возвращает полную ссылку подписки из PasarGuard API.
        Если панель вернула относительный путь — добавляем базовый URL.
        Если пользователь не найден или url пустой — бросает ValueError.
        """
        data = await self.get_user(username)
        if data is None:
            raise ValueError(f"User '{username}' not found in PasarGuard")

        path = data.get("subscription_url") or ""
        if not path:
            raise ValueError(f"PasarGuard returned empty subscription_url for '{username}'")
        if path.startswith("/"):
            return f"{PASARGUARD_URL.rstrip('/')}{path}"
        return path

    async def delete_user(self, username: str) -> None:
        """Удаляет пользователя из PasarGuard."""
        session = self._get_session()
        async with session.delete(
            f"/api/user/{username}", headers=await self._headers()
        ) as resp:
            if resp.status not in (200, 404):
                resp.raise_for_status()


# Глобальный экземпляр — используется во всём проекте
pasarguard = PasarGuardClient()
