"""Small SQLite connection and schema helpers; intentionally no ORM dependency."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path("/tmp/arena.db") if os.getenv("VERCEL") else Path(os.getenv("ARENA_DB_PATH", str(Path(__file__).resolve().parents[1] / "arena.db")))
DB_MODE = "vercel-ephemeral-sqlite" if os.getenv("VERCEL") else "local-sqlite"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS laptops (
  sku_id TEXT PRIMARY KEY,
  price_inr INTEGER,
  price_kind TEXT NOT NULL,
  availability TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shopper_sessions (
  session_id TEXT PRIMARY KEY,
  handoff_code TEXT NOT NULL UNIQUE,
  state_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  finalized INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON shopper_sessions(updated_at DESC);
CREATE TABLE IF NOT EXISTS mission_runs (
  run_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  mission_id TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_missions_session ON mission_runs(session_id, created_at DESC);
CREATE TABLE IF NOT EXISTS associate_tokens (
  token_hash TEXT PRIMARY KEY,
  store_id TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS associate_claims (
  session_id TEXT PRIMARY KEY REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  store_id TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS associate_checklists (
  session_id TEXT PRIMARY KEY REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  checklist_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS associate_interactions (
  interaction_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  store_id TEXT NOT NULL,
  action TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=8, isolation_level="DEFERRED")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 8000")
    return connection


def init_db() -> None:
    from .catalog import CURATED_LAPTOPS

    with connect() as connection:
        connection.executescript(SCHEMA)
        for laptop in CURATED_LAPTOPS:
            connection.execute(
                "INSERT OR IGNORE INTO laptops (sku_id, price_inr, price_kind, availability, data_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (laptop["sku_id"], laptop.get("price_inr"), laptop["price_kind"], laptop["availability"], json.dumps(laptop, ensure_ascii=False), now_iso()),
            )


def get_db() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
