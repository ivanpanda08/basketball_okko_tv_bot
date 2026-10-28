import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from app.euroleague import (
    BUTTONS, DataUnavailable, LeagueDigest, Game, Standing,
    _all_pages, fetch_league_digest, format_league_digest,
)
from app.league_jobs import next_weekly_run, publish_weekly_digest


TZ = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 10, 28, 9, tzinfo=TZ)


def game(code=1, date="2026-10-27T20:00:00Z", played=True, round=5):
    return dict(gameCode=code, round=round, played=played, utcDate=date,
                phaseType={"code": "RS"},
                local={"club": {"code": "A", "name": "A & B"}, "score": 90},
                road={"club": {"code": "B", "name": "Away"}, "score": 85})


def teams(played=1):
    return [dict(position=1, club={"code": c, "name": name}, gamesPlayed=played,
                 gamesWon=played if c == "A" else 0, gamesLost=0 if c == "A" else played,
                 groupName=group)
            for c, name, group in [("A", "A & B", "A"), ("B", "Away", "B")]]


def digest(competition="E"):
    return LeagueDigest(competition, "2026-27", NOW, NOW - timedelta(days=7), NOW,
                        [Game.model_validate(game())],
                        [Standing.model_validate(t) for t in teams()], 5)


class LeagueTests(unittest.TestCase):
    def fetch(self, games, table=None, now=NOW, weekly=False):
        seasons = [{"code": "E2027", "year": 2027, "startDate": "2027-07-01"},
                   {"code": "E2026", "alias": "2026-27", "year": 2026, "startDate": "2026-07-01"}]
        with patch("app.euroleague._all_pages", side_effect=[seasons, games]), \
             patch("app.euroleague._get", return_value={"teams": teams() if table is None else table}) as request:
            result = fetch_league_digest("E", now, weekly=weekly)
        return result, request

    def test_current_season_and_latest_played_round_not_future_round(self):
        result, request = self.fetch([game(), game(2, "2027-01-01T18:00:00Z", False, 20)])
        self.assertEqual(result.season, "2026-27")
        self.assertEqual(result.standings_round, 5)
        self.assertIn("E2026/rounds/5/basicstandings", request.call_args.args[1])
        self.assertFalse(result.standings_unavailable)

    def test_weekly_results_use_moscow_midnights_and_exclude_monday(self):
        monday = datetime(2026, 11, 2, 9, tzinfo=TZ)
        games = [game(1, "2026-10-25T20:59:00Z"),  # Sunday before the window
                 game(2, "2026-10-25T21:00:00Z"),  # Monday 00:00 Moscow
                 game(3, "2026-11-01T20:59:00Z"),  # Sunday in the window
                 game(4, "2026-11-01T21:00:00Z"),  # This Monday, excluded
                 game(5, "2026-10-30T18:00:00Z", False)]
        result, _ = self.fetch(games, teams(4), monday, True)
        self.assertEqual([g.gameCode for g in result.results], [2, 3])
        self.assertEqual(result.period_start, datetime(2026, 10, 26, tzinfo=TZ))

    def test_current_results_include_today_and_exclude_old_games(self):
        games = [game(1, "2026-10-21T20:59:00Z"),
                 game(2, "2026-10-21T21:00:00Z"),
                 game(3, "2026-10-28T05:00:00Z")]
        result, _ = self.fetch(games, teams(3))
        self.assertEqual([g.gameCode for g in result.results], [2, 3])

    def test_stale_or_empty_table_does_not_hide_results(self):
        for table in [[], teams(0)]:
            with self.subTest(table=table), self.assertLogs("app.euroleague", "ERROR"):
                result, _ = self.fetch([game()], table)
            self.assertTrue(result.standings_unavailable)
            texts = format_league_digest(result)
            self.assertIn("90:85", texts[0])
            self.assertIn("ещё обновляется", texts[-1])

    def test_bad_data_is_an_error_not_no_matches(self):
        with self.assertRaises(DataUnavailable):
            self.fetch([{"bad": "payload"}])

    def test_preseason_and_empty_result_period_are_explicit(self):
        result, request = self.fetch([])
        request.assert_not_called()
        texts = format_league_digest(result)
        self.assertIn("завершённых матчей нет", texts[0])
        self.assertIn("пока не сыграно", texts[1])

    def test_pagination_reads_all_pages_and_rejects_incomplete_response(self):
        with patch("app.euroleague._get", side_effect=[
            {"data": [1], "total": 2}, {"data": [2], "total": 2},
        ]) as request:
            self.assertEqual(_all_pages(None, "/games"), [1, 2])
            self.assertEqual(request.call_args.kwargs["offset"], 1)
        with patch("app.euroleague._get", return_value={"data": [], "total": 1}):
            with self.assertRaises(ValueError):
                _all_pages(None, "/games")

    def test_format_groups_escape_html_and_split_large_messages(self):
        data = digest("U")
        data.results *= 300
        texts = format_league_digest(data)
        self.assertTrue(all(len(t) < 4096 for t in texts))
        self.assertIn("A &amp; B", texts[0])
        self.assertIn("Группа A", texts[-1])
        self.assertIn("Группа B", texts[-1])
        self.assertTrue(all(t.count("<b>") == t.count("</b>") for t in texts))

    def test_next_monday_at_nine_moscow(self):
        for now, expected in [
            ("2026-10-28T09:00:00+03:00", "2026-11-02T09:00:00+03:00"),
            ("2026-11-02T08:59:00+03:00", "2026-11-02T09:00:00+03:00"),
            ("2026-11-02T09:00:00+03:00", "2026-11-09T09:00:00+03:00"),
            ("2026-11-01T23:00:00+00:00", "2026-11-02T09:00:00+03:00"),
        ]:
            self.assertEqual(next_weekly_run(datetime.fromisoformat(now)).isoformat(), expected)


class LeagueBotTests(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_send_timeout_does_not_duplicate_channel_message(self):
        from aiogram.exceptions import TelegramNetworkError
        from aiogram.methods import SendMessage
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=[
            TelegramNetworkError(method=SendMessage(chat_id="channel", text="test"), message="Read timeout"),
            None, None,
        ])
        with patch("app.league_jobs.fetch_league_digest", side_effect=lambda c, *a: digest(c)), \
             self.assertLogs("app.league_jobs", "ERROR"):
            await publish_weekly_digest(bot, "channel", NOW)
        texts = [c.args[1] for c in bot.send_message.call_args_list]
        self.assertEqual(len(texts), 3)
        self.assertIn("Еврокубок", texts[0])
        self.assertTrue(all("Евролига" in text for text in texts[1:]))

    async def test_weekly_sends_each_league_separately_and_retries_only_unsent_message(self):
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=[None, RuntimeError("temporary"), None, None, None])
        with patch("app.league_jobs.fetch_league_digest", side_effect=lambda c, *a: digest(c)), \
             patch("app.league_jobs.asyncio.sleep", new_callable=AsyncMock), \
             self.assertLogs("app.league_jobs", "ERROR"):
            await publish_weekly_digest(bot, "channel", NOW)
        texts = [c.args[1] for c in bot.send_message.call_args_list]
        self.assertEqual(len(texts), 5)
        self.assertIn("Еврокубок", texts[0])
        self.assertEqual(texts[1], texts[2])
        self.assertIn("Евролига", texts[3])

    async def test_buttons_route_to_their_own_leagues(self):
        from aiogram import Bot, Dispatcher
        from app import poller
        dp = Dispatcher()
        dp.include_router(poller.router)
        bot = Bot("42:TEST")
        try:
            with patch("app.poller.answer_league_digest", new_callable=AsyncMock) as answer:
                for i, code in enumerate(["E", "U"]):
                    await dp.feed_raw_update(bot, {
                        "update_id": i,
                        "message": {"message_id": i, "date": 1793170800,
                                    "chat": {"id": 42, "type": "private"},
                                    "from": {"id": 42, "is_bot": False, "first_name": "Test"},
                                    "text": BUTTONS[code]},
                    })
                    self.assertEqual(answer.call_args.args[1], code)
        finally:
            await bot.session.close()

    async def test_source_failure_shows_retry_message(self):
        from app.poller import answer_league_digest
        message = MagicMock()
        message.answer = AsyncMock()
        with patch("app.poller.fetch_league_digest", side_effect=DataUnavailable()), \
             self.assertLogs("app.poller", "ERROR"):
            await answer_league_digest(message, "E")
        self.assertIn("Попробуйте позже", message.answer.call_args.args[0])
