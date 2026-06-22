from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
import uuid

import pandas as pd

from .config import DB_PATH, DEMO_USERS, ensure_directories, get_access_db_path, get_db_backend
from .security import hash_password


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    display_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL UNIQUE,
    machine_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    temperature REAL NOT NULL,
    vibration REAL NOT NULL,
    pressure REAL NOT NULL,
    load_pct REAL NOT NULL,
    efficiency REAL NOT NULL,
    anomaly_score REAL NOT NULL,
    risk_level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL,
    maintenance_date TEXT NOT NULL,
    maintenance_type TEXT NOT NULL,
    notes TEXT NOT NULL,
    next_due TEXT NOT NULL,
    technician TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    accuracy REAL NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SQLiteStorage:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        ensure_directories()
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQLITE)
        self.seed_default_users()

    def seed_default_users(self) -> None:
        with self.connect() as connection:
            for user in DEMO_USERS:
                existing = connection.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (user["username"],),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO users (username, password_hash, role, display_name, active, created_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (
                            user["username"],
                            hash_password(user["password"]),
                            user["role"],
                            user["display_name"],
                            datetime.utcnow().isoformat(timespec="seconds"),
                        ),
                    )

    def log_action(self, actor: str, action: str, details: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_logs (actor, action, details, created_at) VALUES (?, ?, ?, ?)",
                (actor, action, details, datetime.utcnow().isoformat(timespec="seconds")),
            )

    def fetch_user(self, username: str):
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ? AND active = 1",
                (username,),
            ).fetchone()

    def list_users(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT id, username, role, display_name, active, created_at FROM users ORDER BY id",
                connection,
            )

    def upsert_user(self, username: str, password: str, role: str, display_name: str, active: int = 1) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role, display_name, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        hash_password(password),
                        role,
                        display_name,
                        active,
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, role = ?, display_name = ?, active = ?
                    WHERE username = ?
                    """,
                    (hash_password(password), role, display_name, active, username),
                )

    def list_machines(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM machines ORDER BY created_at DESC",
                connection,
            )

    def create_machine(self, machine_name: str, model_name: str, location: str, status: str) -> str:
        machine_uid = f"MCH-{uuid.uuid4().hex[:10].upper()}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO machines (machine_uid, machine_name, model_name, location, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    machine_uid,
                    machine_name,
                    model_name,
                    location,
                    status,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
        return machine_uid

    def upsert_machine(self, machine_uid: str, machine_name: str, model_name: str, location: str, status: str) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM machines WHERE machine_uid = ?",
                (machine_uid,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO machines (machine_uid, machine_name, model_name, location, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        machine_uid,
                        machine_name,
                        model_name,
                        location,
                        status,
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE machines
                    SET machine_name = ?, model_name = ?, location = ?, status = ?
                    WHERE machine_uid = ?
                    """,
                    (machine_name, model_name, location, status, machine_uid),
                )

    def add_telemetry_rows(self, telemetry_rows: list[dict]) -> None:
        if not telemetry_rows:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO telemetry (
                    machine_uid, captured_at, temperature, vibration, pressure,
                    load_pct, efficiency, anomaly_score, risk_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["machine_uid"],
                        row["captured_at"],
                        row["temperature"],
                        row["vibration"],
                        row["pressure"],
                        row["load_pct"],
                        row["efficiency"],
                        row["anomaly_score"],
                        row["risk_level"],
                    )
                    for row in telemetry_rows
                ],
            )

    def list_telemetry(self, limit: int = 500) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM telemetry ORDER BY captured_at DESC LIMIT ?",
                connection,
                params=(limit,),
            )

    def add_maintenance_log(
        self,
        machine_uid: str,
        maintenance_date: str,
        maintenance_type: str,
        notes: str,
        next_due: str,
        technician: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO maintenance_logs (
                    machine_uid, maintenance_date, maintenance_type, notes,
                    next_due, technician, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    machine_uid,
                    maintenance_date,
                    maintenance_type,
                    notes,
                    next_due,
                    technician,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )

    def list_maintenance(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM maintenance_logs ORDER BY maintenance_date DESC",
                connection,
            )

    def list_model_versions(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM model_versions ORDER BY created_at DESC",
                connection,
            )

    def save_model_version(self, version_label: str, algorithm_name: str, accuracy: float, notes: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_versions (version_label, algorithm_name, accuracy, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version_label,
                    algorithm_name,
                    accuracy,
                    notes,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )

    def list_audit_logs(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 200",
                connection,
            )


class AccessStorage(SQLiteStorage):
    """Compatibility placeholder for a future Access-backed deployment."""


def get_storage() -> SQLiteStorage:
    backend = get_db_backend()
    if backend == "access":
        return AccessStorage(get_access_db_path())
    return SQLiteStorage(DB_PATH)
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import sqlite3
import uuid
from pathlib import Path

import pandas as pd

from .config import DB_PATH, DEMO_USERS, ensure_directories, get_access_db_path, get_db_backend
from .security import hash_password


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    display_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL UNIQUE,
    machine_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    temperature REAL NOT NULL,
    vibration REAL NOT NULL,
    pressure REAL NOT NULL,
    load_pct REAL NOT NULL,
    efficiency REAL NOT NULL,
    anomaly_score REAL NOT NULL,
    risk_level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_uid TEXT NOT NULL,
    maintenance_date TEXT NOT NULL,
    maintenance_type TEXT NOT NULL,
    notes TEXT NOT NULL,
    next_due TEXT NOT NULL,
    technician TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    accuracy REAL NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SQLiteStorage:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        ensure_directories()
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQLITE)
        self.seed_default_users()

    def seed_default_users(self) -> None:
        with self.connect() as connection:
            for user in DEMO_USERS:
                existing = connection.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (user["username"],),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO users (username, password_hash, role, display_name, active, created_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (
                            user["username"],
                            hash_password(user["password"]),
                            user["role"],
                            user["display_name"],
                            datetime.utcnow().isoformat(timespec="seconds"),
                        ),
                    )

    def log_action(self, actor: str, action: str, details: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_logs (actor, action, details, created_at) VALUES (?, ?, ?, ?)",
                (actor, action, details, datetime.utcnow().isoformat(timespec="seconds")),
            )

    def fetch_user(self, username: str):
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ? AND active = 1",
                (username,),
            ).fetchone()

    def list_users(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT id, username, role, display_name, active, created_at FROM users ORDER BY id",
                connection,
            )

    def upsert_user(self, username: str, password: str, role: str, display_name: str, active: int = 1) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role, display_name, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        hash_password(password),
                        role,
                        display_name,
                        active,
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, role = ?, display_name = ?, active = ?
                    WHERE username = ?
                    """,
                    (hash_password(password), role, display_name, active, username),
                )

    def list_machines(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM machines ORDER BY created_at DESC",
                connection,
            )

    def create_machine(self, machine_name: str, model_name: str, location: str, status: str) -> str:
        machine_uid = f"MCH-{uuid.uuid4().hex[:10].upper()}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO machines (machine_uid, machine_name, model_name, location, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    machine_uid,
                    machine_name,
                    model_name,
                    location,
                    status,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
        return machine_uid

    def get_machine(self, machine_uid: str):
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM machines WHERE machine_uid = ?",
                (machine_uid,),
            ).fetchone()

    def upsert_machine(self, machine_uid: str, machine_name: str, model_name: str, location: str, status: str) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM machines WHERE machine_uid = ?", (machine_uid,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO machines (machine_uid, machine_name, model_name, location, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        machine_uid,
                        machine_name,
                        model_name,
                        location,
                        status,
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE machines
                    SET machine_name = ?, model_name = ?, location = ?, status = ?
                    WHERE machine_uid = ?
                    """,
                    (machine_name, model_name, location, status, machine_uid),
                )

    def add_telemetry_rows(self, telemetry_rows: list[dict]) -> None:
        if not telemetry_rows:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO telemetry (
                    machine_uid, captured_at, temperature, vibration, pressure,
                    load_pct, efficiency, anomaly_score, risk_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["machine_uid"],
                        row["captured_at"],
                        row["temperature"],
                        row["vibration"],
                        row["pressure"],
                        row["load_pct"],
                        row["efficiency"],
                        row["anomaly_score"],
                        row["risk_level"],
                    )
                    for row in telemetry_rows
                ],
            )

    def list_telemetry(self, limit: int = 500) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM telemetry ORDER BY captured_at DESC LIMIT ?",
                connection,
                params=(limit,),
            )

    def add_maintenance_log(
        self,
        machine_uid: str,
        maintenance_date: str,
        maintenance_type: str,
        notes: str,
        next_due: str,
        technician: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO maintenance_logs (
                    machine_uid, maintenance_date, maintenance_type, notes,
                    next_due, technician, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    machine_uid,
                    maintenance_date,
                    maintenance_type,
                    notes,
                    next_due,
                    technician,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )

    def list_maintenance(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM maintenance_logs ORDER BY maintenance_date DESC",
                connection,
            )

    def list_model_versions(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM model_versions ORDER BY created_at DESC",
                connection,
            )

    def save_model_version(self, version_label: str, algorithm_name: str, accuracy: float, notes: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_versions (version_label, algorithm_name, accuracy, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version_label,
                    algorithm_name,
                    accuracy,
                    notes,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )

    def list_audit_logs(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 200",
                connection,
            )


class AccessStorage(SQLiteStorage):
    """Compatibility placeholder for a future Access-backed deployment.

    The Streamlit test build uses SQLite so it can run anywhere. When you move to
    a Windows desktop or intranet deployment, set APP_DB_BACKEND=access and point
    APP_ACCESS_DB_PATH at the .accdb file.
    """


def get_storage() -> SQLiteStorage:
    backend = get_db_backend()
    if backend == "access":
        return AccessStorage(get_access_db_path())
    return SQLiteStorage(DB_PATH)
