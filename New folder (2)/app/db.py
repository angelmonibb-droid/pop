import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import current_app, g
from werkzeug.security import generate_password_hash


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    wins INTEGER NOT NULL DEFAULT 0 CHECK (wins >= 0),
    losses INTEGER NOT NULL DEFAULT 0 CHECK (losses >= 0),
    best_win INTEGER NOT NULL DEFAULT 0 CHECK (best_win >= 0),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    difficulty INTEGER NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 6),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stake INTEGER NOT NULL CHECK (stake > 0),
    current_row INTEGER NOT NULL DEFAULT 0 CHECK (current_row BETWEEN 0 AND 5),
    board_json TEXT NOT NULL,
    revealed_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'won', 'lost', 'withdrawn', 'abandoned')),
    payout INTEGER NOT NULL DEFAULT 0 CHECK (payout >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_round_per_user
ON game_rounds(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS balance_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    round_id INTEGER REFERENCES game_rounds(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('seed', 'stake', 'payout', 'admin_adjustment')),
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ledger_user_created ON balance_ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS rounds_user_created ON game_rounds(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_created ON audit_log(created_at DESC);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_database(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_database(current_app.config["DATABASE"])
    return g.db


def close_db(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    seed_admin(db)


def seed_admin(db: sqlite3.Connection) -> None:
    username = current_app.config["ADMIN_USERNAME"].strip()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        return
    now = utc_now()
    balance = max(0, current_app.config["ADMIN_INITIAL_BALANCE"])
    with transaction(db):
        cursor = db.execute(
            """INSERT INTO users
               (username, password_hash, balance, is_admin, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (username, generate_password_hash(current_app.config["ADMIN_PASSWORD"]), balance, now, now),
        )
        user_id = cursor.lastrowid
        db.execute(
            """INSERT INTO balance_ledger
               (user_id, kind, amount, balance_after, note, created_at)
               VALUES (?, 'seed', ?, ?, 'initial admin balance', ?)""",
            (user_id, balance, balance, now),
        )


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

