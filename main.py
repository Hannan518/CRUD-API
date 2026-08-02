import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
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
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def init_db():
    """Create the database file and tasks table, seeding 3 tasks if empty."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO tasks (title, done, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [
                ("Buy groceries", 0, now, now),
                ("Walk the dog", 1, now, now),
                ("Read a book", 0, now, now),
            ],
        )
    conn.commit()
    conn.close()


init_db()


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
    db: sqlite3.Connection = Depends(get_db),
):
    """Return tasks from the database, optionally filtered by search and/or done."""
    query = "SELECT * FROM tasks"
    conditions = []
    params = []
    if search is not None:
        conditions.append("title LIKE ?")
        params.append(f"%{search}%")
    if done is not None:
        conditions.append("done = ?")
        params.append(int(done))
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    rows = db.execute(query, params).fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/stats", summary="Task statistics")
def stats(db: sqlite3.Connection = Depends(get_db)):
    """Return total, done and open task counts, computed in SQL."""
    total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    done = db.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
    return {"total": total, "done": done, "open": total - done}


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Return a single task. Returns 404 if not found."""
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskError(404, f"Task {task_id} not found")
    return row_to_task(row)


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(new_task: TaskCreate, db: sqlite3.Connection = Depends(get_db)):
    """Add a task to the database. Title is required and cannot be empty."""
    if new_task.title is None:
        raise TaskError(400, "Field 'title' is required")
    if not new_task.title.strip():
        raise TaskError(400, "Field 'title' cannot be empty")
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        "INSERT INTO tasks (title, done, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (new_task.title.strip(), 0, now, now),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return row_to_task(row)


@app.put("/tasks/{task_id}", summary="Update a task")
def update_task(
    task_id: int, updated: TaskUpdate, db: sqlite3.Connection = Depends(get_db)
):
    """Update a task title and/or done status. Returns 404 if not found."""
    if updated.title is None and updated.done is None:
        raise TaskError(400, "No fields to update")
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskError(404, f"Task {task_id} not found")
    if updated.title is not None:
        if not updated.title.strip():
            raise TaskError(400, "Title cannot be empty")
        new_title = updated.title.strip()
    else:
        new_title = row["title"]
    new_done = bool(updated.done) if updated.done is not None else bool(row["done"])
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE tasks SET title = ?, done = ?, updated_at = ? WHERE id = ?",
        (new_title, int(new_done), now, task_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_task(row)


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Remove a task from the database. Returns 404 if not found."""
    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cursor.rowcount == 0:
        raise TaskError(404, f"Task {task_id} not found")
    db.commit()

