import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.parser import ScheduleUnavailable, fetch_matches_for_local_day


class ScheduleTests(unittest.TestCase):
    def fetch(self):
        return fetch_matches_for_local_day(
            "https://example.com", "basketball-broadcasts", "SPORT_COLLECTION",
            50, "test", datetime(2026, 10, 27, tzinfo=ZoneInfo("Europe/Moscow")),
            "Europe/Moscow",
        )

    def test_antibot_is_not_an_empty_schedule(self):
        with patch("app.parser.get_json", return_value={"antibot": True}):
            with self.assertRaises(ScheduleUnavailable):
                self.fetch()

    def test_invalid_structure_is_not_an_empty_schedule(self):
        for data in ({}, {"error": "unavailable"}, {"element": {}}):
            with self.subTest(data=data), patch("app.parser.get_json", return_value=data):
                with self.assertRaises(ScheduleUnavailable):
                    self.fetch()

    def test_valid_empty_schedule(self):
        data = {"element": {"collectionItems": {"items": []}}}
        with patch("app.parser.get_json", return_value=data):
            self.assertEqual(self.fetch(), [])

    def test_network_failure_is_reported_as_unavailable(self):
        with patch("app.parser.get_json", side_effect=TimeoutError()):
            with self.assertRaises(ScheduleUnavailable):
                self.fetch()

    def test_current_season_matches_across_pages_are_filtered_and_deduplicated(self):
        def match(identifier, hour, day=27, status="NOT_STARTED"):
            kickoff = datetime(2026, 10, day, hour, tzinfo=ZoneInfo("Europe/Moscow"))
            return {"element": {
                "id": identifier, "alias": identifier + "-euroleaguebasketball-26-27",
                "kickOffDate": int(kickoff.timestamp() * 1000), "gameStatus": status,
                "homeOpponent": {"element": {"name": "Дубай Баскетбол"}},
                "awayOpponent": {"element": {"name": "Париж Баскетбол"}},
            }}

        pages = [
            {"element": {"collectionItems": {"items": [match("late", 22)]}},
             "relation": {"pageInfo": {"nextPageToken": "page2"}}},
            {"element": {"collectionItems": {"items": [
                match("early", 19), match("late", 22), match("tomorrow", 20, day=28),
                match("finished", 12, status="FINISHED"),
            ]}}},
        ]
        with patch("app.parser.get_json", side_effect=pages) as request:
            matches = self.fetch()
        self.assertEqual(len(matches), 2)
        self.assertEqual([m.kickoff_utc.astimezone(ZoneInfo("Europe/Moscow")).hour for m in matches], [19, 22])
        self.assertTrue(all(m.competition == "Евролига" for m in matches))
        self.assertEqual(request.call_args.kwargs["params"]["pageToken"], "page2")
