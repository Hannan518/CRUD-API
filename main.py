import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DB_PATH = "tasks.db"

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


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_task(row):
    """Convert a database row into the API's JSON shape."""
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


def init_db():
    """Create the database file and tasks table, seeding 3 tasks if empty."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            [
                ("Buy groceries", 0),
                ("Walk the dog", 1),
                ("Read a book", 0),
            ],
        )
    conn.commit()
    conn.close()


init_db()

tasks = [
    {"id": 1, "title": "Buy groceries", "done": False},
    {"id": 2, "title": "Walk the dog", "done": True},
    {"id": 3, "title": "Read a book", "done": False},
]

next_id = 4


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
def list_tasks(db: sqlite3.Connection = Depends(get_db)):
    """Return every task from the database."""
    rows = db.execute("SELECT * FROM tasks").fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Return a single task. Returns 404 if not found."""
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskError(404, f"Task {task_id} not found")
    return row_to_task(row)


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(new_task: TaskCreate):
    """Add a task to the list. Title is required and cannot be empty."""
    if new_task.title is None:
        raise HTTPException(status_code=400, detail="Field 'title' is required")
    if not new_task.title.strip():
        raise HTTPException(status_code=400, detail="Field 'title' cannot be empty")
    global next_id
    task = {"id": next_id, "title": new_task.title.strip(), "done": False}
    tasks.append(task)
    next_id += 1
    return task


@app.put("/tasks/{task_id}", summary="Update a task")
def update_task(task_id: int, updated: TaskUpdate):
    """Update a task title and/or done status. Returns 404 if not found."""
    if updated.title is None and updated.done is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    for task in tasks:
        if task["id"] == task_id:
            if updated.title is not None:
                if not updated.title.strip():
                    raise HTTPException(status_code=400, detail="Title cannot be empty")
                task["title"] = updated.title.strip()
            if updated.done is not None:
                task["done"] = updated.done
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int):
    """Remove a task from the list. Returns 404 if not found."""
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

