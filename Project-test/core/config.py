from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "machine_insight.sqlite3"

APP_TITLE = "Machine Insight MML Studio"
APP_SUBTITLE = "Machine analysis, maintenance, reports, and AI assistance"

DEMO_USERS = (
    {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
        "display_name": "System Admin",
    },
    {
        "username": "user",
        "password": "user123",
        "role": "user",
        "display_name": "Standard User",
    },
)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)


def get_db_backend() -> str:
    return os.getenv("APP_DB_BACKEND", "sqlite").strip().lower()


def get_access_db_path() -> str:
    return os.getenv("APP_ACCESS_DB_PATH", str(DATA_DIR / "machine_insight.accdb"))
from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
MODELS_DIR = DATA_DIR / "models"
DB_PATH = DATA_DIR / "machine_insight.sqlite3"

APP_TITLE = "Machine Insight MML Studio"
APP_SUBTITLE = "Machine analysis, maintenance, reports, and AI help"

DEMO_USERS = (
    {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
        "display_name": "System Admin",
    },
    {
        "username": "user",
        "password": "user123",
        "role": "user",
        "display_name": "Standard User",
    },
)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def get_db_backend() -> str:
    return os.getenv("APP_DB_BACKEND", "sqlite").strip().lower()


def get_access_db_path() -> str:
    return os.getenv("APP_ACCESS_DB_PATH", str(DATA_DIR / "machine_insight.accdb"))
