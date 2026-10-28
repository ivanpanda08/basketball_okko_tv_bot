from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiohttp import ClientConnectorError, ConnectionTimeoutError

from .config import get_settings
from .euroleague import fetch_league_digest, format_league_digest


logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


def next_weekly_run(now: datetime) -> datetime:
    now = now.astimezone(MOSCOW)
    target = datetime.combine(now.date(), time(9), tzinfo=MOSCOW)
    target += timedelta(days=(0 - now.weekday()) % 7)
    if target <= now:
        target += timedelta(days=7)
    return target


async def publish_weekly_digest(bot: Bot, chat_id: str, now: datetime) -> None:
    # Separate progress per league: retry a failure without repeating messages
    # that Telegram has already accepted for the other league.
    for competition in ("U", "E"):
        pending: list[str] | None = None
        sent = 0
        for attempt in range(3):
            try:
                if pending is None:
                    digest = await asyncio.to_thread(
                        fetch_league_digest, competition, now, "Europe/Moscow", True,
                    )
                    # Do not publish an incomplete weekly table to the channel.
                    if digest.standings_unavailable:
                        raise RuntimeError("Weekly standings unavailable")
                    pending = format_league_digest(digest)
                while sent < len(pending):
                    await bot.send_message(chat_id, pending[sent], disable_web_page_preview=True)
                    sent += 1
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Weekly digest failed: competition=%s attempt=%s", competition, attempt + 1)
                # Telegram may have accepted a message before a read timeout.
                # Retrying that send can publish the same message twice.
                if isinstance(exc, TelegramNetworkError) and not isinstance(
                    exc.__context__, (ClientConnectorError, ConnectionTimeoutError)
                ):
                    break
                if attempt < 2:
                    delay = max(60, exc.retry_after) if isinstance(exc, TelegramRetryAfter) else 60
                    await asyncio.sleep(delay)


async def weekly_digest_scheduler(bot: Bot) -> None:
    settings = get_settings()
    while True:
        now = datetime.now(MOSCOW)
        target = next_weekly_run(now)
        logger.info("Next weekly basketball digest: %s", target.isoformat())
        await asyncio.sleep((target - now).total_seconds())
        # Keep the planned date if a network retry crosses midnight.
        await publish_weekly_digest(bot, settings.chat_id, target)
