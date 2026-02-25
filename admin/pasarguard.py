"""
pasarguard.py — лёгкий HTTP-клиент PasarGuard для admin-панели.
Без состояния (stateless): каждый вызов открывает сессию и закрывает её.
"""

import os
import secrets
import string
from datetime import datetime, timedelta

import aiohttp

PASARGUARD_URL:  str = os.environ.get("PASARGUARD_URL", "")
PASARGUARD_USER: str = os.environ.get("PASARGUARD_USERNAME", "")
PASARGUARD_PASS: str = os.environ.get("PASARGUARD_PASSWORD", "")
INBOUND_TAG:     str = os.environ.get("PASARGUARD_INBOUND_TAG", "vless-tcp")
FLOW:            str = os.environ.get("PASARGUARD_FLOW", "xtls-rprx-vision")
PLAN_DAYS:       int = int(os.environ.get("PLAN_DAYS", "30"))


def _gen_username(uid: int) -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"u{uid}_{suffix}"


async def _token(session: aiohttp.ClientSession) -> str:
    async with session.post(
        f"{PASARGUARD_URL}/api/admin/token",
        data={"username": PASARGUARD_USER, "password": PASARGUARD_PASS},
    ) as r:
        r.raise_for_status()
        return (await r.json())["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_user(uid: int) -> dict:
    """Создаёт пользователя в PasarGuard. Возвращает {username, links, subscription_url}."""
    expire_ts = int((datetime.utcnow() + timedelta(days=PLAN_DAYS)).timestamp())
    payload = {
        "username": _gen_username(uid),
        "proxies": {"vless": {"flow": FLOW}},
        "inbounds": {"vless": [INBOUND_TAG]},
        "expire": expire_ts,
        "data_limit": 0,
        "data_limit_reset_strategy": "no_reset",
        "group_ids": [1],  # Группа "ALL" — даёт доступ ко всем серверам
    }
    async with aiohttp.ClientSession() as s:
        token = await _token(s)
        async with s.post(
            f"{PASARGUARD_URL}/api/user", json=payload, headers=_headers(token)
        ) as r:
            r.raise_for_status()
            return await r.json()


async def extend_user(username: str, extra_days: int = PLAN_DAYS) -> None:
    """Продлевает срок пользователя в PasarGuard."""
    async with aiohttp.ClientSession() as s:
        token = await _token(s)
        h = _headers(token)
        async with s.get(f"{PASARGUARD_URL}/api/user/{username}", headers=h) as r:
            r.raise_for_status()
            user = await r.json()
        current = user.get("expire") or int(datetime.utcnow().timestamp())
        new_exp = max(current, int(datetime.utcnow().timestamp())) + extra_days * 86400
        # Передаём все поля пользователя чтобы PasarGuard не сбросил proxies/inbounds
        payload = {
            "proxies": user.get("proxies") or {"vless": {"flow": FLOW}},
            "inbounds": user.get("inbounds") or {"vless": [INBOUND_TAG]},
            "expire": new_exp,
            "data_limit": user.get("data_limit", 0),
            "data_limit_reset_strategy": user.get("data_limit_reset_strategy", "no_reset"),
            "status": "active",
        }
        async with s.put(
            f"{PASARGUARD_URL}/api/user/{username}", json=payload, headers=h
        ) as r:
            r.raise_for_status()


async def delete_user(username: str) -> None:
    """Удаляет пользователя из PasarGuard."""
    async with aiohttp.ClientSession() as s:
        token = await _token(s)
        async with s.delete(
            f"{PASARGUARD_URL}/api/user/{username}", headers=_headers(token)
        ) as r:
            if r.status not in (200, 404):
                r.raise_for_status()
