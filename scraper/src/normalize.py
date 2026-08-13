def price_to_float(price_text: str | None) -> float | None:
    """Turn a price string like '£51.77' into the number 51.77.

    Returns None when the text cannot be parsed; the schema validator then
    sends the record to errors.json instead of crashing the run.
    """
    if price_text is None:
        return None
    cleaned = price_text.replace("\u00a3", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
