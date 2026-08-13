import sys

from . import config, fetch


def main():
    url = config.CATALOGUE_URL
    cache_path = config.CACHE_DIR / "catalogue-page-1.html"
    html, from_cache = fetch.fetch_html(url, cache_path)
    verb = "CACHE HIT" if from_cache else "FETCH"
    print(f"{verb}: {url}  ({len(html)} bytes)", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
