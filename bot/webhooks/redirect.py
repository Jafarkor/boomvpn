"""
webhooks/redirect.py — умные редиректы для инструкции по подключению.

GET /dl/app
    Определяет устройство по User-Agent и перенаправляет в нужный магазин:
      • iOS / macOS  → App Store (Streisand)
      • Android      → Google Play (v2RayTun)
      • Всё остальное → GitHub (Nekoray / Windows)

GET /dl/sub?url=<subscription_url>
    Определяет устройство и открывает нужный deep link для импорта подписки:
      • iOS          → streisand://import/<subscription_url>
      • Android      → v2raytun://import/<subscription_url>
      • Всё остальное → перенаправляет прямо на subscription_url
"""

import logging
from urllib.parse import quote, unquote

from aiohttp import web

logger = logging.getLogger(__name__)

# ── Ссылки на приложения ──────────────────────────────────────────────────────

APP_IOS     = "https://apps.apple.com/ru/app/streisand/id6450534064"
APP_ANDROID = "https://play.google.com/store/apps/details?id=com.v2raytun.android"
APP_WINDOWS = "https://github.com/MatsuriDayo/nekoray/releases/latest"

# ── Определение платформы ─────────────────────────────────────────────────────

def _detect_platform(request: web.Request) -> str:
    """Возвращает 'ios', 'android' или 'other' по User-Agent."""
    ua = request.headers.get("User-Agent", "").lower()
    if any(x in ua for x in ("iphone", "ipad", "macintosh", "mac os x")):
        return "ios"
    if "android" in ua:
        return "android"
    return "other"


# ── Эндпоинт 1: скачать приложение ───────────────────────────────────────────

async def redirect_app(request: web.Request) -> web.Response:
    """Редиректит в нужный магазин приложений."""
    platform = _detect_platform(request)
    if platform == "ios":
        target = APP_IOS
    elif platform == "android":
        target = APP_ANDROID
    else:
        target = APP_WINDOWS
    logger.info("redirect_app: platform=%s → %s", platform, target)
    raise web.HTTPFound(location=target)


# ── Эндпоинт 2: добавить подписку ────────────────────────────────────────────

async def redirect_sub(request: web.Request) -> web.Response:
    """
    Открывает нужный deep link для импорта подписки в VPN-приложение.

    Query-параметр:
        url — ссылка подписки (URL-encoded).
    """
    raw_url = request.rel_url.query.get("url", "")
    if not raw_url:
        return web.Response(status=400, text="Missing 'url' parameter")

    sub_url = unquote(raw_url)
    platform = _detect_platform(request)

    if platform == "ios":
        # Streisand импортирует подписку по deep link:
        # streisand://import/<encoded_url>
        target = f"streisand://import/{quote(sub_url, safe='')}"
    elif platform == "android":
        # v2RayTun импортирует подписку по deep link:
        # v2raytun://import/<encoded_url>
        target = f"v2raytun://import/{quote(sub_url, safe='')}"
    else:
        # На Windows / десктопе открываем ссылку напрямую —
        # пользователь скопирует её вручную в Nekoray.
        target = sub_url

    logger.info("redirect_sub: platform=%s → %s", platform, target)
    raise web.HTTPFound(location=target)


# ── Регистрация маршрутов ─────────────────────────────────────────────────────

def register_redirect_routes(app: web.Application) -> None:
    app.router.add_get("/dl/app", redirect_app)
    app.router.add_get("/dl/sub", redirect_sub)
