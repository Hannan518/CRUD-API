from pathlib import Path

BASE_URL = "https://books.toscrape.com"
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/Hannan518/CRUD-API)"
TIMEOUT_SECONDS = 10
REQUEST_DELAY_SECONDS = 0.5

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
