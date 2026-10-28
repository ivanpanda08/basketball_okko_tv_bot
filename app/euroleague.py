"""EuroLeague / EuroCup data, independent of the Okko broadcast schedule."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
import logging
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field, ValidationError


API_BASE = "https://api-live.euroleague.net"
COMPETITIONS = {"E": "Евролига", "U": "Еврокубок"}
BUTTONS = {"E": "🏀 Евролига", "U": "🏆 Еврокубок"}
logger = logging.getLogger(__name__)


class DataUnavailable(RuntimeError):
    pass


class Club(BaseModel):
    code: str
    name: str
    abbreviatedName: str = ""

    @property
    def title(self) -> str:
        return escape(self.abbreviatedName.strip() or self.name)


class Side(BaseModel):
    club: Club
    score: int = Field(ge=0, strict=True)


class Game(BaseModel):
    gameCode: int
    round: int
    played: bool = Field(strict=True)
    utcDate: datetime
    local: Side
    road: Side
    phaseType: dict


class Standing(BaseModel):
    position: int = Field(ge=1)
    club: Club
    gamesPlayed: int = Field(ge=0)
    gamesWon: int = Field(ge=0)
    gamesLost: int = Field(ge=0)
    groupName: str


@dataclass
class LeagueDigest:
    competition: str
    season: str
    fetched_at: datetime
    period_start: datetime
    period_end: datetime
    results: list[Game]
    standings: list[Standing]
    standings_round: int | None
    standings_unavailable: bool = False


def _get(client: httpx.Client, path: str, **params) -> dict:
    response = client.get(API_BASE + path, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def _all_pages(client: httpx.Client, path: str) -> list[dict]:
    rows: list[dict] = []
    for _ in range(100):
        payload = _get(client, path, limit=200, offset=len(rows))
        page, total = payload["data"], payload["total"]
        if not isinstance(page, list) or not isinstance(total, int) or total < 0:
            raise ValueError("Invalid paginated response")
        rows.extend(page)
        if len(rows) >= total:
            return rows
        if not page:
            raise ValueError("Incomplete paginated response")
    raise ValueError("Too many API pages")


def fetch_league_digest(
    competition: str, now: datetime, timezone_name: str = "Europe/Moscow",
    weekly: bool = False,
) -> LeagueDigest:
    if competition not in COMPETITIONS:
        raise ValueError("Unknown competition")
    tz = ZoneInfo(timezone_name)
    now = now.astimezone(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = midnight if weekly else now
    start = midnight - timedelta(days=7 if weekly else 6)
    try:
        with httpx.Client(timeout=20, follow_redirects=True, transport=httpx.HTTPTransport(retries=2)) as client:
            seasons = _all_pages(client, f"/v2/competitions/{competition}/seasons")
            active = [s for s in seasons if datetime.fromisoformat(
                s.get("activationDate") or s["startDate"]
            ).date() <= now.date()]
            season = max(active, key=lambda s: int(s["year"]))
            code = season["code"]
            path = f"/v2/competitions/{competition}/seasons/{code}"
            games = [Game.model_validate(g) for g in _all_pages(client, path + "/games")]
            if any(g.utcDate.tzinfo is None for g in games):
                raise ValueError("Missing UTC timezone on a game")
            if len({g.gameCode for g in games}) != len(games):
                raise ValueError("Duplicate games in API pagination")
            played = [g for g in games if g.played and g.utcDate <= now]
            # Future rounds return empty tables. Use the latest played group round,
            # including an unfinished round, and keep the API's official positions.
            rounds = [g.round for g in played if g.phaseType.get("code") == "RS"]
            standings_round = max(rounds, default=None)
            standings: list[Standing] = []
            unavailable = False
            if standings_round is not None:
                try:
                    data = _get(client, f"/v3/competitions/{competition}/seasons/{code}"
                                f"/rounds/{standings_round}/basicstandings")
                    standings = [Standing.model_validate(t) for t in data["teams"]]
                    if not standings:
                        raise ValueError("Empty standings after played games")
                    regular_games = [g for g in played if g.phaseType.get("code") == "RS"]
                    counts: dict[str, int] = {}
                    for game in regular_games:
                        for side in (game.local, game.road):
                            counts[side.club.code] = counts.get(side.club.code, 0) + 1
                    if ({t.club.code: t.gamesPlayed for t in standings if t.gamesPlayed}
                            != counts):
                        raise ValueError("Standings have not caught up with completed games")
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    logger.exception("Standings unavailable for %s", code)
                    standings, unavailable = [], True
            return LeagueDigest(
                competition, season.get("alias", code), now, start, end,
                sorted([g for g in played if start <= g.utcDate < end], key=lambda g: g.utcDate),
                standings, standings_round, unavailable,
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError) as exc:
        raise DataUnavailable(f"Could not load {competition} data") from exc


def _split_lines(header: str, lines: list[str], limit: int = 3500) -> list[str]:
    """Split at complete HTML lines; leave room below Telegram's 4096 limit."""
    messages: list[str] = []
    current = header
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            messages.append(current)
            current = header + "\n<i>Продолжение</i>"
        current += "\n" + line
    messages.append(current)
    return messages


def format_league_digest(digest: LeagueDigest) -> list[str]:
    heading = f"<b>{BUTTONS[digest.competition]} · {escape(digest.season)}</b>"
    stamp = digest.fetched_at.strftime("%d.%m.%Y %H:%M")
    tz_label = "МСК" if str(digest.fetched_at.tzinfo) == "Europe/Moscow" else str(digest.fetched_at.tzinfo)
    heading += f"\n<i>Обновлено {stamp} {escape(tz_label)}</i>"
    last_day = (digest.period_end - timedelta(microseconds=1)).strftime("%d.%m.%Y")
    result_lines = [f"<b>Результаты {digest.period_start:%d.%m.%Y}–{last_day}</b>"]
    day = None
    for game in digest.results:
        local = game.utcDate.astimezone(digest.fetched_at.tzinfo)
        if local.date() != day:
            result_lines.append(f"\n<b>{local:%d.%m}</b>")
            day = local.date()
        result_lines.append(f"{game.local.club.title} <b>{game.local.score}:{game.road.score}</b> {game.road.club.title}")
    if not digest.results:
        result_lines.append("За этот период завершённых матчей нет.")
    messages = _split_lines(heading, result_lines)
    table_lines = ["<b>Таблица регулярного сезона</b>", "Место · команда · победы–поражения"]
    if digest.standings_unavailable:
        table_lines = ["Таблица временно недоступна или ещё обновляется. Попробуйте позже."]
    elif not digest.standings:
        table_lines = ["Матчей регулярного сезона пока не сыграно. Таблица появится после первых результатов."]
    else:
        groups: dict[str, list[Standing]] = {}
        for team in digest.standings:
            groups.setdefault(team.groupName, []).append(team)
        for group, teams in sorted(groups.items()):
            if digest.competition == "U" or len(groups) > 1:
                label = group.removeprefix("Group ")
                table_lines.append(f"\n<b>Группа {escape(label)}</b>")
            for team in sorted(teams, key=lambda t: t.position):
                table_lines.append(f"{team.position}. {team.club.title} — <b>{team.gamesWon}–{team.gamesLost}</b>")
        table_lines.append(f"\n<i>По данным API: тур {digest.standings_round}. Источник: EuroLeague Basketball.</i>")
    messages.extend(_split_lines(heading, table_lines))
    return messages
