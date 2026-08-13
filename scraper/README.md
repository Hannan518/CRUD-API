# W5 · A9 — The polite scraper

A small, polite scraping pipeline for **Books to Scrape** (`books.toscrape.com`). It downloads the first three
catalogue pages, visits all 60 book pages, turns the messy HTML into clean, validated JSON, survives a broken
page, and ends every run with an honest report.

## Target classification

- **Site:** [Books to Scrape](https://books.toscrape.com/) (`books.toscrape.com`)
- **Why it is appropriate:** this is a public **sandbox** built specifically so people can practise web scraping —
  the site says so itself, and the whole catalogue exists for that purpose. It is the only site this project touches.
- **How much:** the first **3 catalogue pages only** (20 books each → 60 book pages). No pagination beyond that.
- **What data we collect:** title, product URL, price text and numeric price, availability, star rating, description
  (when present), the catalogue page it was found on, and the time it was fetched.
- **Robots result:** requesting `https://books.toscrape.com/robots.txt` returned **HTTP 404** — the site ships no
  robots file, so the README records: **no robots file found**.

> I will not reuse this code on another site without checking its rules and terms first.

## Run it

Lane: **Python 3.10+** (requests · Beautiful Soup · Pydantic).

```bash
cd scraper
python -m venv .venv                # one-time setup
.venv\Scripts\pip install -r requirements.txt   # Windows; on macOS/Linux: .venv/bin/pip ...
.venv\Scripts\python -m src.main    # Windows; on macOS/Linux: .venv/bin/python -m src.main
```

Output lands in `scraper/output/`: `books.json` (the 60 validated records), `errors.json` (rejected records and
why), and `run-report.json` (what the run actually did). Cached pages live in `scraper/cache/` and are git-ignored.

To prove the failure handling, add a deliberately broken URL to the list:

```bash
.venv\Scripts\python -m src.main --test-failure
```

## The record schema

Every finished record is checked against this shape (Pydantic) before it is stored; a record that fails goes to
`errors.json`, never to `books.json`:

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "description": "It's hard to imagine a world without A Light in the Attic. ...",
  "source_page": "https://books.toscrape.com/catalogue/page-1.html",
  "fetched_at": "2026-08-13T18:45:05.220257Z"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | required |
| `product_url` | URL | **canonical identity** — the same book counts once |
| `price_text` | string | the raw text, kept as scraped |
| `price_gbp` | float | the cleaned, sortable number (`£51.77` → `51.77`) |
| `availability_text` | string | required |
| `rating_text` | string | required |
| `description` | string \| null | optional — missing stays `null`, never invented |
| `source_page` | URL | provenance: which catalogue page it came from |
| `fetched_at` | datetime | provenance: when it was fetched |

## Politeness rules

- **User-agent:** every request says who it is — `FlyRankInternship-A9/1.0 (+https://github.com/Hannan518/CRUD-API)`.
- **Delay:** at least **0.5 s** between real requests to the site.
- **Timeout:** every request gives up after **10 s** instead of hanging forever.
- **Status check:** only HTTP 200 is treated as a page; anything else is a failed fetch, not HTML to parse.
- **Cache:** saved copies in `cache/` are re-read during development, so the site is asked once, not fifty times.
  The first run prints `FETCH`; later runs print `CACHE HIT`.
- **Retry (Stage 5):** one retry on timeouts, connection errors, and 5xx. A **404 or 403 is never retried** — asking
  again would not help and would make a polite robot a pest.

## Why this needed no browser

The data we wanted is already in the HTML the server sends with the catalogue and product pages — a browser would
only add cost (rendering, JavaScript, memory) on top of pages that are pure static markup.

## Honest limitation

The sandbox is occasionally slow and flaky — real runs in this assignment hit connect/read timeouts mid-run. The
cache makes reruns resumable (already-fetched pages are never fetched again), but the pipeline is single-threaded
with one retry, so a page that stays unreachable is skipped and reported in `run-report.json` rather than queued and
re-attempted. Next week's assignment (A16) replaces that with proper exponential backoff, `Retry-After` support,
and structured logs.

## Sample run report

A real `run-report.json` from this repository:

```json
{
  "start_time": "2026-08-13T18:46:34.634991+00:00",
  "duration_seconds": 4.95,
  "catalogue_pages": 3,
  "discovered_links": 60,
  "unique_urls": 60,
  "pages_fetched": 1,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "test_failure_injected": true
}
```

This one was the `--test-failure` run: 60 valid records survived, the one invented URL was skipped (`failed_pages:
1`), and the single real request (`pages_fetched: 1`) was the 404 — every real page was served from cache.

## Ethics note

Use an official API when one exists; never bypass logins, paywalls, or blocks; collect only what you need. This
project touches exactly one public sandbox that exists so people can learn scraping — the same rules do not
automatically apply anywhere else, which is why the target-classification step above is the first thing in this README.
