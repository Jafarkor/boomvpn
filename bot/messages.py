"""
bot/messages.py — все тексты бота в одном месте.

Правило: хэндлеры не содержат строк — только вызовы этого модуля.
"""

from datetime import datetime
from urllib.parse import quote

from bot.config import PLAN_PRICE, PLAN_DAYS, PLAN_NAME, GIFT_DAYS, REFERRAL_BONUS_DAYS, BASE_URL


# ── Приветствие ───────────────────────────────────────────────────────────────

def welcome_new(name: str) -> str:
    """Приветствие нового пользователя — подписка успешно создана."""
    return (
        f"Привет, {name}! <tg-emoji emoji-id=\"5472055112702629499\">👋</tg-emoji>\n\n"
        f"<tg-emoji emoji-id=\"5193085063998224234\">🎁</tg-emoji> <b>Тебе активирована бесплатная подписка на 7 дней</b>\n\n"
        f"Инструкция по подключению в главном меню <b>↓</b>"
    )



def welcome_new_no_sub(name: str) -> str:
    """Приветствие нового пользователя — подписку создать не удалось."""
    return (
        f"Привет, {name}! <tg-emoji emoji-id=\"5472055112702629499\">👋</tg-emoji>\n\n"
        f"⚠️ <b>Не удалось автоматически создать подписку.</b>\n\n"
        f"Напиши в поддержку — мы разберёмся и активируем её вручную."
    )


def welcome_back(name: str) -> str:
    return f"С возвращением, {name}! <tg-emoji emoji-id=\"5472055112702629499\">👋</tg-emoji>\n\nВсё по‑прежнему работает."


# ── Инструкция по подключению ─────────────────────────────────────────────────

def instruction_text(url: str = "") -> str:
    app_link = f"{BASE_URL}/dl/app"
    sub_link = f"{BASE_URL}/dl/sub?url={quote(url, safe='')}" if url else ""

    step2 = (
        f"2️⃣ Перейди по <a href=\"{sub_link}\">ссылке</a></b>"
        if sub_link
        else "2️⃣ Купи подписку, чтобы получить ссылку на VPN</b>"
    )

    return (
        f"1️⃣ <b>Скачай <a href=\"{app_link}\">приложение</a>\n\n"
        f"{step2}"
    )


# ── Главное меню ──────────────────────────────────────────────────────────────

def menu_text(sub: dict | None, ref_link: str, ref_count: int) -> str:
    lines = []

    # Блок подписки
    if sub:
        expires = sub["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        days_left = max(0, (expires - datetime.utcnow()).days)
        lines.append(
            f'<tg-emoji emoji-id="5350404270032166927">🏠</tg-emoji> <b>Подписка</b>\n'
            f"╰ <b>Осталось дней:</b> {days_left}\n"
        )
    else:
        lines.append(
            '<tg-emoji emoji-id="5350404270032166927">🏠</tg-emoji> <b>Подписка</b>\n'
            "╰ Не активна"
        )

    # Блок рефералов
    lines.append(
        f'\n<tg-emoji emoji-id="6001526766714227911">👥</tg-emoji> <b>Друзья</b>\n'
        f"├ <b>Приглашено:</b> {ref_count}\n"
        f"╰ <b> +{REFERRAL_BONUS_DAYS} дней за друга</b>\n"
        f"Ссылка для друзей (нажми, чтобы скопировать):"
        f"<blockquote><code>{ref_link}</code></blockquote>"
    )

    return "\n".join(lines)


# ── Настройки подписки ────────────────────────────────────────────────────────

def settings_text(sub: dict) -> str:
    expires = sub["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    days_left = max(0, (expires - datetime.utcnow()).days)
    auto = sub.get("auto_renew", False)
    auto_icon = '<tg-emoji emoji-id="5411197345968701560">✅</tg-emoji>' if auto else '<tg-emoji emoji-id="5416076321442777828">❌</tg-emoji>'

    return (
        f"<tg-emoji emoji-id=\"5217604963571621845\">📅</tg-emoji> "
        f"Осталось дней: <b>{days_left}</b>\n\n"

        f"<tg-emoji emoji-id=\"5258419835922030550\">🔄</tg-emoji> "
        f"Автопродление: <b>{auto_icon}</b>\n\n"

        f"<i>{'Подписка продлится автоматически — вручную ничего делать не нужно.' if auto else 'Подписка не продлится автоматически. Включи автопродление или продли вручную.'}</i>\n\n"

        f"<tg-emoji emoji-id=\"6244241334320762892\"></tg-emoji> "
    )


# ── Ссылка подписки ───────────────────────────────────────────────────────────

def sub_url_text(url: str) -> str:
    return (
        "<i>Нажми, чтобы скопировать</i>\n\n"
        f"────────────────\n"
        f"<code>{url}</code>\n"
        "────────────────\n\n"
        "<i>Если VPN перестал работать — просто открой меню и обнови ссылку.</i>"
    )


# ── Покупка ───────────────────────────────────────────────────────────────────

def buy_text() -> str:
    return (
        f"<b>Быстрый и безопасный VPN <tg-emoji emoji-id=\"5372917041193828849\">🚀</tg-emoji></b>\n\n"

        f"├ Срок: <b>{PLAN_DAYS} дней</b>\n"
        f"╰ Цена: <b>{PLAN_PRICE} ₽</b>\n\n"

        "После оплаты нажми <b>«<tg-emoji emoji-id=\"5411197345968701560\"></tg-emoji>  Проверить оплату»</b> — "
        "подписка активируется мгновенно."
    )


def payment_success_text() -> str:
    return (
        "<tg-emoji emoji-id=\"5411197345968701560\">✅</tg-emoji> <b>Оплата прошла!</b>\n\n"
        f"Подписка активна на <b>{PLAN_DAYS} дней</b>.\n\n"
        "Нажми <b>«Подключить VPN»</b> в меню и следуй инструкции."
    )


def payment_fail_text() -> str:
    return (
        "<tg-emoji emoji-id=\"5416076321442777828\">❌</tg-emoji> <b>Оплата не найдена.</b>\n\n"
        "Попробуй чуть позже или начни заново через меню."
    )


# ── Реферальная система ───────────────────────────────────────────────────────

def referral_reward_text(days: int) -> str:
    return (
        f"<tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> <b>Твой друг зарегистрировался!</b>\n\n"
        f"Тебе начислено <b>+{days} дней</b> подписки."
    )


# ── Ошибки ────────────────────────────────────────────────────────────────────

ERROR_TEXT = "Что‑то пошло не так. Попробуй ещё раз или напиши в поддержку."
