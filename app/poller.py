
from datetime import datetime, time, timedelta
import asyncio
import zoneinfo
import contextlib

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties

from .config import get_settings, HELP_TEXT
from .parser import fetch_matches_for_local_day
from .formatting import format_digest


router = Router()

@router.message(CommandStart())
async def on_start(message: types.Message) -> None:
    await message.answer(HELP_TEXT, disable_web_page_preview=True)


@router.message(Command("today"))
async def on_today(message: types.Message) -> None:
    settings = get_settings()
    now_local = datetime.now(zoneinfo.ZoneInfo(settings.timezone))
    matches = fetch_matches_for_local_day(
        api_url=settings.api_url,
        element_alias=settings.element_alias,
        element_type=settings.element_type,
        max_results=settings.max_results,
        user_agent=settings.user_agent,
        target_date_local=now_local,
        timezone_name=settings.timezone,
    )
    text = format_digest(matches, settings.timezone, now_local)
    await message.answer(text, disable_web_page_preview=True)

@router.message(Command("tomorrow"))
async def on_tomorrow(message: types.Message) -> None:
    settings = get_settings()
    now_local = datetime.now(zoneinfo.ZoneInfo(settings.timezone))
    matches = fetch_matches_for_local_day(
        api_url=settings.api_url,
        element_alias=settings.element_alias,
        element_type=settings.element_type,
        max_results=settings.max_results,
        user_agent=settings.user_agent,
        target_date_local=now_local + timedelta(days=1),
        timezone_name=settings.timezone,
    )
    text = format_digest(matches, settings.timezone, now_local + timedelta(days=1))
    await message.answer(text, disable_web_page_preview=True)

async def _seconds_until_next(time_of_day: time, tz_name: str) -> float:
    tz = zoneinfo.ZoneInfo(tz_name)
    now = datetime.now(tz)
    today_at = datetime.combine(now.date(), time_of_day).replace(tzinfo=tz)
    if now >= today_at:
        next_run = today_at + timedelta(days=1)
    else:
        next_run = today_at
    return (next_run - now).total_seconds()


async def daily_digest_scheduler(bot: Bot) -> None:
    settings = get_settings()
    # Парсим HH:MM из настроек
    try:
        hh, mm = [int(x) for x in settings.digest_time.split(":", 1)]
        target_tod = time(hour=hh, minute=mm)
    except Exception:
        # Фоллбек: 09:00 по TZ
        target_tod = time(hour=9, minute=0)

    while True:
        try:
            # Ждём до следующего времени запуска в локальном TZ
            sleep_s = await _seconds_until_next(target_tod, settings.timezone)
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)

            # Сбор дайджеста на сегодня в локальном TZ
            now_local = datetime.now(zoneinfo.ZoneInfo(settings.timezone))
            matches = fetch_matches_for_local_day(
                api_url=settings.api_url,
                element_alias=settings.element_alias,
                element_type=settings.element_type,
                max_results=settings.max_results,
                user_agent=settings.user_agent,
                target_date_local=now_local,
                timezone_name=settings.timezone,
            )
            text = format_digest(matches, settings.timezone, now_local)

            # Отправляем в указанный чат/канал
            await bot.send_message(settings.chat_id, text, disable_web_page_preview=True)

            # Гарантируем, что следующий запуск — завтра
            tomorrow_same_time = datetime.now(zoneinfo.ZoneInfo(settings.timezone)).replace(
                hour=target_tod.hour, minute=target_tod.minute, second=0, microsecond=0
            ) + timedelta(days=1)
            await asyncio.sleep(max(0.0, (tomorrow_same_time - datetime.now(zoneinfo.ZoneInfo(settings.timezone))).total_seconds()))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Не валим цикл: ждём минуту и пробуем снова
            await asyncio.sleep(60)


async def run_async() -> None:
    settings = get_settings()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    # Запускаем фоновый планировщик ежедневного дайджеста
    digest_task = asyncio.create_task(daily_digest_scheduler(bot))
    try:
        await dp.start_polling(bot)
    finally:
        digest_task.cancel()
        with contextlib.suppress(Exception):
            await digest_task


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
