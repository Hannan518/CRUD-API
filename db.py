import os

import psycopg
from psycopg.rows import dict_row

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None


def get_conn():
    """Open a connection to Postgres using the DATABASE_URL environment variable."""
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True)


def init_db():
    """Create the tasks table and its index, seeding 3 example tasks if empty."""
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id serial PRIMARY KEY,
            title text NOT NULL,
            done boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()["count"]
    if count == 0:
        conn.execute(
            """
            INSERT INTO tasks (title, done)
            VALUES
                ('Buy groceries', false),
                ('Walk the dog', true),
                ('Read a book', false)
            """
        )
    conn.close()


def list_tasks(search=None, done=None):
    """Return tasks, optionally filtered by title search and/or done status."""
    query = "SELECT * FROM tasks"
    conditions = []
    params = []
    if search is not None:
        conditions.append("title LIKE %s")
        params.append(f"%{search}%")
    if done is not None:
        conditions.append("done = %s")
        params.append(done)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    conn = get_conn()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_task(task_id):
    """Return a single task by id, or None if it does not exist."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    conn.close()
    return row


def get_stats():
    """Return total, done and open task counts, computed in SQL."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()["count"]
    done = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = true").fetchone()["count"]
    conn.close()
    return {"total": total, "done": done, "open": total - done}


def create_task(title):
    """Insert a new task and return the stored row."""
    conn = get_conn()
    row = conn.execute(
        "INSERT INTO tasks (title) VALUES (%s) RETURNING *",
        (title,),
    ).fetchone()
    conn.close()
    return row


def update_task(task_id, title, done):
    """Update a task's title and/or done status, refreshing updated_at."""
    conn = get_conn()
    row = conn.execute(
        "UPDATE tasks SET title = %s, done = %s, updated_at = now() WHERE id = %s RETURNING *",
        (title, done, task_id),
    ).fetchone()
    conn.close()
    return row


def delete_task(task_id):
    """Delete a task by id and return the number of deleted rows."""
    conn = get_conn()
    cursor = conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    deleted = cursor.rowcount
    conn.close()
    return deleted


def ping():
    """Check the database is reachable with a trivial SELECT 1."""
    conn = get_conn()
    conn.execute("SELECT 1").fetchone()
    conn.close()


def ping_redis():
    """Check Redis is reachable, returning True/False without raising."""
    if redis_lib is None:
        return False
    try:
        client = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        )
        return bool(client.ping())
    except Exception:
        return False
