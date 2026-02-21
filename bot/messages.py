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
        "📱 <b>Как подключить VPN</b>\n\n"

        "🍎 <b>iPhone / iPad</b> — приложение <b>Streisand</b>\n"
        "1. Скачай <b>Streisand</b> в App Store\n"
        "2. Нажми <b>«🔗 Ссылка подписки»</b> → скопируй\n"
        "3. В Streisand: <b>«+»</b> → <b>«Импорт из буфера»</b>\n\n"

        "🤖 <b>Android</b> — приложение <b>v2rayNG</b>\n"
        "1. Скачай <b>v2rayNG</b> в Google Play\n"
        "2. Нажми <b>«🔗 Ссылка подписки»</b> → скопируй\n"
        "3. В v2rayNG: <b>«☰»</b> → <b>«Добавить»</b> → <b>«Импорт подписки»</b>\n\n"

        "💻 <b>Windows</b> — приложение <b>Nekoray</b>\n"
        "1. Скачай <b>Nekoray</b> с github.com/MatsuriDayo/nekoray\n"
        "2. Нажми <b>«🔗 Ссылка подписки»</b> → скопируй\n"
        "3. В Nekoray: <b>«Сервер»</b> → <b>«Добавить по URL»</b>\n\n"

        "🍏 <b>Mac</b> — приложение <b>FoXray</b>\n"
        "1. Скачай <b>FoXray</b> в Mac App Store\n"
        "2. Нажми <b>«🔗 Ссылка подписки»</b> → скопируй\n"
        "3. В FoXray: <b>«+»</b> → <b>«Из буфера обмена»</b>\n\n"

        "💡 <i>Ссылка обновляется автоматически — переустанавливать ничего не нужно.</i>"
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
        auto_icon = '<tg-emoji emoji-id="5429501538806548545">✅</tg-emoji>' if sub.get("auto_renew") else '<tg-emoji emoji-id="5416076321442777828">❌</tg-emoji>'
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
        f'\n<tg-emoji emoji-id="5258513401784573443">👥</tg-emoji> <b>Рефералы</b>\n'
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
        "⚙️ <b>Настройки подписки</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📅  <b>Срок действия</b>\n"
        f"└ Осталось <b>{days_left} дн.</b>\n\n"

        "🔄  <b>Автопродление</b>\n"
        f"└ {auto_icon}\n"
        f"<i>{'Подписка продлится автоматически — вручную ничего делать не нужно.' if auto else 'Подписка не продлится автоматически. Включи автопродление или продли вручную.'}</i>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳  <b>Тариф</b>\n"
        f"└ {PLAN_NAME} — <b>{PLAN_PRICE} ₽</b> / {PLAN_DAYS} дней"
    )


# ── Ссылка подписки ───────────────────────────────────────────────────────────

def sub_url_text(url: str) -> str:
    return (
        "🔗 <b>Ссылка подписки</b>\n\n"
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
