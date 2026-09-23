"""User-facing texts and result formatting for Telegram."""
from __future__ import annotations

from ...core.errors import (AccessDenied, GlobalLimitReached, InvalidUrl, NotAVideo, ProviderUnavailable,
                            RateLimited, ReelNotFound, ReelToTextError, ReelTooLong,
                            TranscriptionFailed)
from ...core.models import Transcript

TG_LIMIT = 4096
CHUNK = 3900          # room for a part marker
MAX_MESSAGES = 4      # longer than this goes as a .txt file

START = (
    "Пришли ссылку на Instagram Reel, верну текст речи из ролика.\n\n"
    "Пример: https://www.instagram.com/reel/XXXXXXXXXXX/\n\n"
    "Можно просто переслать текст из «Поделиться», ссылку найду сам."
)
WORKING = "⏳ Расшифровываю…"
NO_ACCESS = (
    "Бот пока в закрытой бете. Твой Telegram ID: {user_id}\n"
    "Отправь его владельцу бота, чтобы добавили."
)
NO_SPEECH = "В ролике не нашлось речи. Похоже, там только музыка или звуки."


def _mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def minutes(seconds: int) -> str:
    m = max(1, round(seconds / 60))
    return f"{m} мин"


def error_text(e: ReelToTextError) -> str:
    if isinstance(e, InvalidUrl):
        return "Не вижу ссылки на Instagram Reel. Нужна ссылка вида instagram.com/reel/…"
    if isinstance(e, ReelNotFound):
        return "Ролик не открывается: он приватный, удалён или ссылка неверная."
    if isinstance(e, NotAVideo):
        return "По ссылке нет видео. Это фото или карусель без роликов."
    if isinstance(e, ReelTooLong):
        return f"Ролик длиннее лимита: {_mmss(e.duration)}, а можно до {_mmss(e.limit)}."
    if isinstance(e, RateLimited):
        return f"Лимит расшифровок исчерпан. Попробуй через {minutes(e.retry_after)}."
    if isinstance(e, GlobalLimitReached):
        return "Бот на сегодня исчерпал общий лимит расшифровок. Попробуй завтра."
    if isinstance(e, AccessDenied):
        return "Нет доступа."
    if isinstance(e, ProviderUnavailable):
        return "Instagram сейчас не отдаёт ролик. Попробуй чуть позже."
    if isinstance(e, TranscriptionFailed):
        return "Не получилось распознать речь. Попробуй ещё раз чуть позже."
    return "Что-то сломалось. Попробуй ещё раз."


def footer(t: Transcript) -> str:
    parts = []
    if t.author:
        parts.append(f"@{t.author}")
    if t.duration:
        parts.append(_mmss(t.duration))
    return "— " + " · ".join(parts) if parts else ""


def split_text(text: str, limit: int = CHUNK) -> list[str]:
    """Split on paragraph, then sentence, then word boundaries; never exceed `limit`."""
    chunks: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        cut = max(window.rfind("\n\n"), -1)
        if cut < limit // 2:
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            cut = cut + 1 if cut >= limit // 2 else -1
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def render(t: Transcript) -> list[str]:
    """Messages to send. Empty list = too long, send as a file."""
    if not t.text.strip():
        return [NO_SPEECH + ("\n\n" + footer(t) if footer(t) else "")]
    body = t.text.strip()
    tail = footer(t)
    full = f"{body}\n\n{tail}" if tail else body
    if len(full) <= TG_LIMIT:
        return [full]
    chunks = split_text(body)
    if len(chunks) > MAX_MESSAGES:
        return []
    if tail:
        chunks[-1] = f"{chunks[-1]}\n\n{tail}"
    n = len(chunks)
    return [f"{c}\n\n[{i}/{n}]" for i, c in enumerate(chunks, 1)]


def txt_file(t: Transcript) -> str:
    head = [f"Источник: {t.source_url}"]
    if t.author:
        head.append(f"Автор: @{t.author}")
    if t.duration:
        head.append(f"Длительность: {_mmss(t.duration)}")
    return "\n".join(head) + "\n\n" + t.text.strip() + "\n"


def stats_text(st: dict, days: int) -> str:
    lines = [
        f"За {days} дн.: запросов {st['requests']}, людей {st['users']}",
        f"Успешно {st['success']}, из кэша {st['cache_hits']}, платных {st['paid']}",
    ]
    if st["avg_paid_ms"]:
        lines.append(f"Среднее время платной расшифровки: {st['avg_paid_ms'] / 1000:.1f} с")
    if st["errors"]:
        lines.append("Ошибки: " + ", ".join(f"{k} {v}" for k, v in st["errors"].items()))
    lines.append(f"Роликов в кэше всего: {st['cached_transcripts']}")
    return "\n".join(lines)
