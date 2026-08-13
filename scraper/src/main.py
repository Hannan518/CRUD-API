import argparse
import json
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

from . import config, fetch, normalize, report, validate
from .extract import extract_raw_record, parse_catalogue

FAKE_URL = "https://books.toscrape.com/catalogue/this-book-does-not-exist_99999/index.html"


def discover() -> tuple[int, int, list[tuple[str, str]]]:
    """Follow the catalogue's next links for up to MAX_CATALOGUE_PAGES pages.

    Returns (catalogue_pages, discovered_links, [(product_url, source_page_url)]),
    with duplicate product URLs collapsed to their first occurrence.
    """
    page_number = 1
    url = config.CATALOGUE_URL
    url_to_source = {}
    catalogue_pages = 0
    discovered = 0

    while True:
        cache_path = fetch.catalogue_cache_path(page_number)
        html, _ = fetch.fetch_html(url, cache_path)
        links, next_href = parse_catalogue(html)
        discovered += len(links)
        for href in links:
            url_to_source.setdefault(urljoin(url, href), url)
        catalogue_pages += 1

        if not next_href or catalogue_pages >= config.MAX_CATALOGUE_PAGES:
            break
        url = urljoin(url, next_href)
        page_number += 1

    return catalogue_pages, discovered, list(url_to_source.items())


def main():
    parser = argparse.ArgumentParser(description="Polite Books to Scrape pipeline")
    parser.add_argument(
        "--test-failure",
        action="store_true",
        help="append one deliberately broken URL to prove failures are survived",
    )
    args = parser.parse_args()

    start_time = datetime.now(timezone.utc)
    start_clock = time.monotonic()

    catalogue_pages, discovered, pages = discover()
    if args.test_failure:
        pages.append((FAKE_URL, config.CATALOGUE_URL))

    valid_records = []
    errors = []
    failed_pages = 0

    for index, (product_url, source_page) in enumerate(pages, start=1):
        try:
            cache_path = fetch.detail_cache_path(product_url)
            html, _from_cache = fetch.fetch_html(product_url, cache_path)
            raw = extract_raw_record(html, product_url, source_page)
            raw["price_gbp"] = normalize.price_to_float(raw["price_text"])
            record, reason = validate.validate_record(raw)
        except Exception as exc:
            failed_pages += 1
            print(f"SKIP {product_url}: {exc}", flush=True)
            continue

        if record is not None:
            valid_records.append(record)
        else:
            errors.append({"url": product_url, "error": reason})
        if index % 10 == 0:
            print(f"detail_pages={index}", flush=True)

    duration_seconds = round(time.monotonic() - start_clock, 2)

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUTPUT_DIR / "books.json").write_text(
        json.dumps(valid_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (config.OUTPUT_DIR / "errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report.write_run_report(
        {
            "start_time": start_time.isoformat(),
            "duration_seconds": duration_seconds,
            "catalogue_pages": catalogue_pages,
            "discovered_links": discovered,
            "unique_urls": len(pages) - (1 if args.test_failure else 0),
            "pages_fetched": fetch.pages_fetched,
            "cache_hits": fetch.cache_hits,
            "valid_records": len(valid_records),
            "invalid_records": len(errors),
            "failed_pages": failed_pages,
            "test_failure_injected": args.test_failure,
        }
    )

    print(
        f"books={len(valid_records)}  errors={len(errors)}  failed_pages={failed_pages}  "
        f"cache_hits={fetch.cache_hits}  duration={duration_seconds}s",
        flush=True,
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
