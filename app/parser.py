from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Dict, Iterator, List, Optional, Tuple
import zoneinfo

from .http import get_json
from .models import Match


EUROLEAGUE_KEYS = ("euroleague",)
EUROCUP_KEYS = ("eurocup",)
VTB_KEYS = ("vtb", "vtb-united", "vtb-league", "exttv")
OKKO_BASE = "https://okko.sport"


def _guess_competition(el: Dict) -> str:
    # Try explicit fields first if Okko exposes tournament name
    name = (el.get("name") or "").lower()
    original = (el.get("originalName") or "").lower()
    alias = (el.get("alias") or "").lower()

    for key in EUROLEAGUE_KEYS:
        if key in alias or key in original or key in name:
            return "Евролига"
    for key in EUROCUP_KEYS:
        if key in alias or key in original or key in name:
            return "Еврокубок"
    for key in VTB_KEYS:
        if key in alias or key in original or key in name:
            return "Единая Лига ВТБ"
    return "Прочее"


def _fetch_page(api_url: str, params: Dict[str, str], user_agent: str, page_token: Optional[str]) -> Dict:
    p = dict(params)
    if page_token:
        p["pageToken"] = page_token
    return get_json(api_url, params=p, user_agent=user_agent)


def _iter_elements(api_url: str, base_params: Dict[str, str], user_agent: str) -> Iterator[Dict]:
    token: Optional[str] = None
    seen: set[str] = set()
    while True:
        data = _fetch_page(api_url, base_params, user_agent, token)
        items = ((data.get("element") or {}).get("collectionItems") or {}).get("items", []) or []
        for it in items:
            el = it.get("element") or {}
            el_id = str(el.get("id"))
            if el_id in seen:
                continue
            seen.add(el_id)
            yield el
        page_info = (data.get("relation") or {}).get("pageInfo") or {}
        next_token = page_info.get("nextPageToken")
        if not next_token or next_token == token:
            break
        token = next_token


def fetch_matches_for_local_day(api_url: str, element_alias: str, element_type: str, max_results: int, user_agent: str, target_date_local: datetime, timezone_name: str) -> List[Match]:
    tz = zoneinfo.ZoneInfo(timezone_name)
    day_start = datetime.combine(target_date_local.date(), time.min).replace(tzinfo=tz)
    day_end = datetime.combine(target_date_local.date(), time.max).replace(tzinfo=tz)

    base_params = {
        "elementAlias": element_alias,
        "elementType": element_type,
        "maxResults": str(max_results),
        "includeProductsForUpsale": "false",
    }

    results: List[Match] = []
    for el in _iter_elements(api_url, base_params, user_agent):
        status = el.get("gameStatus")
        ko_ms = el.get("kickOffDate")
        if status != "NOT_STARTED" or not ko_ms:
            continue
        dt_utc = datetime.utcfromtimestamp(ko_ms / 1000).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        dt_local = dt_utc.astimezone(tz)
        if not (day_start <= dt_local <= day_end):
            continue
        home = ((el.get("homeOpponent") or {}).get("element") or {}).get("name")
        away = ((el.get("awayOpponent") or {}).get("element") or {}).get("name")
        alias = el.get("alias")
        is_free = (el.get("playbackAvailabilityType") == "FREE")
        if not home or not away:
            continue
        competition = _guess_competition(el)
        url = f"{OKKO_BASE}/sport/live_event/{alias}" if alias else None
        results.append(Match(home_team=home, away_team=away, kickoff_utc=dt_utc, alias=alias, is_free=is_free, competition=competition, url=url))

    results.sort(key=lambda m: m.kickoff_utc)
    return results


def find_nearest_day_with_matches(api_url: str, element_alias: str, element_type: str, max_results: int, user_agent: str, start_date_local: datetime, timezone_name: str, lookahead_days: int = 30) -> Tuple[datetime, List[Match]]:
    tz = zoneinfo.ZoneInfo(timezone_name)
    cur = start_date_local
    for offset in range(0, lookahead_days + 1):
        target = (cur + timedelta(days=offset)).replace(tzinfo=tz)
        matches = fetch_matches_for_local_day(api_url, element_alias, element_type, max_results, user_agent, target, timezone_name)
        if matches:
            return target, matches
    return start_date_local, []
