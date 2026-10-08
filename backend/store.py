"""Small persistent store; invalid data is an error rather than an empty dataset."""

import json
import os
import sqlite3
import threading
from pathlib import Path

from sentinel import strict_json_object

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.RLock()


def connect():
    path = Path(os.environ.get("HONEYPOT_DATA_PATH", str(ROOT / "backend/data/application.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("CREATE TABLE IF NOT EXISTS records (bucket TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(bucket,id))")
    return connection


def put(bucket: str, record_id: str, data: dict):
    connection = connect()
    try:
        with connection:
            connection.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (bucket, record_id, json.dumps(data, allow_nan=False)))
    finally:
        connection.close()


def get(bucket: str, record_id: str) -> dict | None:
    connection = connect()
    try:
        row = connection.execute("SELECT data FROM records WHERE bucket=? AND id=?", (bucket, record_id)).fetchone()
        return strict_json_object(row[0]) if row else None
    finally:
        connection.close()


def all_records(bucket: str) -> list[dict]:
    connection = connect()
    try:
        return [strict_json_object(row[0]) for row in connection.execute("SELECT data FROM records WHERE bucket=? ORDER BY id", (bucket,))]
    finally:
        connection.close()
