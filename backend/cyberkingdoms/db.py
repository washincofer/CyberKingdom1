from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = r'''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citizens (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    city_id TEXT NOT NULL,
    hunger INTEGER NOT NULL CHECK (hunger BETWEEN 0 AND 100),
    energy INTEGER NOT NULL CHECK (energy BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS financial_accounts (
    id TEXT PRIMARY KEY,
    citizen_id TEXT REFERENCES citizens(id),
    account_kind TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'Cz',
    balance INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS inventories (
    id TEXT PRIMARY KEY,
    citizen_id TEXT NOT NULL UNIQUE REFERENCES citizens(id)
);

CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_id TEXT NOT NULL REFERENCES inventories(id) ON DELETE CASCADE,
    item_code TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (inventory_id, item_code)
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    citizen_id TEXT NOT NULL REFERENCES citizens(id),
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','COMPLETED','INTERRUPTED')),
    position INTEGER NOT NULL CHECK (position >= 1),
    starts_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_actions_pending ON actions(citizen_id, status, position);
CREATE INDEX IF NOT EXISTS idx_actions_due ON actions(status, due_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_active_position
    ON actions(citizen_id, position)
    WHERE status IN ('QUEUED','RUNNING');

CREATE TABLE IF NOT EXISTS action_settlements (
    action_id TEXT PRIMARY KEY REFERENCES actions(id),
    settled_at TEXT NOT NULL,
    result_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_transactions (
    id TEXT PRIMARY KEY,
    reference_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    posted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL REFERENCES ledger_transactions(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES financial_accounts(id),
    amount INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_txn ON ledger_entries(transaction_id);

CREATE TABLE IF NOT EXISTS market_listings (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    price_cz INTEGER NOT NULL CHECK (price_cz >= 0),
    available_qty INTEGER NOT NULL CHECK (available_qty >= 0),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','CLOSED'))
);

CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL REFERENCES market_listings(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_cz INTEGER NOT NULL CHECK (total_cz >= 0),
    item_code TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    body_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL,
    aggregate_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS demo_params (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
'''

SEED_SQL = r'''
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO accounts(id, display_name) VALUES ('acc-player', 'Prototype Player');
INSERT OR IGNORE INTO citizens(id, account_id, city_id, hunger, energy)
VALUES ('cit-player', 'acc-player', 'city-alpha', 45, 100);
INSERT OR IGNORE INTO financial_accounts(id, citizen_id, account_kind, currency, balance)
VALUES ('fa-player', 'cit-player', 'PLAYER', 'Cz', 0);
INSERT OR IGNORE INTO financial_accounts(id, citizen_id, account_kind, currency, balance)
VALUES ('fa-treasury', NULL, 'TREASURY', 'Cz', 1000000);
INSERT OR IGNORE INTO financial_accounts(id, citizen_id, account_kind, currency, balance)
VALUES ('fa-market-sink', NULL, 'MARKET_SINK', 'Cz', 0);
INSERT OR IGNORE INTO inventories(id, citizen_id) VALUES ('inv-player', 'cit-player');
INSERT OR IGNORE INTO market_listings(id, city_id, item_code, price_cz, available_qty, status)
VALUES ('lst-ration-basic', 'city-alpha', 'RATION_BASIC', 20, 50, 'ACTIVE');
INSERT OR IGNORE INTO demo_params(key, value) VALUES ('public_work_reward_cz', 50);
INSERT OR IGNORE INTO demo_params(key, value) VALUES ('public_work_energy_cost', 10);
INSERT OR IGNORE INTO demo_params(key, value) VALUES ('ration_hunger_gain', 25);
'''


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.executescript(SEED_SQL)
        finally:
            conn.close()

    def reset(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            p = Path(self.path + suffix)
            if p.exists():
                p.unlink()
        self.initialize()

    @contextmanager
    def transaction(self, immediate: bool = False, retries: int = 8):
        conn = self.connect()
        delay = 0.025
        try:
            for attempt in range(retries):
                try:
                    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == retries - 1:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, 0.5)
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    @staticmethod
    def one(conn: sqlite3.Connection, sql: str, params=()):
        return conn.execute(sql, params).fetchone()

    @staticmethod
    def all(conn: sqlite3.Connection, sql: str, params=()):
        return conn.execute(sql, params).fetchall()

    @staticmethod
    def json(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
