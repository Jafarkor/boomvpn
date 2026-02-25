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
    PASARGUARD_USER_GROUP,
)

logger = logging.getLogger(__name__)

_TOKEN: str | None = None
_TOKEN_EXPIRES: datetime = datetime.min
_GROUP_ID_CACHE: dict[str, int] = {}  # кеш: name → id


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

    # ── Группы пользователей ──────────────────────────────────────────────────

    async def get_group_id(self, group_name: str) -> int | None:
        """
        Возвращает ID группы по её имени.
        Результат кешируется на время жизни процесса.
        Если группа не найдена — возвращает None и пишет WARNING.
        """
        if group_name in _GROUP_ID_CACHE:
            return _GROUP_ID_CACHE[group_name]

        session = self._get_session()
        async with session.get(
            "/api/user_groups", headers=await self._headers()
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        # PasarGuard возвращает {"user_groups": [...]} или просто список
        groups = data.get("user_groups", data) if isinstance(data, dict) else data
        for g in groups:
            _GROUP_ID_CACHE[g["name"]] = g["id"]

        group_id = _GROUP_ID_CACHE.get(group_name)
        if group_id is None:
            logger.warning(
                "PasarGuard: group '%s' not found. User will be created without group.", group_name
            )
        return group_id

    # ── Пользователи ──────────────────────────────────────────────────────────

    async def create_user(self, username: str, days: int) -> dict[str, Any]:
        """
        Создаёт пользователя в PasarGuard и возвращает данные.

        PasarGuard генерирует UUID автоматически — не передаём id в proxies.
        Пользователь автоматически добавляется в группу PASARGUARD_USER_GROUP (по умолчанию "ALL").
        """
        expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())

        # Получаем ID группы (с кешем, безопасно при ошибке)
        group_id = None
        if PASARGUARD_USER_GROUP:
            try:
                group_id = await self.get_group_id(PASARGUARD_USER_GROUP)
            except Exception as exc:
                logger.warning("Could not fetch group id for '%s': %s", PASARGUARD_USER_GROUP, exc)

        payload = {
            "username": username,
            "proxies": {
                "vless": {
                    "flow": PASARGUARD_FLOW,
                }
            },
            "inbounds": {"vless": [PASARGUARD_INBOUND_TAG]},
            "expire": expire_ts,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }

        if group_id is not None:
            payload["group_ids"] = [group_id]

        session = self._get_session()
        async with session.post(
            "/api/user", json=payload, headers=await self._headers()
        ) as resp:
            if resp.status == 409:
                raise ValueError(f"User '{username}' already exists in PasarGuard")
            resp.raise_for_status()
            data = await resp.json()
            logger.info(
                "PasarGuard: created user '%s' for %d days (group: %s)",
                username, days, PASARGUARD_USER_GROUP or "none",
            )
            return data

    async def extend_user(self, username: str, additional_days: int) -> None:
        """
        Продлевает подписку пользователя на additional_days дней.

        ИСПРАВЛЕНО: явно проверяем наличие vless-ключа в proxies/inbounds,
        т.к. пустой dict является truthy и fallback через `or` не срабатывал.
        Это приводило к тому, что PUT отправлял пустые proxies/inbounds,
        и PasarGuard сохранял подписку без конфигурации.
        """
        session = self._get_session()
        headers = await self._headers()

        async with session.get(f"/api/user/{username}", headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()

        current_expire = data.get("expire") or int(datetime.utcnow().timestamp())
        new_expire = max(current_expire, int(datetime.utcnow().timestamp()))
        new_expire += additional_days * 86400

        # ИСПРАВЛЕНИЕ: пустой dict ({}) — truthy, поэтому `data.get(...) or fallback`
        # не работает. Явно проверяем наличие ключа "vless" внутри словаря.
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
        }

        async with session.put(
            f"/api/user/{username}",
            json=payload,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            logger.info(
                "PasarGuard: extended user '%s' by %d days", username, additional_days
            )

    async def get_subscription_url(self, username: str) -> str:
        """
        Возвращает полную ссылку подписки из PasarGuard API.
        Если панель вернула относительный путь — добавляем базовый URL.
        """
        session = self._get_session()
        async with session.get(
            f"/api/user/{username}", headers=await self._headers()
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        path = data["subscription_url"]
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
