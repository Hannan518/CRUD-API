"""LLM integration for POST /enrich — schemas, client, stub, cost log."""
import json
import os
import time
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# --------------- output schema (from JOB-CARD.md) ---------------

class Category(str, Enum):
    fiction = "fiction"
    non_fiction = "non-fiction"
    poetry = "poetry"
    science = "science"
    history = "history"
    biography = "biography"
    self_help = "self-help"
    business = "business"
    technology = "technology"
    other = "other"


class QualityFlag(str, Enum):
    missing_description = "missing_description"
    high_price = "high_price"
    low_stock = "low_stock"
    unclear_category = "unclear_category"


class EnrichResponse(BaseModel):
    category: Category
    summary: str = Field(..., min_length=1, max_length=200)
    quality_flags: list[QualityFlag] = []
    confidence: float = Field(..., ge=0.0, le=1.0)


# --------------- input schema ---------------

class EnrichRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    price_text: str = Field(..., min_length=1, max_length=100)
    availability_text: str = Field(..., min_length=1, max_length=200)


# --------------- stub (Stage 1) ---------------

STUB_RESPONSE = EnrichResponse(
    category=Category.other,
    summary="Stub response — no model call made.",
    quality_flags=[QualityFlag.unclear_category],
    confidence=0.0,
)


# --------------- client ---------------

def get_client():
    """Create an OpenAI-compatible client pointing at the configured provider."""
    from openai import OpenAI
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=30.0,
    )


# --------------- enrich (stub for now, real call in Stage 2) ---------------

def enrich_record(req: EnrichRequest) -> EnrichResponse:
    """Enrich a book record. Returns stub in Stage 1."""
    return STUB_RESPONSE
