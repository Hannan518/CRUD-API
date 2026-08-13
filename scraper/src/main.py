import sys
from urllib.parse import urljoin

from . import config, fetch
from .extract import parse_catalogue


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
    print(
        f"catalogue_pages={catalogue_pages}  discovered={len(pages)}  unique_urls={len(pages)}",
        flush=True,
    )
    for product_url, _source_page in pages:
        print(product_url, flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
