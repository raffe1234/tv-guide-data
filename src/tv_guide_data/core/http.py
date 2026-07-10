from __future__ import annotations

import requests

USER_AGENT = "tv-guide-data/0.2 (+https://github.com/raffe1234/tv-guide-data)"


def fetch_text(url: str, timeout: int = 45) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text
