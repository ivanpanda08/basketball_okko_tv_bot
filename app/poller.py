
from datetime import datetime, time, timedelta
import asyncio
import zoneinfo
import contextlib
import logging
import sys
import traceback

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError

from .config import DIGEST_TIME, get_settings, HELP_TEXT
from .parser import ScheduleUnavailable, fetch_matches_for_local_day
from .formatting import format_digest
from .telegram_session import TelegramSession
from .euroleague import BUTTONS, VIEW_BUTTONS, DataUnavailable, fetch_league_digest, format_league_digest
from .league_jobs import weekly_digest_scheduler


router = Router()

def main_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text=VIEW_BUTTONS[(code, "results")]),
            types.KeyboardButton(text=VIEW_BUTTONS[(code, "table")]),
        ] for code in ("E", "U")],
        resize_keyboard=True,
        is_persistent=True,
    )

@router.message(CommandStart())
@router.message(Command("menu"))
async def on_start(message: types.Message) -> None:
    await message.answer(HELP_TEXT, disable_web_page_preview=True, reply_markup=main_keyboard())


@router.message(Command("euroleague"))
@router.message(Command("euroleague_table"))
@router.message(F.text == BUTTONS["E"])
@router.message(F.text == VIEW_BUTTONS[("E", "table")])
async def on_euroleague(message: types.Message) -> None:
    await answer_league_digest(message, "E", "table")


@router.message(Command("eurocup"))
@router.message(Command("eurocup_table"))
@router.message(F.text == BUTTONS["U"])
@router.message(F.text == VIEW_BUTTONS[("U", "table")])
async def on_eurocup(message: types.Message) -> None:
    await answer_league_digest(message, "U", "table")


@router.message(Command("euroleague_results"))
@router.message(F.text == VIEW_BUTTONS[("E", "results")])
async def on_euroleague_results(message: types.Message) -> None:
    await answer_league_digest(message, "E", "results")


@router.message(Command("eurocup_results"))
@router.message(F.text == VIEW_BUTTONS[("U", "results")])
async def on_eurocup_results(message: types.Message) -> None:
    await answer_league_digest(message, "U", "results")


async def answer_league_digest(message: types.Message, competition: str, view: str = "table") -> None:
    loading = "Загружаю свежие результаты…" if view == "results" else "Загружаю актуальную таблицу…"
    await message.answer(loading, reply_markup=main_keyboard())
    try:
        digest = await asyncio.to_thread(
            fetch_league_digest, competition,
            datetime.now(zoneinfo.ZoneInfo("Europe/Moscow")),
            include_standings=view != "results",
        )
    except DataUnavailable:
        logging.getLogger(__name__).exception("Could not load league %s", competition)
        await message.answer("Не удалось получить данные турнира. Источник временно недоступен. Попробуйте позже.")
        return
    for text in format_league_digest(digest, view=view):
        await message.answer(text, disable_web_page_preview=True, reply_markup=main_keyboard())


@router.message(Command("today"))
async def on_today(message: types.Message) -> None:
    await answer_digest(message, days_ahead=0)

@router.message(Command("tomorrow"))
async def on_tomorrow(message: types.Message) -> None:
    await answer_digest(message, days_ahead=1)


async def answer_digest(message: types.Message, days_ahead: int) -> None:
    settings = get_settings()
    target = datetime.now(zoneinfo.ZoneInfo(settings.timezone)) + timedelta(days=days_ahead)
    try:
        matches = await asyncio.to_thread(
            fetch_matches_for_local_day,
            api_url=settings.api_url,
            element_alias=settings.element_alias,
            element_type=settings.element_type,
            max_results=settings.max_results,
            user_agent=settings.user_agent,
            target_date_local=target,
            timezone_name=settings.timezone,
        )
    except ScheduleUnavailable:
        logging.getLogger(__name__).exception("Could not load Okko schedule")
        await message.answer(
            "Не удалось получить расписание Okko. Источник временно недоступен. "
            "Попробуйте позже.",
        )
        return
    text = format_digest(matches, settings.timezone, target)
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
    # Парсим HH:MM/HH.MM/HH-MM из настроек
    raw_time = (settings.digest_time or "").strip()
    target_tod: time
    parsed = False
    for sep in (":", ".", "-"):
        if sep in raw_time:
            try:
                hh_str, mm_str = raw_time.split(sep, 1)
                hh, mm = int(hh_str), int(mm_str)
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    target_tod = time(hour=hh, minute=mm)
                    parsed = True
                    break
            except Exception:
                pass
    if not parsed:
        # При некорректной настройке используем стандартное время дайджеста.
        target_tod = time.fromisoformat(DIGEST_TIME)

    while True:
        try:
            # Ждём до следующего времени запуска в локальном TZ
            sleep_s = await _seconds_until_next(target_tod, settings.timezone)
            print(f"[digest] settings_tz={settings.timezone}, settings_digest_time={settings.digest_time}, target_tod={target_tod}, sleep_s={sleep_s}")
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)

            # Получаем актуальное время ПОСЛЕ сна
            now_local = datetime.now(zoneinfo.ZoneInfo(settings.timezone))
            print(f"[digest] woke up at {now_local}")

            matches = await asyncio.to_thread(
                fetch_matches_for_local_day,
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
            print(f"[digest] sent on {now_local.strftime('%H:%M')} local time")

        except asyncio.CancelledError:
            # Завершаем шедулер по отмене без проброса
            return
        except Exception as e:
            # Не валим цикл: логируем и ждём минуту
            print(f"[digest][error] {e}")
            traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(60)


async def run_async() -> None:
    settings = get_settings()
    session = TelegramSession(timeout=settings.bot_http_timeout)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()
    dp.include_router(router)
    # Запускаем фоновый планировщик ежедневного дайджеста
    digest_task = asyncio.create_task(daily_digest_scheduler(bot))
    weekly_task = asyncio.create_task(weekly_digest_scheduler(bot))
    retry_count = 0
    try:
        while True:
            try:
                await dp.start_polling(bot, polling_timeout=settings.polling_timeout)
                break
            except asyncio.CancelledError:
                raise
            except (TelegramNetworkError, asyncio.TimeoutError) as exc:
                retry_count += 1
                delay = min(60, 2 ** min(retry_count, 5))
                print(
                    f"[polling][network_error] {exc}. "
                    f"Retry in {delay}s (attempt={retry_count})"
                )
                await asyncio.sleep(delay)
    finally:
        for task in (digest_task, weekly_task):
            task.cancel()
        for task in (digest_task, weekly_task):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
