from __future__ import annotations

import time
from urllib.parse import urljoin
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
    p = dict(params) if params else {}
    p.setdefault("utm_referrer", "https://okko.sport/")

    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                cookies: Dict[str, str] = {}
                current_url = url
                current_params: Optional[Dict[str, Any]] = p
                for _ in range(10):
                    resp = client.get(
                        current_url,
                        params=current_params,
                        headers=merged_headers,
                        cookies=cookies,
                    )
                    if resp.status_code in (301, 302, 307, 308):
                        for k, v in resp.cookies.items():
                            cookies[k] = v
                        loc = resp.headers.get("location")
                        if not loc:
                            break
                        current_url = urljoin(str(resp.url), loc)
                        current_params = None
                        continue
                    resp.raise_for_status()
                    return resp.json()
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise last_exc
        