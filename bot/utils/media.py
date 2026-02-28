"""
utils/media.py — работа с фото-сообщениями в боте.

Все экраны бота отображаются как фото с caption, чтобы при переходах
между разделами меню можно было редактировать одно сообщение (без
нового сообщения с перемоткой чата).

Принцип кэша file_id:
  После первой загрузки Telegram сохраняет файл на своих серверах
  и возвращает file_id. Сохраняем его и переиспользуем — не загружаем
  файл повторно при каждом открытии экрана.

Структура медиа:
  bot/media/<page>.png  — фото для каждого экрана.
  Если файл страницы не найден — используется menu.png (fallback).
  Замени файлы на нужные изображения, код менять не придётся.
"""

import logging
from pathlib import Path

from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)

# ── Медиа-директория ──────────────────────────────────────────────────────────

MEDIA_DIR = Path(__file__).parent.parent / "media"
FALLBACK_PHOTO = MEDIA_DIR / "menu.png"

# Маппинг ключ страницы → файл изображения.
# Добавь новый экран — добавь строку здесь.
PAGE_PHOTOS: dict[str, Path] = {
    "menu":        MEDIA_DIR / "menu.png",
    "instruction": MEDIA_DIR / "instruction.png",
    "settings":    MEDIA_DIR / "settings.png",
    "sub_url":     MEDIA_DIR / "sub_url.png",
    "buy":         MEDIA_DIR / "buy.png",
    "support":     MEDIA_DIR / "support.png",
}


def _photo_path(page: str) -> Path:
    """Возвращает путь к фото страницы, fallback — menu.png."""
    path = PAGE_PHOTOS.get(page, FALLBACK_PHOTO)
    return path if path.exists() else FALLBACK_PHOTO


# ── Кэш file_id ───────────────────────────────────────────────────────────────

# path (str) → Telegram file_id
_cache: dict[str, str] = {}


def _cached(path: Path) -> str | None:
    return _cache.get(str(path))


def _save_cache(path: Path, file_id: str) -> None:
    _cache[str(path)] = file_id
    logger.debug("Cached file_id for %s", path.name)


def _input_file(path: Path) -> str | FSInputFile:
    """Возвращает закэшированный file_id или FSInputFile для первой загрузки."""
    return _cached(path) or FSInputFile(path)


# ── Публичные функции ─────────────────────────────────────────────────────────

async def send_photo_page(
    message: Message,
    page: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> Message:
    """
    Отправляет новое фото-сообщение.
    Используется при /start, /menu (когда нет предыдущего фото).
    """
    path = _photo_path(page)
    sent = await message.answer_photo(
        photo=_input_file(path),
        caption=caption,
        reply_markup=reply_markup,
    )
    if sent.photo and not _cached(path):
        _save_cache(path, sent.photo[-1].file_id)
    return sent


async def edit_photo_page(
    callback: CallbackQuery,
    page: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """
    Редактирует текущее сообщение, показывая нужный экран.

    Логика:
    • Текущее сообщение — фото с тем же изображением → меняем только caption.
    • Текущее сообщение — фото с другим изображением → edit_media (новое фото).
    • Текущее сообщение — текст → удаляем и отправляем новое фото.
    """
    msg = callback.message
    path = _photo_path(page)
    cached_id = _cached(path)

    if msg.photo:
        current_id = msg.photo[-1].file_id

        if cached_id and current_id == cached_id:
            # То же фото — обновляем только подпись (быстрее всего)
            await msg.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            # Другое фото — заменяем через edit_media
            media = InputMediaPhoto(
                media=_input_file(path),
                caption=caption,
            )
            sent = await msg.edit_media(media=media, reply_markup=reply_markup)
            if sent.photo and not cached_id:
                _save_cache(path, sent.photo[-1].file_id)
    else:
        # Текстовое сообщение — удаляем и шлём фото
        await msg.delete()
        sent = await msg.answer_photo(
            photo=_input_file(path),
            caption=caption,
            reply_markup=reply_markup,
        )
        if sent.photo and not cached_id:
            _save_cache(path, sent.photo[-1].file_id)
