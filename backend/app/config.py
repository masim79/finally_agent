"""Environment configuration — loads `.env` once and exposes typed settings.

CONTRACTS.md §7 lists OPENROUTER_API_KEY, MASSIVE_API_KEY, LLM_MOCK, and
FINALLY_DB_PATH. Everything except live chat must work with none of them set.
Individual modules (the market factory, the LLM layer, the repository layer)
each read their own env var directly at call time — this module's job is
only to make sure the project-root `.env` has been loaded into the process
environment before anything reads from it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> backend/app -> backend -> repo root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / ".env"

_loaded = False


def load_environment() -> None:
    """Load the project-root `.env` into the environment, if present. Idempotent.

    Variables already set in the environment take precedence (`override=False`)
    so container env vars and test fixtures are never clobbered by a stray
    `.env` file.
    """
    global _loaded
    if _loaded:
        return
    load_dotenv(dotenv_path=_ENV_PATH, override=False)
    _loaded = True


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    massive_api_key: str
    llm_mock: bool
    db_path: str


def get_settings() -> Settings:
    """Snapshot of the current environment. Call `load_environment()` first."""
    return Settings(
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        massive_api_key=os.environ.get("MASSIVE_API_KEY", ""),
        llm_mock=(os.environ.get("LLM_MOCK") or "").strip().lower() == "true",
        db_path=os.environ.get("FINALLY_DB_PATH", "db/finally.db"),
    )
