from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_assets,
    routes_backtests,
    routes_data,
    routes_experiments,
    routes_features,
    routes_layouts,
    routes_signals,
    routes_targets,
    routes_transforms,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Trading Research Dashboard",
        version="0.1.0",
        description="Local-first dashboard API for systematic trading research artifacts.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_assets.router, prefix="/api", tags=["assets"])
    app.include_router(routes_data.router, prefix="/api", tags=["data"])
    app.include_router(routes_features.router, prefix="/api", tags=["features"])
    app.include_router(routes_signals.router, prefix="/api", tags=["signals"])
    app.include_router(routes_targets.router, prefix="/api", tags=["targets"])
    app.include_router(routes_transforms.router, prefix="/api", tags=["transforms"])
    app.include_router(routes_experiments.router, prefix="/api", tags=["experiments"])
    app.include_router(routes_backtests.router, prefix="/api", tags=["backtests"])
    app.include_router(routes_layouts.router, prefix="/api", tags=["layouts"])
    return app


app = create_app()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
