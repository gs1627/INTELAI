"""Database adapter: SQLite locally/tests and PostgreSQL when DATABASE_URL is set."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = Path("/tmp/arena.db") if os.getenv("VERCEL") else Path(os.getenv("ARENA_DB_PATH", str(Path(__file__).resolve().parents[1] / "arena.db")))
DB_MODE = "postgresql" if DATABASE_URL else "vercel-ephemeral-sqlite" if os.getenv("VERCEL") else "local-sqlite"
DB_PERSISTENT = bool(DATABASE_URL) or not bool(os.getenv("VERCEL"))

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS laptops (
  sku_id TEXT PRIMARY KEY, price_inr INTEGER, price_kind TEXT NOT NULL,
  availability TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shopper_sessions (
  session_id TEXT PRIMARY KEY, handoff_code TEXT NOT NULL UNIQUE, state_json TEXT NOT NULL,
  handoff_token_hash TEXT UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  finalized INTEGER NOT NULL DEFAULT 0, handoff_expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON shopper_sessions(updated_at DESC);
CREATE TABLE IF NOT EXISTS mission_runs (
  run_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  mission_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_missions_session ON mission_runs(session_id, created_at DESC);
CREATE TABLE IF NOT EXISTS associate_tokens (
  token_hash TEXT PRIMARY KEY, store_id TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS associate_claims (
  session_id TEXT PRIMARY KEY REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  store_id TEXT NOT NULL, token_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_store ON associate_claims(store_id, created_at DESC);
CREATE TABLE IF NOT EXISTS associate_checklists (
  session_id TEXT PRIMARY KEY REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  checklist_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS associate_interactions (
  interaction_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES shopper_sessions(session_id) ON DELETE CASCADE,
  store_id TEXT NOT NULL, action TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_store ON associate_interactions(store_id, action);
CREATE TABLE IF NOT EXISTS lookup_attempts (key_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_lookup_attempts ON lookup_attempts(key_hash, created_at);
CREATE TABLE IF NOT EXISTS lookup_rate_windows (
  key_hash TEXT NOT NULL, window_bucket TEXT NOT NULL, attempts INTEGER NOT NULL,
  PRIMARY KEY(key_hash, window_bucket)
);
CREATE TABLE IF NOT EXISTS benchmark_definitions (
  test_id TEXT PRIMARY KEY, round_id TEXT NOT NULL, benchmark_version TEXT NOT NULL,
  task_definition TEXT NOT NULL, model_id TEXT, model_hash TEXT, prompt_hash TEXT, input_hash TEXT,
  metric_name TEXT NOT NULL, metric_unit TEXT NOT NULL, lower_is_better INTEGER NOT NULL,
  created_at TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS benchmark_sessions (
  benchmark_session_id TEXT PRIMARY KEY, sku_id TEXT NOT NULL REFERENCES laptops(sku_id),
  test_date TEXT NOT NULL, device_name TEXT, os_version TEXT, runtime_version TEXT,
  power_mode TEXT, ac_power INTEGER, bios_version TEXT, driver_version TEXT,
  environment_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS benchmark_results (
  result_id TEXT PRIMARY KEY, benchmark_session_id TEXT NOT NULL REFERENCES benchmark_sessions(benchmark_session_id) ON DELETE CASCADE,
  test_id TEXT NOT NULL REFERENCES benchmark_definitions(test_id), run_index INTEGER NOT NULL,
  metric_value REAL NOT NULL, result_status TEXT NOT NULL, execution_provider TEXT NOT NULL,
  model_hash TEXT NOT NULL, input_hash TEXT NOT NULL, prompt_hash TEXT NOT NULL,
  runtime_version TEXT NOT NULL, verification_status TEXT NOT NULL,
  evidence_json TEXT NOT NULL, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_benchmark_results ON benchmark_results(test_id, benchmark_session_id, verification_status);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class DatabaseConnection:
    """Small DB-API facade for the qmark SQL used by the existing API."""
    def __init__(self, connection: Any, postgres: bool = False):
        self.connection = connection
        self.postgres = postgres

    def _sql(self, sql: str) -> str:
        if not self.postgres:
            return sql
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: Any = ()):
        return self.connection.execute(self._sql(sql), params)

    def executescript(self, script: str) -> None:
        statements = [s.strip() for s in script.split(";") if s.strip() and not s.strip().upper().startswith("PRAGMA")]
        for statement in statements:
            self.execute(statement)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.connection.rollback()
        else:
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def connect() -> DatabaseConnection:
    if DATABASE_URL:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL requires psycopg 3; install backend requirements") from exc

        class HybridRow(dict):
            def __getitem__(self, key):
                if isinstance(key, int):
                    return tuple(self.values())[key]
                return super().__getitem__(key)

        def hybrid_row(cursor):
            names = [column.name for column in cursor.description]
            return lambda values: HybridRow(zip(names, values))

        database_url = "postgresql://" + DATABASE_URL[len("postgres://"):] if DATABASE_URL.startswith("postgres://") else DATABASE_URL
        connection = psycopg.connect(database_url, row_factory=hybrid_row, connect_timeout=8)
        return DatabaseConnection(connection, postgres=True)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=8, isolation_level="DEFERRED")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 8000")
    return DatabaseConnection(connection)


def _has_handoff_expiry(connection: DatabaseConnection) -> bool:
    if connection.postgres:
        row = connection.execute("SELECT 1 FROM information_schema.columns WHERE table_name='shopper_sessions' AND column_name='handoff_expires_at'").fetchone()
        return row is not None
    return any(row["name"] == "handoff_expires_at" for row in connection.execute("PRAGMA table_info(shopper_sessions)").fetchall())


def _columns(connection: DatabaseConnection, table: str = "shopper_sessions") -> set[str]:
    if not table.replace("_", "").isalnum():
        raise ValueError("Invalid table name")
    if connection.postgres:
        return {row["column_name"] for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_name=?", (table,)).fetchall()}
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db() -> None:
    from .catalog import CURATED_LAPTOPS

    with connect() as connection:
        connection.executescript(SCHEMA)
        columns = _columns(connection)
        if "handoff_expires_at" not in columns:
            connection.execute("ALTER TABLE shopper_sessions ADD COLUMN handoff_expires_at TEXT")
        if "handoff_token_hash" not in columns:
            connection.execute("ALTER TABLE shopper_sessions ADD COLUMN handoff_token_hash TEXT")
            old_rows = connection.execute("SELECT session_id, handoff_code, state_json FROM shopper_sessions").fetchall()
            import hashlib
            for old in old_rows:
                old_state = json.loads(old["state_json"] or "{}")
                prior = old_state.get("handoff") or {}
                legacy_code = prior.get("handoff_code") or old["handoff_code"]
                if legacy_code and not str(legacy_code).startswith("retired-"):
                    connection.execute("UPDATE shopper_sessions SET handoff_token_hash = ? WHERE session_id = ?", (hashlib.sha256(str(legacy_code).encode()).hexdigest(), old["session_id"]))
                if "handoff_code" in prior:
                    prior.pop("handoff_code", None)
                    old_state["handoff"] = prior
                    connection.execute("UPDATE shopper_sessions SET state_json = ? WHERE session_id = ?", (json.dumps(old_state, ensure_ascii=False), old["session_id"]))
                if not str(old["handoff_code"]).startswith("retired-"):
                    connection.execute("UPDATE shopper_sessions SET handoff_code = ? WHERE session_id = ?", (f"retired-{old['session_id']}", old["session_id"]))
        benchmark_columns = _columns(connection, "benchmark_definitions")
        if "input_hash" not in benchmark_columns:
            connection.execute("ALTER TABLE benchmark_definitions ADD COLUMN input_hash TEXT")
        insert_sql = (
            "INSERT INTO laptops (sku_id, price_inr, price_kind, availability, data_json, created_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(sku_id) DO NOTHING"
        )
        for laptop in CURATED_LAPTOPS:
            connection.execute(insert_sql, (laptop["sku_id"], laptop.get("price_inr"), laptop["price_kind"], laptop["availability"], json.dumps(laptop, ensure_ascii=False), now_iso()))
        definitions = [
            ("CPU_MULTITASKING_V1", "CPU_MULTITASKING", "Fixed synthetic foreground productivity checklist", None, None, None, "completion_time_ms", "ms", 1),
            ("NPU_AI_RELAY_V1", "NPU_AI_RELAY", "NOVA synthetic lecture summary with fixed prompt and local model", "arena-nova-local-llm", None, None, "inference_time_ms", "ms", 1),
            ("GPU_VISUALS_V1", "GPU_VISUALS", "Controlled graphics scene; not yet implemented", None, None, None, "frame_rate_fps", "fps", 0),
            ("FOREGROUND_PRODUCTIVITY_V1", "FOREGROUND_PRODUCTIVITY", "Browser checklist completion time; not a hardware benchmark", None, None, None, "completion_time_ms", "ms", 1),
            ("OVERALL_MISSION_V1", "OVERALL_MISSION", "NOVA task completion and output validation", "arena-nova-local-llm", None, None, "completion_time_ms", "ms", 1),
        ]
        for test_id, round_id, task, model_id, model_hash, prompt_hash, metric, unit, lower in definitions:
            connection.execute(
                "INSERT INTO benchmark_definitions (test_id, round_id, benchmark_version, task_definition, model_id, model_hash, prompt_hash, input_hash, metric_name, metric_unit, lower_is_better, created_at, approved) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(test_id) DO NOTHING",
                (test_id, round_id, "1.0", task, model_id, model_hash, prompt_hash, None, metric, unit, lower, now_iso(), 0),
            )


def get_db() -> Iterator[DatabaseConnection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
