"""SQLite storage layer: user accounts + persistent chat memory.

Uses plain `sqlite3` (no native extensions) so it works on any Python build,
including the default macOS Python which doesn't support
`enable_load_extension` (required by extensions like sqlite-vec). Semantic
vector recall is instead done in Python (see backend/memory.py) by storing
each message's embedding as a BLOB and comparing with cosine similarity -
plenty fast at this app's scale.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "school_friend_ai.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
"""


def get_connection() -> sqlite3.Connection:
    """Open a new connection to the SQLite DB. SQLite handles multiple
    short-lived connections fine (WAL mode), which keeps this safe to call
    per-request from FastAPI's threadpool without sharing connections
    across threads.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
