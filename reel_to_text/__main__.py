"""Entrypoints.

  python -m reel_to_text bot            run the Telegram bot
  python -m reel_to_text transcribe URL one-off transcription in the terminal (no limits)
  python -m reel_to_text health         exit 0 if the bot heartbeat is fresh
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time

from dotenv import load_dotenv

from .config import Settings


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its URLs carry signed CDN tokens
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    ap = argparse.ArgumentParser(prog="reel_to_text")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bot")
    tr = sub.add_parser("transcribe")
    tr.add_argument("url")
    tr.add_argument("--json", action="store_true", help="print the full Transcript object")
    hc = sub.add_parser("health")
    hc.add_argument("--max-age", type=int, default=120)
    args = ap.parse_args()
    s = Settings.from_env()

    if args.cmd == "bot":
        from .interfaces.telegram.bot import run
        asyncio.run(run(s))
    elif args.cmd == "transcribe":
        from .core.errors import ReelToTextError
        from .core.factory import build_core
        core = build_core(s)
        try:
            t = asyncio.run(core.transcribe(args.url, requester="cli", unlimited=True))
        except ReelToTextError as e:
            print(f"error: {e.code}: {e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(t.to_dict(), ensure_ascii=False, indent=2) if args.json else t.text)
    elif args.cmd == "health":
        hb = s.data_dir / "heartbeat"
        try:
            age = time.time() - int(hb.read_text().strip())
        except (OSError, ValueError):
            print("no heartbeat")
            sys.exit(1)
        print(f"heartbeat age {age:.0f}s")
        sys.exit(0 if age <= args.max_age else 1)


if __name__ == "__main__":
    main()
