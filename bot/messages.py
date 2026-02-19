"""
bot/messages.py — все тексты бота в одном месте.

Правило: хэндлеры не содержат строк, только вызовы этого модуля.
"""

from datetime import datetime
from bot.config import PLAN_PRICE, PLAN_DAYS, PLAN_NAME, GIFT_DAYS, REFERRAL_BONUS_DAYS


# ── Приветствие ───────────────────────────────────────────────────────────────

def welcome_new(name: str) -> str:
    return (
        f"Привет, {name}! 👋\n\n"
        f"Добро пожаловать — ты подключился к <b>VPN-сервису</b>.\n\n"
        f"🎁 <b>Тебе начислено {GIFT_DAYS} дней бесплатно</b> — просто за то, что ты здесь.\n\n"
        f"Ниже — короткая инструкция, как активировать VPN на своём устройстве."
    )


def welcome_back(name: str) -> str:
    return f'С возвращением, {name}! <tg-emoji emoji-id="5472055112702629499">👋</tg-emoji>\n\nВсё по-прежнему работает. Чем могу помочь?'


# ── Инструкция по подключению ─────────────────────────────────────────────────

INSTRUCTION_TEXT = (
    "📱 <b>Как подключить VPN</b>\n\n"

    "<b>iPhone / iPad</b>\n"
    "1. Установи приложение <b>Streisand</b> из App Store\n"
    "2. Открой бота → /menu → скопируй ссылку подписки\n"
    "3. В Streisand нажми «+» → «Импорт из буфера» → Готово\n\n"

    "<b>Android</b>\n"
    "1. Установи <b>v2rayNG</b> из Google Play (или APK с сайта)\n"
    "2. Открой бота → /menu → скопируй ссылку подписки\n"
    "3. В v2rayNG нажми «☰» → «Добавить» → «Импорт подписки» → вставь ссылку\n\n"

    "<b>Windows</b>\n"
    "1. Скачай <b>Nekoray</b> с github.com/MatsuriDayo/nekoray\n"
    "2. Открой бота → /menu → скопируй ссылку подписки\n"
    "3. В программе: Сервер → «Добавить по URL» → вставь ссылку\n\n"

    "<b>Mac</b>\n"
    "1. Установи <b>FoXray</b> из Mac App Store\n"
    "2. Открой бота → /menu → скопируй ссылку подписки\n"
    "3. В FoXray нажми «+» → «Из буфера обмена»\n\n"

    "💡 <i>Ссылка подписки обновляется автоматически — переустанавливать приложение не нужно.</i>\n\n"
    "Всё готово? Открой /menu"
)


# ── Главное меню ──────────────────────────────────────────────────────────────

def menu_text(
    name: str,
    sub: dict | None,
    ref_link: str,
    ref_count: int,
    bonus_days: int,
) -> str:
    lines = [f"<b>Меню</b> · {name}\n"]

    # Подписка
    if sub:
        expires = sub["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        days_left = max(0, (expires - datetime.utcnow()).days)
        auto = "вкл" if sub.get("auto_renew") else "выкл"
        lines.append(
            f"📶 <b>Подписка активна</b>\n"
            f"   Осталось: <b>{days_left} дн.</b>  ·  Авто: {auto}"
        )
    else:
        lines.append("📵 <b>Подписка не активна</b>")

    if bonus_days:
        lines.append(f"\n🎁 Бонус при покупке: +{bonus_days} дн.")

    # Реферальная программа
    lines.append(
        f"\n👥 <b>Рефералы</b>\n"
        f"   Приглашено: {ref_count} чел.  ·  Бонус: +{REFERRAL_BONUS_DAYS} дн. за друга\n"
        f"   <code>{ref_link}</code>"
    )

    return "\n".join(lines)


# ── Настройки подписки ────────────────────────────────────────────────────────

def settings_text(sub: dict) -> str:
    expires = sub["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    days_left = max(0, (expires - datetime.utcnow()).days)
    auto = sub.get("auto_renew", True)

    return (
        f"⚙️ <b>Настройки подписки</b>\n\n"
        f"Активна ещё <b>{days_left} дн.</b>\n\n"
        f"<b>Автопродление</b> {'🟢 включено' if auto else '🔴 выключено'}\n"
        f"<i>Каждые {PLAN_DAYS} дней списывается {PLAN_PRICE} ₽ — "
        f"вручную ничего делать не нужно.</i>\n\n"
        f"<b>Ручное продление</b>\n"
        f"<i>Продли подписку прямо сейчас — срок прибавится к текущему.</i>"
    )


# ── Покупка ───────────────────────────────────────────────────────────────────

def buy_text(bonus_days: int = 0) -> str:
    total = PLAN_DAYS + bonus_days
    bonus_note = f"\n🎁 +{bonus_days} бонусных дней будут добавлены" if bonus_days else ""
    return (
        f"💳 <b>Оформление подписки</b>\n\n"
        f"Тариф: <b>{PLAN_NAME}</b>\n"
        f"Срок: <b>{total} дней</b>"
        f"{bonus_note}\n"
        f"Цена: <b>{PLAN_PRICE} ₽</b>\n\n"
        f"Оплата через СБП — быстро и без комиссии."
    )


def payment_pending_text() -> str:
    return "⏳ Ожидаем подтверждение оплаты...\n\nОбычно это занимает несколько секунд."


def payment_success_text(days: int) -> str:
    return f"✅ <b>Оплата прошла!</b>\n\nПодписка активна на <b>{days} дней</b>.\nОткрой /menu и скопируй ссылку подписки."


def payment_fail_text() -> str:
    return "❌ Оплата не найдена. Попробуй чуть позже или начни заново через /menu."


# ── Реферальная система ───────────────────────────────────────────────────────

def referral_reward_text(days: int) -> str:
    return f"🎉 Твой друг зарегистрировался! Тебе начислено <b>+{days} дней</b> к подписке."


# ── Ошибки ───────────────────────────────────────────────────────────────────

ERROR_TEXT = "Что-то пошло не так. Попробуй ещё раз или напиши в поддержку."
