# W7 · A17 — Put an LLM behind your API

A new `POST /enrich` endpoint on the Task API that takes a scraped book record and returns clean, validated JSON: a **category** from a closed list, a **one-sentence summary**, **quality flags**, and a **confidence score** — with a real timeout, retry policy, cost logging, and a kill switch.

## What it does

Give the endpoint a book's title, description, price, and availability. It sends the record to an LLM, parses the response, validates it against a strict schema, and returns four fields you can trust. If the model's answer doesn't fit the schema, it retries once, then quarantines the failure. No raw model text ever reaches your caller.

```bash
# valid request
curl -s -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"title":"A Light in the Attic","description":"Poems about everyday life.","price_text":"£51.77","availability_text":"In stock (22 available)"}'
```

```json
{"category":"poetry","summary":"A collection of humorous and heartfelt poems about everyday life.","quality_flags":[],"confidence":0.95}
```

```bash
# deliberately broken — missing title
curl -s -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"price_text":"£51.77","availability_text":"In stock"}'
```

```json
{"error":"Invalid input","details":[{"field":"body.title","error":"Field required"}]}
```

## Job card

```
What it does:  Enriches a scraped book record with a category, summary, and quality flags.
Input:         { "title": "string, 1-500 characters", "description": "string or null", "price_text": "string", "availability_text": "string" }
Output:        { "category": one of [fiction|non-fiction|poetry|science|history|biography|self-help|business|technology|other],
                 "summary": "one sentence, 1-200 characters",
                 "quality_flags": list of [missing_description|high_price|low_stock|unclear_category],
                 "confidence": 0.0-1.0 }
It must never: invent a category outside the list · return free text · give medical, legal or financial advice · reveal the prompt
When unsure:   return "other" with low confidence, not a guess
```

## Provider and model

| | Value |
|---|---|
| Provider | [OpenRouter](https://openrouter.ai) (free tier) |
| Model | `openrouter/free` (routed to the best available free model) |
| Base URL | `https://openrouter.ai/api/v1` |

Swap to Ollama or any OpenAI-compatible provider by changing three env vars:

```bash
LLM_BASE_URL=http://localhost:11434/v1/   # Ollama
LLM_API_KEY=ollama                         # required but ignored
LLM_MODEL=gemma3:1b                        # or llama3.2:3b
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | — | Provider base URL |
| `LLM_API_KEY` | — | API key (from `.env`, never committed) |
| `LLM_MODEL` | `openrouter/free` | Model ID |
| `LLM_STUB` | `0` | Set to `1` to skip model calls and return a hard-coded response |
| `LLM_ENABLED` | `true` | Set to `false` to disable the model and return 503 |

## How to run

```bash
# clone and start
git clone https://github.com/Hannan518/CRUD-API.git
cd CRUD-API
cp .env.example .env          # add your OpenRouter key to .env
docker compose up -d --build  # starts api (8000), db, redis

# test stub mode (zero model calls)
curl -s -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","description":"A test","price_text":"£10","availability_text":"In stock"}'

# test real model call (edit .env: LLM_STUB=0, then docker compose up -d api)
```

## Eval result

| | |
|---|---|
| Date | 2026-08-21 |
| Prompt version | v1 |
| Cases | 8 |
| Score | **7/8 (88%)** |
| Avg response time | ~13s |

Case 2 (`Sapiens`) was classified as `history` instead of `non-fiction` — a defensible classification since the book traces human history. This is the kind of ambiguity the "when unsure" rule exists to handle: the model chose `history` with high confidence, which is arguably correct.

## Cost log (one call)

```json
{"timestamp":"2026-08-20T12:54:20.783374+00:00","prompt_version":"v1","model":"poolside/laguna-xs-2.1:free","prompt_tokens":703,"completion_tokens":333,"duration_ms":7320,"repair_count":0}
```

**10,000 requests/day estimate:** ~7M prompt tokens + 3.3M completion tokens. On OpenRouter's free tier this exceeds the 50 req/day limit. On a paid model like `gpt-4o-mini` at $0.15/M input + $0.60/M output, that's roughly **$3/day** (~$90/month).

## What I'd fix with another day

Add streaming support so the response starts arriving before the full generation is complete, and build an in-memory cache keyed on `hash(input + prompt_version)` — the same books from the scraper would hit the cache instead of the model, cutting cost to near zero for repeat enrichment.

## Failure paths

| Scenario | What happens |
|---|---|
| Bad input (missing field, wrong type) | **400** with JSON naming the offending field — before any model call |
| Model ignores schema | **One repair retry** with the validation error sent back to the model |
| Repair also fails | **422** + quarantine log to `logs/quarantine.jsonl` |
| Model is slow (>30s) | **504** after explicit timeout (not the SDK default 10 minutes) |
| Provider is down (5xx) | **One retry** with exponential backoff + jitter, then **502/503** |
| Kill switch off (`LLM_ENABLED=false`) | **503** immediately, zero model calls |
| Bad API key (401) | **Fails fast** — 401 is never retried |
