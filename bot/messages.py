"""
bot/messages.py — все тексты бота в одном месте.

Правило: хэндлеры не содержат строк — только вызовы этого модуля.
"""

from datetime import datetime
from bot.config import PLAN_PRICE, PLAN_DAYS, PLAN_NAME, GIFT_DAYS, REFERRAL_BONUS_DAYS


# ── Приветствие ───────────────────────────────────────────────────────────────

def welcome_new(name: str, sub_url: str) -> str:
    """Приветствие нового пользователя — подписка успешно создана."""
    return (
        f"👋 Привет, {name}!\n\n"
        f"🎁 <b>Тебе активирована бесплатная подписка на {GIFT_DAYS} дней.</b>\n\n"
        f"Вот твоя ссылка подписки — скопируй её и вставь в VPN‑приложение:\n\n"
        f"<code>{sub_url}</code>\n\n"
        f"Ниже — пошаговая инструкция как подключиться 👇"
    )


def welcome_new_no_sub(name: str) -> str:
    """Приветствие нового пользователя — подписку создать не удалось."""
    return (
        f"👋 Привет, {name}!\n\n"
        f"⚠️ <b>Не удалось автоматически создать подписку.</b>\n\n"
        f"Напиши в поддержку — мы разберёмся и активируем её вручную.\n"
        f"Ниже — инструкция по подключению, она понадобится чуть позже 👇"
    )


def welcome_back(name: str) -> str:
    return f"С возвращением, {name}! 👋\n\nВсё по‑прежнему работает."


# ── Инструкция по подключению ─────────────────────────────────────────────────

def instruction_text() -> str:
    return (
        "<b>В боте нажми на \"<tg-emoji emoji-id=\"5877465816030515018\">🔗</tg-emoji> VPN-ссылка\" и скопируй, нажав на неё.</b>\n\n"
        "<b>Затем, в зависимости от устройства:</b>\n\n"

        "<tg-emoji emoji-id=\"5449665821850739918\">🍏</tg-emoji> "
        "<b>iPhone / iPad / Mac</b>\n"
        "• Скачай <b>Streisand</b> в App Store\n"
        "• В Streisand: <b>«+» → «Импорт из буфера»</b>\n\n"

        "<tg-emoji emoji-id=\"5398055016625876216\">🤖</tg-emoji> "
        "<b>Android</b>\n"
        "• Скачай <b>v2rayNG</b> в Google Play\n"
        "• В v2rayNG: <b>«☰» → «Добавить» → «Импорт подписки»</b>\n\n"

        "<tg-emoji emoji-id=\"5465513856035992056\">💻</tg-emoji> "
        "<b>Windows</b>\n"
        "• Скачай <b>Nekoray</b> с github.com/MatsuriDayo/nekoray\n"
        "• В Nekoray: <b>«Сервер» → «Добавить по URL»</b>\n\n"
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
        auto_icon = '<tg-emoji emoji-id="5411197345968701560">✅</tg-emoji>' if sub.get("auto_renew") else '<tg-emoji emoji-id="5416076321442777828">❌</tg-emoji>'
        lines.append(
            f'<tg-emoji emoji-id="5350404270032166927">🏠</tg-emoji> <b>Подписка</b>\n'
            f"├ <b>Осталось дней:</b> {days_left}\n"
            f"╰ <b>Автопродление:</b> {auto_icon}"
        )
    else:
        lines.append(
            '<tg-emoji emoji-id="5350404270032166927">🏠</tg-emoji> <b>Подписка</b>\n'
            "└ Не активна"
        )

    # Блок рефералов
    lines.append(
        f'\n<tg-emoji emoji-id="6001526766714227911">👥</tg-emoji> <b>Рефералы</b>\n'
        f"├ <b>Приглашено:</b> {ref_count}\n"
        f"├ <b>Бонус:</b> +{REFERRAL_BONUS_DAYS} дней за друга\n"
        f"╰ <code>{ref_link}</code>"
    )

    return "\n".join(lines)


# ── Настройки подписки ────────────────────────────────────────────────────────

def settings_text(sub: dict) -> str:
    expires = sub["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    days_left = max(0, (expires - datetime.utcnow()).days)
    auto = sub.get("auto_renew", False)
    auto_icon = "✅ Включено" if auto else "❌ Выключено"

    return (
        "📅  <b>Срок действия</b>\n"
        f"└ Осталось <b>{days_left} дн.</b>\n\n"

        "🔄  <b>Автопродление</b>\n"
        f"└ {auto_icon}\n"
        f"<i>{'Подписка продлится автоматически — вручную ничего делать не нужно.' if auto else 'Подписка не продлится автоматически. Включи автопродление или продли вручную.'}</i>\n\n"

        "💳  <b>Тариф</b>\n"
        f"└ {PLAN_NAME} — <b>{PLAN_PRICE} ₽</b> / {PLAN_DAYS} дней"
    )


# ── Ссылка подписки ───────────────────────────────────────────────────────────

def sub_url_text(url: str) -> str:
    return (
        "Нажми на ссылку — она скопируется в буфер обмена.\n"
        "Затем вставь её в своё VPN‑приложение.\n\n"
        f"<code>{url}</code>\n\n"
        "<i>Если VPN перестал работать — просто открой меню и обнови ссылку.</i>"
    )


# ── Покупка ───────────────────────────────────────────────────────────────────

def buy_text() -> str:
    return (
        "💳 <b>Оформление подписки</b>\n\n"

        f"📦  <b>{PLAN_NAME}</b>\n"
        f"├ Срок: <b>{PLAN_DAYS} дней</b>\n"
        f"├ Цена: <b>{PLAN_PRICE} ₽</b>\n"
        "╰ Оплата: <b>СБП</b> — быстро, без комиссии\n"
        "После оплаты нажми <b>«✅ Проверить оплату»</b> — "
        "подписка активируется мгновенно."
    )


def payment_success_text() -> str:
    return (
        "✅ <b>Оплата прошла!</b>\n\n"
        f"Подписка активна на <b>{PLAN_DAYS} дней</b>.\n\n"
        "Нажми <b>«🔗 Ссылка подписки»</b> в меню и вставь её в VPN‑приложение."
    )


def payment_fail_text() -> str:
    return (
        "❌ <b>Оплата не найдена.</b>\n\n"
        "Попробуй чуть позже или начни заново через меню."
    )


# ── Реферальная система ───────────────────────────────────────────────────────

def referral_reward_text(days: int) -> str:
    return (
        f"🎉 <b>Твой друг зарегистрировался!</b>\n\n"
        f"Тебе начислено <b>+{days} дней</b> подписки."
    )


# ── Ошибки ────────────────────────────────────────────────────────────────────

ERROR_TEXT = "Что‑то пошло не так. Попробуй ещё раз или напиши в поддержку."
