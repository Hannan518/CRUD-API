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

## Run

(Install + run instructions are completed in Stage 6.)
