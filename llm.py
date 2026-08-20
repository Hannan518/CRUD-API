"""LLM integration for POST /enrich — schemas, client, prompt, cost log."""
import json
import os
import time
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

PROMPT_DIR = Path(__file__).parent / "prompts"


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


# --------------- stub ---------------

STUB_RESPONSE = EnrichResponse(
    category=Category.other,
    summary="Stub response — no model call made.",
    quality_flags=[QualityFlag.unclear_category],
    confidence=0.0,
)


# --------------- prompt loading ---------------

def load_prompt(version: str = "v1") -> str:
    """Load the prompt file for the given version."""
    path = PROMPT_DIR / f"enrich-{version}.md"
    return path.read_text(encoding="utf-8")


# --------------- client ---------------

def get_client():
    """Create an OpenAI-compatible client pointing at the configured provider."""
    from openai import OpenAI
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=30.0,
    )


# --------------- enrich (real model call, raw text) ---------------

def enrich_record(req: EnrichRequest) -> dict:
    """Call the model and return the raw response text along with metadata."""
    system_prompt = load_prompt("v1")
    user_content = json.dumps(req.model_dump(mode="json"), ensure_ascii=False)

    start = time.monotonic()
    client = get_client()
    res = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "openrouter/free"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    duration_ms = round((time.monotonic() - start) * 1000)
    raw_text = res.choices[0].message.content or ""
    usage = res.usage

    return {
        "raw_text": raw_text,
        "model": res.model,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "duration_ms": duration_ms,
    }
