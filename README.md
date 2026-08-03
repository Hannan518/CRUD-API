# Task API (Containerized)

A CRUD API for managing a to-do list, built with Python and FastAPI, backed by **PostgreSQL running in Docker**. This is the third storage swap in the same repo: the endpoints are identical to Assignments 1 and 2, but tasks now live in a Postgres database, and the whole stack (API + Postgres + Redis) starts with one command.

## Why Postgres in Docker?

Assignment 2 used SQLite — a single file, zero setup. This assignment swaps storage to PostgreSQL, the database you would meet in a real deployment, and runs it inside a Docker container so the environment is identical for everyone:

- **Same stack everywhere** — Docker pins the exact Postgres image, so there is no "works on my machine".
- **Persistence for real** — Postgres keeps its data in a named Docker volume, so it survives `docker compose down` and even a laptop reboot.
- **One-command startup** — `docker compose up` runs the API, the database, and Redis together.

## Requirements

- Docker Desktop (or Docker Engine + the Compose plugin), with the engine running.

## Quick start

```
git clone https://github.com/Hannan518/CRUD-API.git
cd CRUD-API
docker compose up --build
```

That builds the API image, starts Postgres and Redis, creates the `tasks` table, and seeds three example tasks. The server is at `http://localhost:8000`; Swagger UI is at `http://localhost:8000/docs`.

The compose stack supplies its own environment, so no `.env` file is needed inside Docker. A committed `.env.example` documents the same variables for running the API outside Docker:

```
DATABASE_URL=postgres://postgres:dev@localhost:5432/tasks
REDIS_URL=redis://localhost:6379/0
```

## Endpoints

| Method | Path | Description | Status Codes |
|--------|------|-------------|--------------|
| GET | `/` | API info | 200 |
| GET | `/health` | Health check (API + database `SELECT 1`) | 200 |
| GET | `/tasks` | List all tasks | 200 |
| GET | `/tasks?search=milk` | Search tasks by title (SQL `LIKE`) | 200 |
| GET | `/tasks?done=true` | Filter by done status | 200 |
| GET | `/tasks/{id}` | Get a task by ID | 200, 404 |
| GET | `/stats` | Task statistics (total / done / open) | 200 |
| POST | `/tasks` | Create a new task | 201, 400 |
| PUT | `/tasks/{id}` | Update a task | 200, 400, 404 |
| DELETE | `/tasks/{id}` | Delete a task | 204, 404 |

## Example: List all tasks

```
curl -i http://localhost:8000/tasks
```

Response (against the running compose stack):

```
HTTP/1.1 200 OK
date: Mon, 03 Aug 2026 16:13:53 GMT
server: uvicorn
content-length: 562
content-type: application/json

[{"id":1,"title":"Buy groceries","done":false,"created_at":"2026-08-03T16:10:45.306796+00:00","updated_at":"2026-08-03T16:10:45.306796+00:00"},{"id":2,"title":"Walk the dog","done":true,"created_at":"2026-08-03T16:10:45.306796+00:00","updated_at":"2026-08-03T16:10:45.306796+00:00"},{"id":3,"title":"Read a book","done":false,"created_at":"2026-08-03T16:10:45.306796+00:00","updated_at":"2026-08-03T16:10:45.306796+00:00"}]
```

## Storage

All SQL lives in one module, `db.py` (the repository), so the API routes stay storage-agnostic. The `tasks` table is created on first run, and seeded once (only when empty):

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id serial PRIMARY KEY,
    title text NOT NULL,
    done boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done);
```

Every query is parameterized (`%s` placeholders via psycopg), so user input is never glued into a query string. The API behaves exactly as in Assignment 2 — the storage swap changed the backend, not the promise.

### Persistence: why a named volume

The `db` service mounts the named volume `taskdata` at Postgres's data directory. I ran the mortality experiment on purpose: a Postgres **without** a volume was started, a table was created, the container was deleted, and a fresh one was started from the same image — the data was gone (`relation "notes" does not exist`). The compose stack keeps data because `taskdata` is a real named volume that outlives containers:

```
docker compose down     # containers stop, volume survives
docker compose up -d    # data is still there
```

### Exploring the database

`docker compose exec` opens psql inside the running database container:

```
docker compose exec db psql -U postgres -d tasks
tasks=# \dt
tasks=# SELECT id, title, done, created_at FROM tasks ORDER BY id;
```

![Tasks in Postgres](screenshots/postgres-data.png)

## Extras

### Health check with `SELECT 1`

`GET /health` verifies the API is up **and** that the database answers a real query:

```
curl http://localhost:8000/health
{"status":"ok","db":"ok"}
```

### Redis in compose

A Redis container runs as part of the stack, and the API pings it on startup (`[startup] redis reachable: True`). Nothing depends on it, so it is a graceful bonus rather than a single point of failure.

### Index + `EXPLAIN ANALYZE`

The schema indexes the column we filter by (`done`). To see what the planner actually does, I ran `EXPLAIN ANALYZE` on a scratch table with 50,000 rows before and after adding an index on a high-cardinality column:

```
BEFORE index:  Seq Scan on demo (actual time=8.081..8.766 rows=1)
               Execution Time: 8.788 ms      -- filters 49,999 rows

AFTER index:   Bitmap Index Scan on idx_demo_value (actual time=0.096..0.098)
               Execution Time: 0.142 ms      -- ~60x faster
```

One honest nuance: on the real `done` column (a 50/50 split), Postgres still prefers a sequential scan even with the index — an index scan only wins when few rows match. That is the planner doing its job; the index is still cheap insurance for skewed data.

### Multi-stage Dockerfile

The image is built in two stages: a builder stage that compiles wheels, and a slim runtime stage that only copies in the wheels it needs. `docker images`:

```
task-api:single-stage   279MB
task-api:multi-stage    279MB
```

The sizes match here because every dependency ships prebuilt wheels, so there is no compiler layer to strip. The pattern pays off the moment a package must be compiled from source — build tools stay in the builder stage and never reach the final image.

### Timestamps

Each task has `created_at` and `updated_at`, both set by Postgres (`DEFAULT now()`), with `updated_at` refreshed on every update — no application code needed.
