import os
import sqlite3

_DB_PATH: str | None = None


def init_storage(db_path: str):
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              text TEXT NOT NULL,
              time TEXT NOT NULL,
              date TEXT NOT NULL,
              completed INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _require_db():
    if not _DB_PATH:
        raise RuntimeError("Storage is not initialized. Call init_storage(db_path) first.")
    return _DB_PATH


def load_tasks():
    db_path = _require_db()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, text, time, date, completed, created_at, updated_at FROM tasks"
        ).fetchall()
        tasks = []
        for r in rows:
            tasks.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "time": r["time"],
                    "date": r["date"],
                    "completed": bool(r["completed"]),
                    "createdAt": r["created_at"],
                    "updatedAt": r["updated_at"],
                }
            )
        return tasks


def save_tasks(tasks):
    db_path = _require_db()
    now_ms = int(__import__("time").time() * 1000)
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")
        for t in tasks:
            created_at = int(t.get("createdAt") or now_ms)
            updated_at = int(t.get("updatedAt") or now_ms)
            conn.execute(
                """
                INSERT INTO tasks (id, text, time, date, completed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  text=excluded.text,
                  time=excluded.time,
                  date=excluded.date,
                  completed=excluded.completed,
                  updated_at=excluded.updated_at
                """,
                (
                    t["id"],
                    t["text"],
                    t["time"],
                    t["date"],
                    1 if t.get("completed") else 0,
                    created_at,
                    updated_at,
                ),
            )
        conn.commit()
