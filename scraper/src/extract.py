from datetime import datetime, timezone

from bs4 import BeautifulSoup


def parse_catalogue(html: str) -> tuple[list[str], str | None]:
    """Return (book_link_hrefs, next_page_href) from a catalogue page."""
    soup = BeautifulSoup(html, "html.parser")
    links = [a.get("href") for a in soup.select(".product_pod h3 a")]
    next_el = soup.select_one("li.next a")
    next_href = next_el.get("href") if next_el else None
    return links, next_href


def extract_raw_record(html: str, product_url: str, source_page: str) -> dict:
    """Pull the eight raw fields out of one book detail page.

    Selectors aim at the product area of the page. Missing data stays None -
    nothing is invented. provenance (source_page, fetched_at) is kept on the record.
    """
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None

    price_el = soup.select_one(".price_color")
    price_text = price_el.get_text(strip=True) if price_el else None

    avail_el = soup.select_one(".availability")
    availability_text = avail_el.get_text(" ", strip=True) if avail_el else None

    rating_el = soup.select_one("p.star-rating")
    rating_classes = rating_el.get("class") if rating_el else None
    rating_text = rating_classes[1] if rating_classes and len(rating_classes) > 1 else None

    description = None
    desc_el = soup.select_one("#product_description")
    if desc_el is not None:
        desc_p = desc_el.find_next_sibling("p")
        if desc_p is not None:
            description = desc_p.get_text(strip=True)

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
