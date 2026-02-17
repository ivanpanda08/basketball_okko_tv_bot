from __future__ import annotations

import logging
import time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://okko.sport/",
}

UTM_REFERRER = "https://okko.sport/"


def _ensure_utm_referrer(u: str) -> str:
    parsed = urlparse(u)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if "utm_referrer" not in qs:
        qs["utm_referrer"] = [UTM_REFERRER]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


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
    p.setdefault("utm_referrer", UTM_REFERRER)

    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                cookies: Dict[str, str] = {}
                current_url = url
                current_params: Optional[Dict[str, Any]] = p
                for step in range(10):
                    logger.debug(
                        "get_json attempt=%s step=%s url=%s params=%s cookies_keys=%s",
                        attempt + 1, step, current_url, current_params, list(cookies.keys()),
                    )
                    resp = client.get(
                        current_url,
                        params=current_params,
                        headers=merged_headers,
                        cookies=cookies,
                    )
                    logger.debug(
                        "get_json response status=%s url=%s",
                        resp.status_code, resp.url,
                    )
                    if resp.status_code in (301, 302, 307, 308):
                        cookies.update(dict(resp.cookies))
                        loc = resp.headers.get("location")
                        logger.info(
                            "get_json redirect status=%s location=%s cookies=%s",
                            resp.status_code, loc, list(cookies.keys()),
                        )
                        if not loc:
                            break
                        current_url = _ensure_utm_referrer(
                            urljoin(str(resp.url), loc)
                        )
                        current_params = None
                        continue
                    resp.raise_for_status()
                    logger.debug("get_json success url=%s", resp.url)
                    return resp.json()
                logger.warning("get_json redirect loop ended without 2xx step=%s status=%s", step, resp.status_code)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            last_exc = exc
            logger.warning("get_json attempt=%s failed: %s", attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise last_exc
        