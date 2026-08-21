# CRUD API — Task Manager + Scraper + LLM Enrichment

A full-stack backend project: a **Task CRUD API** with Supabase Auth, a **polite web scraper** that collects 60 books, and a **POST /enrich endpoint** that sends scraped book records to an LLM and returns clean, validated JSON. The whole stack (API + Postgres + Redis) starts with one command.

## Quick Start

```bash
git clone https://github.com/Hannan518/CRUD-API.git
cd CRUD-API
cp .env.example .env          # add your Supabase + OpenRouter keys
docker compose up -d --build  # starts api (8000), db, redis
```

Open `http://localhost:8000/docs` for interactive Swagger UI.

## Project Structure

```
├── main.py              FastAPI app, all routes
├── db.py                Postgres + Redis connection layer
├── auth.py              Supabase Auth routes (signup, login, logout, protected)
├── errors.py            TaskError exception + handler
├── llm.py               LLM client, schemas, prompt loading, retry, cost logging
├── prompts/
│   └── enrich-v1.md     Versioned prompt for book enrichment
├── evals/
│   ├── cases.json       8 hand-labelled test cases
│   └── run_eval.py      Automated eval script
├── scraper/             Polite scraper for books.toscrape.com (60 books)
│   ├── src/             Scraper source code
│   ├── output/          books.json, run-report.json, errors.json
│   └── README.md        Full scraper documentation
├── compose.yaml         Docker Compose: api + db + redis
├── Dockerfile           Multi-stage Python 3.12-slim build
├── .env.example         Template for all environment variables
├── JOB-CARD.md          Enrichment endpoint specification
└── requirements.txt     fastapi, uvicorn, psycopg, python-dotenv, redis, supabase, openai
```

---

## 1. Task CRUD API

A CRUD API for managing a to-do list, built with FastAPI and backed by **PostgreSQL running in Docker**. Assignment 4 adds **Supabase Auth**: sign up, log in, log out, and JWT-verified protected routes.

### Endpoints

| Method | Path | Description | Status Codes |
|--------|------|-------------|--------------|
| GET | `/` | API info | 200 |
| GET | `/health` | Health check (API + database) | 200 |
| GET | `/tasks` | List all tasks | 200 |
| GET | `/tasks?search=milk` | Search tasks by title | 200 |
| GET | `/tasks?done=true` | Filter by done status | 200 |
| GET | `/tasks/{id}` | Get a task by ID | 200, 404 |
| GET | `/stats` | Task statistics (total / done / open) | 200 |
| POST | `/tasks` | Create a new task | 201, 400 |
| PUT | `/tasks/{id}` | Update a task | 200, 400, 404 |
| DELETE | `/tasks/{id}` | Delete a task | 204, 404 |
| POST | `/auth/signup` | Register a new user | 201, 400 |
| POST | `/auth/login` | Log in, receive `access_token` | 200, 401 |
| POST | `/auth/logout` | Log out (Bearer token required) | 204, 401 |
| GET | `/protected/profile` | Current user's profile | 200, 401 |
| GET | `/protected/dashboard` | Protected greeting | 200, 401 |
| GET | `/public/info` | Public API info (no auth) | 200 |
| POST | `/enrich` | Enrich a book record with LLM | 200, 400, 422, 503 |

### Example: List all tasks

```bash
curl -i http://localhost:8000/tasks
```

```json
[{"id":1,"title":"Buy groceries","done":false,"created_at":"2026-08-03T16:10:45.306796+00:00","updated_at":"2026-08-03T16:10:45.306796+00:00"},{"id":2,"title":"Walk the dog","done":true,...},{"id":3,"title":"Read a book","done":false,...}]
```

### Supabase Auth

Signup, login and logout are delegated to **Supabase Auth**. Protected routes verify the caller's JSON Web Token against Supabase before answering. On startup the API reports: `[startup] connected to Supabase: True`.

All auth code lives in `auth.py` behind a single `HTTPBearer` scheme. Missing body fields return `400`; a missing, malformed or expired Bearer token returns `401`.

```bash
# Sign up (201)
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"supersecret123"}'

# Log in (200, returns access_token)
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"supersecret123"}'

# Access protected route (200 with profile; 401 without valid token)
curl -s http://localhost:8000/protected/profile \
  -H "Authorization: Bearer <access_token>"

# Log out (204 — revokes session with Supabase)
curl -i -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

### Storage

All SQL lives in `db.py`. The `tasks` table is created on first run, and seeded only when empty:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id serial PRIMARY KEY,
    title text NOT NULL,
    done boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

Every query is parameterized (`%s` placeholders via psycopg). The `taskdata` named volume keeps data alive across `docker compose down` and restarts.

```bash
docker compose exec db psql -U postgres -d tasks
```

### Why Postgres in Docker?

- **Same stack everywhere** — Docker pins the exact Postgres image, no "works on my machine".
- **Persistence** — data lives in a named Docker volume, survives container removal.
- **One-command startup** — `docker compose up` runs the API, Postgres, and Redis together.

---

## 2. Polite Scraper

A scraping pipeline for [Books to Scrape](https://books.toscrape.com/) (a public sandbox built for practicing scraping). It downloads the first 3 catalogue pages, visits all 60 book pages, turns messy HTML into clean validated JSON, and ends every run with an honest report.

### Run it

```bash
cd scraper
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m src.main
```

Output lands in `scraper/output/`: `books.json` (60 validated records), `errors.json` (rejected records), `run-report.json` (run statistics).

### Record schema

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | required |
| `product_url` | URL | canonical identity — same book counts once |
| `price_text` | string | raw text as scraped |
| `price_gbp` | float | cleaned number (`£51.77` → `51.77`) |
| `availability_text` | string | required |
| `rating_text` | string | required |
| `description` | string \| null | optional — missing stays `null`, never invented |
| `source_page` | URL | which catalogue page it came from |
| `fetched_at` | datetime | when it was fetched |

### Politeness rules

- **User-agent:** `FlyRankInternship-A9/1.0 (+https://github.com/Hannan518/CRUD-API)`
- **Delay:** at least 0.5s between real requests
- **Timeout:** 10s per request
- **Cache:** saved copies in `cache/` — site is asked once, not fifty times
- **Retry:** one retry on timeouts/5xx; 404 and 403 never retried

Full documentation: [`scraper/README.md`](scraper/README.md)

### Sample run report

```json
{
  "start_time": "2026-08-13T18:46:34.634991+00:00",
  "duration_seconds": 4.95,
  "catalogue_pages": 3,
  "discovered_links": 60,
  "unique_urls": 60,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "test_failure_injected": true
}
```

---

## 3. LLM Enrichment

A `POST /enrich` endpoint that takes a scraped book record and returns clean, validated JSON: a **category** from a closed list, a **one-sentence summary**, **quality flags**, and a **confidence score** — with a real timeout, retry policy, cost logging, and a kill switch.

### How it works

```
Request → POST /enrich
  ├─ LLM_ENABLED=false?  → 503 immediately
  ├─ LLM_STUB=1?         → return fake JSON instantly
  ├─ Bad input?          → 400 naming the field
  └─ Call model (with timeout + retry)
       ├─ Parse JSON from response (strip fences, regex extract)
       ├─ Validate against Pydantic schema
       │    ├─ Fail → send back to model once ("repair")
       │    │         ├─ Second attempt valid? → return it
       │    │         └─ Still broken? → quarantine + 422
       │    └─ Pass → return clean JSON
       └─ Log cost to stdout (tokens, duration, model, repair count)
```

### curl examples

```bash
# Valid request
curl -s -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"title":"A Light in the Attic","description":"Poems about everyday life.","price_text":"£51.77","availability_text":"In stock (22 available)"}'
```

```json
{"category":"poetry","summary":"A collection of humorous and heartfelt poems about everyday life.","quality_flags":[],"confidence":0.95}
```

```bash
# Deliberately broken — missing title
curl -s -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"price_text":"£51.77","availability_text":"In stock"}'
```

```json
{"error":"Invalid input","details":[{"field":"body.title","error":"Field required"}]}
```

### Job card

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

### Provider and model

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

### Eval result

| | |
|---|---|
| Date | 2026-08-21 |
| Prompt version | v1 |
| Cases | 8 |
| Score | **7/8 (88%)** |
| Avg response time | ~13s |

Case 2 (`Sapiens`) was classified as `history` instead of `non-fiction` — a defensible classification since the book traces human history. The model chose `history` with high confidence, which is arguably correct.

```bash
# Run the eval yourself
.venv\Scripts\python.exe evals\run_eval.py
```

### Cost log

```json
{"timestamp":"2026-08-20T12:54:20.783374+00:00","prompt_version":"v1","model":"poolside/laguna-xs-2.1:free","prompt_tokens":703,"completion_tokens":333,"duration_ms":7320,"repair_count":0}
```

**10,000 requests/day estimate:** ~7M prompt tokens + 3.3M completion tokens. On OpenRouter's free tier this exceeds the 50 req/day limit. On a paid model like `gpt-4o-mini` at $0.15/M input + $0.60/M output, that's roughly **$3/day** (~$90/month).

### Failure paths

| Scenario | What happens |
|---|---|
| Bad input (missing field, wrong type) | **400** with JSON naming the offending field |
| Model ignores schema | **One repair retry** with the validation error sent back to the model |
| Repair also fails | **422** + quarantine log to `logs/quarantine.jsonl` |
| Model is slow (>30s) | **504** after explicit timeout |
| Provider is down (5xx) | **One retry** with exponential backoff + jitter, then **502/503** |
| Kill switch off (`LLM_ENABLED=false`) | **503** immediately, zero model calls |
| Bad API key (401) | **Fails fast** — 401 is never retried |

### What I'd fix with another day

Add streaming support so the response starts arriving before the full generation is complete, and build an in-memory cache keyed on `hash(input + prompt_version)` — the same books from the scraper would hit the cache instead of the model, cutting cost to near zero for repeat enrichment.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string |
| `REDIS_URL` | — | Redis connection string |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_KEY` | — | Supabase anon public key |
| `LLM_BASE_URL` | — | LLM provider base URL |
| `LLM_API_KEY` | — | LLM API key (from `.env`, never committed) |
| `LLM_MODEL` | `openrouter/free` | Model ID |
| `LLM_STUB` | `0` | Set to `1` to skip model calls and return a hard-coded response |
| `LLM_ENABLED` | `true` | Set to `false` to disable the model and return 503 |

All keys live in `.env` (git-ignored). See `.env.example` for the template.

---

## Extras

### Health check

`GET /health` verifies the API is up **and** the database answers a real query:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok"}
```

### Redis

A Redis container runs as part of the stack and the API pings it on startup (`[startup] redis reachable: True`). Nothing depends on it — it is a graceful bonus, not a single point of failure.

### Multi-stage Dockerfile

The image is built in two stages: a builder that compiles wheels, and a slim runtime that only copies in what it needs. Build tools stay in the builder stage and never reach the final image.

### Timestamps

Each task has `created_at` and `updated_at`, both set by Postgres (`DEFAULT now()`), with `updated_at` refreshed on every update — no application code needed.
