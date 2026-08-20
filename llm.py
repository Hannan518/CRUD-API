"""LLM integration for POST /enrich — schemas, client, prompt, parse, repair, cost log."""
import json
import os
import re
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

PROMPT_DIR = Path(__file__).parent / "prompts"
LOG_DIR = Path(__file__).parent / "logs"


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


# --------------- JSON parsing ---------------

def _extract_json(text: str) -> dict | None:
    """Strip markdown fences and extract the first JSON object from model output."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned)
    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# --------------- quarantine ---------------

def _quarantine(raw_text: str, error: str, prompt_version: str, input_data: dict):
    """Write one line to logs/quarantine.jsonl so a bad answer is never lost."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "input": input_data,
        "raw_output": raw_text,
        "error": error,
    }, ensure_ascii=False)
    with open(LOG_DIR / "quarantine.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# --------------- client ---------------

def get_client():
    """Create an OpenAI-compatible client pointing at the configured provider."""
    from openai import OpenAI
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=30.0,
    )


# --------------- single model call ---------------

def _call_model(client, system_prompt: str, user_content: str) -> tuple[str, dict]:
    """Make one model call and return (raw_text, usage_info)."""
    model = os.environ.get("LLM_MODEL", "openrouter/free")
    start = time.monotonic()
    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    duration_ms = round((time.monotonic() - start) * 1000)
    raw_text = res.choices[0].message.content or ""
    usage = res.usage
    info = {
        "model": res.model,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "duration_ms": duration_ms,
    }
    return raw_text, info


# --------------- enrich (with parse + repair + quarantine) ---------------

def enrich_record(req: EnrichRequest) -> dict:
    """Call the model, parse JSON, validate, repair once if needed, quarantine on failure.

    Returns a dict with the validated response and metadata.
    Raises ValueError if both attempts fail (caller returns 422).
    """
    system_prompt = load_prompt("v1")
    user_content = json.dumps(req.model_dump(mode="json"), ensure_ascii=False)
    client = get_client()
    prompt_version = "v1"

    # --- first attempt ---
    raw_text, info = _call_model(client, system_prompt, user_content)
    parsed = _extract_json(raw_text)

    if parsed is not None:
        try:
            validated = EnrichResponse.model_validate(parsed)
            return {"response": validated, **info, "repair_count": 0}
        except ValidationError as ve:
            first_error = str(ve)
    else:
        first_error = "No JSON object found in model output"

    # --- repair retry (once) ---
    repair_prompt = (
        f"Your previous answer was rejected for this reason: {first_error}\n\n"
        f"Your answer was:\n{raw_text}\n\n"
        "Return ONLY corrected JSON matching the schema. No explanation, no markdown fence."
    )
    raw_text2, info2 = _call_model(client, system_prompt, repair_prompt)
    info2["duration_ms"] = info["duration_ms"] + info2["duration_ms"]
    parsed2 = _extract_json(raw_text2)

    if parsed2 is not None:
        try:
            validated = EnrichResponse.model_validate(parsed2)
            return {"response": validated, **info2, "repair_count": 1}
        except ValidationError as ve2:
            second_error = str(ve2)
    else:
        second_error = "No JSON object found in repair attempt"

    # --- both failed: quarantine and raise ---
    _quarantine(
        raw_text=raw_text,
        error=f"First: {first_error} | Repair: {second_error}",
        prompt_version=prompt_version,
        input_data=req.model_dump(mode="json"),
    )
    raise ValueError(f"Model output could not be repaired: {second_error}")
