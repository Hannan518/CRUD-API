import json
import sys
from urllib.parse import urljoin

from . import config, fetch
from .extract import extract_raw_record, parse_catalogue


def discover() -> tuple[int, list[tuple[str, str]]]:
    """Follow the catalogue's next links for up to MAX_CATALOGUE_PAGES pages.

    Returns (catalogue_pages, [(product_url, source_page_url), ...]) with
    duplicate product URLs collapsed to their first occurrence.
    """
    page_number = 1
    url = config.CATALOGUE_URL
    url_to_source = {}
    catalogue_pages = 0

    while True:
        cache_path = fetch.catalogue_cache_path(page_number)
        html, _ = fetch.fetch_html(url, cache_path)
        links, next_href = parse_catalogue(html)
        for href in links:
            url_to_source.setdefault(urljoin(url, href), url)
        catalogue_pages += 1

        if not next_href or catalogue_pages >= config.MAX_CATALOGUE_PAGES:
            break
        url = urljoin(url, next_href)
        page_number += 1

    return catalogue_pages, list(url_to_source.items())


def main():
    catalogue_pages, pages = discover()
    raw_records = []

    for index, (product_url, source_page) in enumerate(pages, start=1):
        cache_path = fetch.detail_cache_path(product_url)
        html, _from_cache = fetch.fetch_html(product_url, cache_path)
        raw_records.append(extract_raw_record(html, product_url, source_page))
        if index % 10 == 0:
            print(f"detail_pages={index}", flush=True)

    print(json.dumps(raw_records[0], indent=2, ensure_ascii=False), flush=True)
    print(f"detail_pages={len(raw_records)}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
