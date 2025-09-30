from __future__ import annotations

from typing import List, Dict
import zoneinfo
from datetime import datetime

from .models import Match


def format_digest(matches: List[Match], timezone_name: str, target_date_local: datetime) -> str:
    tz = zoneinfo.ZoneInfo(timezone_name)
    if not matches:
        return "Матчей не найдено."
    date_str = target_date_local.astimezone(tz).strftime("%d.%m.%Y")
    if target_date_local.date() == datetime.now(tz).date():
        date_str = f"на сегодня ({date_str})"
    else:
        date_str = f"на {date_str}"


    buckets: Dict[str, List[Match]] = {}
    for m in matches:
        buckets.setdefault(m.competition, []).append(m)

    lines: List[str] = [f"<b>Матчи {date_str}:</b>"]
    for comp in sorted(buckets.keys()):
        lines.append("")
        lines.append(f"<b>🏆 {comp} </b>")
        for m in buckets[comp]:
            local_dt = m.kickoff_utc.astimezone(tz).strftime("%H:%M")
            free = " — FREE" if m.is_free else ""
            title = f"{m.home_team} 🆚 {m.away_team}"
            if m.url:
                title = f"<a href=\"{m.url}\">{title}</a>"
            lines.append(f"{local_dt} — {title}{free}")

    return "\n".join(lines)
