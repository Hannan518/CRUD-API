import db
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A simple CRUD API for managing tasks.",
)


class TaskError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@app.exception_handler(TaskError)
def task_error_handler(request: Request, exc: TaskError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


load_dotenv()
db.init_db()


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.get("/", summary="API info")
def read_root():
    """Return API name, version, and available endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Health check")
def health():
    """Check if the server is running."""
    return {"status": "ok"}


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
