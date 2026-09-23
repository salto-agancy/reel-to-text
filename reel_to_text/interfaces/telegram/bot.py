"""Telegram interface: a thin layer over the core. Long polling, no webhook, no domain."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message

from ...config import Settings
from ...core.errors import ReelToTextError
from ...core.factory import build_core
from ...core.service import ReelToText
from ...core.urls import find_url
from . import texts

log = logging.getLogger("reel_to_text.telegram")

HEARTBEAT_EVERY = 30


class Access:
    def __init__(self, s: Settings):
        self.mode = s.access_mode
        self.allowed = s.allowed_user_ids | s.admin_user_ids
        self.admins = s.admin_user_ids

    def allowed_user(self, user_id: int) -> bool:
        return self.mode == "open" or user_id in self.allowed

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admins


def build_dispatcher(core: ReelToText, access: Access) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    @dp.message(Command("help"))
    async def start(m: Message) -> None:
        await m.answer(texts.START, disable_web_page_preview=True)

    @dp.message(Command("id"))
    async def my_id(m: Message) -> None:
        await m.answer(f"Твой Telegram ID: {m.from_user.id}")

    @dp.message(Command("stats"))
    async def stats(m: Message) -> None:
        if not access.is_admin(m.from_user.id):
            return
        parts = (m.text or "").split()
        days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        await m.answer(texts.stats_text(core.store.stats(time.time() - days * 86400), days))

    @dp.message(F.text | F.caption)
    async def on_text(m: Message) -> None:
        user_id = m.from_user.id
        text = m.text or m.caption or ""
        url = find_url(text)
        if not access.allowed_user(user_id):
            log.info("denied user=%s", user_id)
            await m.answer(texts.NO_ACCESS.format(user_id=user_id))
            return
        if not url:
            try:
                await core.transcribe(text, requester=f"tg:{user_id}")  # raises InvalidUrl, logs the event
            except ReelToTextError as e:
                await m.answer(texts.error_text(e), disable_web_page_preview=True)
            return

        status = await m.answer(texts.WORKING)
        started = time.monotonic()
        try:
            t = await core.transcribe(url, requester=f"tg:{user_id}", unlimited=access.is_admin(user_id))
        except ReelToTextError as e:
            log.info("fail user=%s url=%s code=%s err=%s", user_id, url, e.code, e)
            await status.edit_text(texts.error_text(e))
            return
        except Exception:
            log.exception("crash user=%s url=%s", user_id, url)
            await status.edit_text(texts.error_text(ReelToTextError()))
            return

        log.info("ok user=%s shortcode=%s cached=%s secs=%.1f chars=%d",
                 user_id, t.shortcode, t.cached, time.monotonic() - started, len(t.text))
        messages = texts.render(t)
        if not messages:
            await status.delete()
            await m.answer_document(
                BufferedInputFile(texts.txt_file(t).encode("utf-8"), filename=f"reel_{t.shortcode}.txt"),
                caption=f"Текст длинный, отправляю файлом.\n{texts.footer(t)}",
            )
            return
        await status.edit_text(messages[0], disable_web_page_preview=True)
        for extra in messages[1:]:
            await m.answer(extra, disable_web_page_preview=True)

    return dp


async def heartbeat(path: Path) -> None:
    """The polling loop is alive while this file keeps getting fresh. deploy/healthcheck.sh reads it."""
    while True:
        path.write_text(str(int(time.time())))
        await asyncio.sleep(HEARTBEAT_EVERY)


async def run(s: Settings) -> None:
    if not s.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    core = build_core(s)
    access = Access(s)
    if access.mode != "open" and not access.allowed:
        log.warning("ACCESS_MODE=allowlist but ALLOWED_USER_IDS/ADMIN_USER_IDS are empty: nobody can use the bot")
    bot = Bot(s.telegram_bot_token)
    dp = build_dispatcher(core, access)
    me = await bot.get_me()
    log.info("started bot=@%s providers=%s access=%s", me.username,
             [p.name for p in core.instagram], access.mode)
    hb = asyncio.create_task(heartbeat(s.data_dir / "heartbeat"))
    try:
        await dp.start_polling(bot, handle_signals=True)
    finally:
        hb.cancel()
        await bot.session.close()
