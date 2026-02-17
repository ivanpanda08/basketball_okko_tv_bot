from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx


DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://okko.sport/",
}


def get_json(
    url: str, 
    headers: Optional[Dict[str, str]] = None, 
    params: Optional[Dict[str, Any]] = None, 
    user_agent: Optional[str] = None, 
    timeout: float = 15.0,
    retries: int = 3
    ) -> Dict[str, Any]:

    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    if user_agent:
        merged_headers["User-Agent"] = user_agent
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                cookies=httpx.Cookies(),
            ) as client:
                resp = client.get(url, params=params, headers=merged_headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc: 
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise last_exc
        