from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class Match(BaseModel):
    home_team: str
    away_team: str
    kickoff_utc: datetime
    alias: str | None = None
    is_free: bool = False
    competition: str = "Прочее"
    url: str | None = None

