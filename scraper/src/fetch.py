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


def _decode(content: bytes) -> str:
    """Decode a page, preferring UTF-8 but falling back to latin-1.

    Books to Scrape sends no charset in its Content-Type, and different
    responses have arrived as either UTF-8 or latin-1. UTF-8-first handles
    both: a lone latin-1 byte raises UnicodeDecodeError and falls through.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace")


def polite_get(url: str, attempt: int = 1) -> str:
    """One polite HTTP GET with a single retry on transient trouble.

    Retries only timeouts, connection errors, and 5xx responses. A 404 (page
    does not exist) or 403 (site refused) is never retried - asking again
    would not help and would make a polite robot a pest.
    """
    global pages_fetched
    _respect_delay()
    pages_fetched += 1
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
    except (requests.Timeout, requests.ConnectionError):
        if attempt >= 2:
            raise FetchError(f"{url} unreachable after retry") from None
        time.sleep(1.0)
        return polite_get(url, attempt + 1)

    if response.status_code == 200:
        return _decode(response.content)
    if response.status_code >= 500 and attempt < 2:
        time.sleep(1.0)
        return polite_get(url, attempt + 1)
    raise FetchError(f"{url} returned HTTP {response.status_code}")


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
