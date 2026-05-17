from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.core.paths import DashboardPaths, get_paths


@dataclass(frozen=True)
class Settings:
    paths: DashboardPaths = field(default_factory=get_paths)
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

