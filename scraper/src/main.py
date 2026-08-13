import json
import sys
from urllib.parse import urljoin

from . import config, fetch, normalize, validate
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
    valid_records = []
    errors = []

    for index, (product_url, source_page) in enumerate(pages, start=1):
        cache_path = fetch.detail_cache_path(product_url)
        html, _from_cache = fetch.fetch_html(product_url, cache_path)
        raw = extract_raw_record(html, product_url, source_page)
        raw["price_gbp"] = normalize.price_to_float(raw["price_text"])
        record, reason = validate.validate_record(raw)
        if record is not None:
            valid_records.append(record)
        else:
            errors.append({"url": product_url, "error": reason})
        if index % 10 == 0:
            print(f"detail_pages={index}", flush=True)

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUTPUT_DIR / "books.json").write_text(
        json.dumps(valid_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (config.OUTPUT_DIR / "errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    prices_numeric = all(isinstance(r["price_gbp"], (int, float)) for r in valid_records)
    urls_https = all(str(r["product_url"]).startswith("https://") for r in valid_records)
    print(f"catalogue_pages={catalogue_pages}  books={len(valid_records)}  errors={len(errors)}")
    print(f"prices_numeric={prices_numeric}  urls_https={urls_https}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
