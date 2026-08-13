from bs4 import BeautifulSoup


def parse_catalogue(html: str) -> tuple[list[str], str | None]:
    """Return (book_link_hrefs, next_page_href) from a catalogue page."""
    soup = BeautifulSoup(html, "html.parser")
    links = [a.get("href") for a in soup.select(".product_pod h3 a")]
    next_el = soup.select_one("li.next a")
    next_href = next_el.get("href") if next_el else None
    return links, next_href
