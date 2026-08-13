"""Polite fetching with caching.

Every real request identifies itself, gives up after a timeout, and waits at
least REQUEST_DELAY_SECONDS since the last one. Pages are cached to disk so
development reads saved copies instead of asking the site again.
"""

import time
from urllib.parse import urlparse

import requests

from .config import REQUEST_DELAY_SECONDS, TIMEOUT_SECONDS, USER_AGENT

_last_request_at = 0.0
pages_fetched = 0
cache_hits = 0


class FetchError(Exception):
    """Raised when a page cannot be fetched or is not HTTP 200."""


def _respect_delay():
    global _last_request_at
    elapsed = time.time() - _last_request_at
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_at = time.time()


def polite_get(url: str) -> str:
    """One real HTTP GET: honest user-agent, timeout, status check, politeness delay."""
    global pages_fetched
    _respect_delay()
    pages_fetched += 1
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise FetchError(f"{url} returned HTTP {response.status_code}")
    return response.text


def fetch_html(url: str, cache_path) -> tuple[str, bool]:
    """Return (html, from_cache) for a URL, preferring the saved copy when present."""
    global cache_hits
    if cache_path.exists():
        cache_hits += 1
        return cache_path.read_text(encoding="utf-8"), True
    text = polite_get(url)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text, False


def cache_name(url: str) -> str:
    """Turn a URL into a stable cache filename."""
    path = urlparse(url).path.strip("/")
    name = path.replace("/", "-").replace("index.html", "index")
    return f"{name}.html"


def catalogue_cache_path(page_number: int):
    from .config import CACHE_DIR

    return CACHE_DIR / f"catalogue-page-{page_number}.html"


def detail_cache_path(url: str):
    from .config import CACHE_DIR

    return CACHE_DIR / cache_name(url)
