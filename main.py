import os

import auth
import db
import llm
from dotenv import load_dotenv
from errors import TaskError, task_error_handler
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A CRUD API for managing tasks with Supabase Auth (signup, login, logout, protected routes).",
)

app.add_exception_handler(TaskError, task_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    """Return 400 (not 422) for input validation failures, naming the field."""
    from fastapi.responses import JSONResponse

    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        errors.append({"field": field, "error": err.get("msg", "invalid")})
    return JSONResponse(status_code=400, content={"error": "Invalid input", "details": errors})

app.include_router(auth.router)
app.include_router(auth.info_router)

load_dotenv()
db.init_db()


@app.on_event("startup")
def check_services():
    print(f"[startup] redis reachable: {db.ping_redis()}", flush=True)
    print(f"[startup] connected to Supabase: {auth.check_connection()}", flush=True)


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.get("/", summary="API info")
def read_root():
    """Return API name, version, and available endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks", "/auth/signup", "/auth/login", "/auth/logout", "/protected/profile", "/protected/dashboard", "/public/info", "/enrich"]}


@app.get("/health", summary="Health check")
def health():
    """Check that the API is running and the database is reachable."""
    try:
        db.ping()
        db_ok = "ok"
    except Exception:
        db_ok = "error"
    return {"status": "ok", "db": db_ok}


@app.get("/tasks", summary="List all tasks")
def list_tasks(
    search: str | None = None,
    done: bool | None = None,
):
    """Return tasks from the database, optionally filtered by search and/or done."""
    return db.list_tasks(search=search, done=done)


@app.get("/stats", summary="Task statistics")
def stats():
    """Return total, done and open task counts, computed in SQL."""
    return db.get_stats()


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int):
    """Return a single task. Returns 404 if not found."""
    row = db.get_task(task_id)
    if row is None:
        raise TaskError(404, f"Task {task_id} not found")
    return row


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(new_task: TaskCreate):
    """Add a task to the database. Title is required and cannot be empty."""
    if new_task.title is None:
        raise TaskError(400, "Field 'title' is required")
    if not new_task.title.strip():
        raise TaskError(400, "Field 'title' cannot be empty")
    return db.create_task(new_task.title.strip())


@app.put("/tasks/{task_id}", summary="Update a task")
def update_task(task_id: int, updated: TaskUpdate):
    """Update a task title and/or done status. Returns 404 if not found."""
    if updated.title is None and updated.done is None:
        raise TaskError(400, "No fields to update")
    row = db.get_task(task_id)
    if row is None:
        raise TaskError(404, f"Task {task_id} not found")
    new_title = updated.title.strip() if updated.title is not None else row["title"]
    if updated.title is not None and not new_title:
        raise TaskError(400, "Title cannot be empty")
    new_done = updated.done if updated.done is not None else row["done"]
    return db.update_task(task_id, new_title, new_done)


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int):
    """Remove a task from the database. Returns 404 if not found."""
    if db.delete_task(task_id) == 0:
        raise TaskError(404, f"Task {task_id} not found")


@app.post("/enrich", summary="Enrich a book record with LLM")
def enrich_book(req: llm.EnrichRequest):
    """Enrich a scraped book record with a category, summary, quality flags, and confidence.

    With LLM_STUB=1 returns a hard-coded stub. Invalid input returns 400.
    """
    stub = os.environ.get("LLM_STUB", "0") == "1"
    if stub:
        return llm.STUB_RESPONSE.model_dump(mode="json")
    try:
        result = llm.enrich_record(req)
    except ValueError as exc:
        if "LLM is disabled" in str(exc):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={"error": "LLM service is disabled", "detail": str(exc)},
            )
        raise TaskError(422, str(exc))
    resp = result["response"]
    return {
        "category": resp.category.value,
        "summary": resp.summary,
        "quality_flags": [f.value for f in resp.quality_flags],
        "confidence": resp.confidence,
    }
