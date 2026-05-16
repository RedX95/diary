import os
import sqlite3

_DB_PATH: str | None = None


def _ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          user_id TEXT,
          text TEXT NOT NULL,
          address TEXT,
          phone TEXT,
          lat REAL,
          lon REAL,
          map_url TEXT,
          time TEXT NOT NULL,
          date TEXT NOT NULL,
          completed INTEGER NOT NULL DEFAULT 0,
          deleted INTEGER NOT NULL DEFAULT 0,
          dirty INTEGER NOT NULL DEFAULT 1,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )

    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN user_id TEXT")
    if "address" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN address TEXT")
    if "phone" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN phone TEXT")
    if "lat" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN lat REAL")
    if "lon" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN lon REAL")
    if "map_url" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN map_url TEXT")
    if "deleted" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")
    if "dirty" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN dirty INTEGER NOT NULL DEFAULT 1")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_updated ON tasks(user_id, updated_at)"
    )


def init_storage(db_path: str):
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
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
            "SELECT id, user_id, text, address, phone, lat, lon, map_url, time, date, completed, deleted, dirty, created_at, updated_at FROM tasks"
        ).fetchall()
        tasks = []
        for r in rows:
            tasks.append(
                {
                    "id": r["id"],
                    "userId": r["user_id"],
                    "text": r["text"],
                    "address": r["address"],
                    "phone": r["phone"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "mapUrl": r["map_url"],
                    "time": r["time"],
                    "date": r["date"],
                    "completed": bool(r["completed"]),
                    "deleted": bool(r["deleted"]),
                    "dirty": bool(r["dirty"]),
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
                INSERT INTO tasks (id, user_id, text, address, phone, lat, lon, map_url, time, date, completed, deleted, dirty, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  user_id=excluded.user_id,
                  text=excluded.text,
                  address=excluded.address,
                  phone=excluded.phone,
                  lat=excluded.lat,
                  lon=excluded.lon,
                  map_url=excluded.map_url,
                  time=excluded.time,
                  date=excluded.date,
                  completed=excluded.completed,
                  deleted=excluded.deleted,
                  dirty=excluded.dirty,
                  updated_at=excluded.updated_at
                """,
                (
                    t["id"],
                    t.get("userId"),
                    t["text"],
                    t.get("address"),
                    t.get("phone"),
                    t.get("lat"),
                    t.get("lon"),
                    t.get("mapUrl"),
                    t["time"],
                    t["date"],
                    1 if t.get("completed") else 0,
                    1 if t.get("deleted") else 0,
                    1 if t.get("dirty", True) else 0,
                    created_at,
                    updated_at,
                ),
            )
        conn.commit()


def set_tasks_dirty(task_ids: list[str], dirty: bool):
    if not task_ids:
        return
    db_path = _require_db()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"UPDATE tasks SET dirty = ? WHERE id IN ({','.join(['?'] * len(task_ids))})",
            [1 if dirty else 0, *task_ids],
        )
        conn.commit()
