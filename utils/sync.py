from __future__ import annotations

import os
from typing import Any

from supabase import Client

from utils.storage import load_tasks, save_tasks, set_tasks_dirty
from utils.supabase_service import get_supabase_client


def _table() -> str:
    return os.getenv("SUPABASE_TASKS_TABLE", "tasks")


def sync_once(access_token: str, user_id: str):
    """Базовый sync: push локальных dirty задач, потом pull всех задач пользователя.

    LWW: при pull сравниваем updatedAt/updated_at для всех задач и применяем данные из облака, если они новее.
    """

    client: Client = get_supabase_client(access_token=access_token)

    local = load_tasks()

    for t in local:
        if not t.get("userId"):
            t["userId"] = user_id

    dirty = [t for t in local if t.get("dirty") and t.get("userId") == user_id]

    if dirty:
        payload: list[dict[str, Any]] = []
        for t in dirty:
            payload.append(
                {
                    "id": t["id"],
                    "user_id": user_id,
                    "text": t["text"],
                    "address": t.get("address"),
                    "lat": t.get("lat"),
                    "lon": t.get("lon"),
                    "map_url": t.get("mapUrl"),
                    "time": t["time"],
                    "date": t["date"],
                    "completed": bool(t.get("completed")),
                    "deleted": bool(t.get("deleted")),
                    "created_at": int(t.get("createdAt") or 0),
                    "updated_at": int(t.get("updatedAt") or 0),
                }
            )

        client.table(_table()).upsert(payload, on_conflict="id").execute()

        set_tasks_dirty([t["id"] for t in dirty], dirty=False)
        for t in local:
            if t.get("dirty") and t.get("userId") == user_id:
                t["dirty"] = False

    remote = (
        client.table(_table())
        .select("id,user_id,text,address,lat,lon,map_url,time,date,completed,deleted,created_at,updated_at")
        .eq("user_id", user_id)
        .execute()
    )

    remote_rows = remote.data or []

    by_id: dict[str, dict[str, Any]] = {t["id"]: t for t in local}
    for r in remote_rows:
        existing = by_id.get(r["id"])
        if existing and int(existing.get("updatedAt") or 0) > int(r.get("updated_at") or 0):
            # локальная версия новее — оставляем локальную (LWW)
            continue

        by_id[r["id"]] = {
            "id": r["id"],
            "userId": r.get("user_id"),
            "text": r.get("text") or "",
            "address": r.get("address"),
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "mapUrl": r.get("map_url"),
            "time": r.get("time") or "",
            "date": r.get("date") or "",
            "completed": bool(r.get("completed")),
            "deleted": bool(r.get("deleted")),
            "dirty": False,
            "createdAt": int(r.get("created_at") or 0),
            "updatedAt": int(r.get("updated_at") or 0),
        }

    merged = list(by_id.values())
    save_tasks(merged)

    return merged
