from datetime import datetime

from pydantic import BaseModel, HttpUrl, ValidationError


class BookRecord(BaseModel):
    """The finished shape of a record, checked before anything is stored.

    product_url is the canonical identity - the same book counts once even if
    it appears on several catalogue pages. description is optional.
    """

    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: str | None = None
    source_page: HttpUrl
    fetched_at: datetime


def validate_record(raw: dict) -> tuple[dict | None, list | None]:
    """Return (json_ready_record, None) or (None, reason) for a raw record."""
    try:
        record = BookRecord(**raw)
    except ValidationError as exc:
        return None, exc.errors()
    return record.model_dump(mode="json"), None
