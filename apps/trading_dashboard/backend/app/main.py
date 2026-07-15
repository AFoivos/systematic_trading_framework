from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import (
    routes_assets,
    routes_backtests,
    routes_data,
    routes_execution,
    routes_experiments,
    routes_features,
    routes_layouts,
    routes_predictions,
    routes_signals,
    routes_targets,
    routes_transforms,
)
from app.core.config import get_settings


FRONTEND_INDEX_HEADERS = {"Cache-Control": "no-cache"}


def _frontend_index_path(frontend_dist_root: Path) -> Path | None:
    index_path = frontend_dist_root / "index.html"
    return index_path if index_path.exists() else None


def _resolve_frontend_asset(frontend_dist_root: Path, request_path: str) -> Path | None:
    relative = request_path.strip("/")
    if not relative:
        return _frontend_index_path(frontend_dist_root)
    candidate = (frontend_dist_root / relative).resolve()
    try:
        candidate.relative_to(frontend_dist_root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else _frontend_index_path(frontend_dist_root)


def _configure_frontend_routes(app: FastAPI) -> None:
    frontend_dist_root = get_settings().paths.frontend_dist_root
    index_path = _frontend_index_path(frontend_dist_root)
    if index_path is None:
        return

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(index_path, headers=FRONTEND_INDEX_HEADERS)

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_catchall(full_path: str) -> FileResponse:
        resolved = _resolve_frontend_asset(frontend_dist_root, full_path)
        if resolved is None:
            return FileResponse(index_path, headers=FRONTEND_INDEX_HEADERS)
        headers = FRONTEND_INDEX_HEADERS if resolved == index_path else None
        return FileResponse(resolved, headers=headers)


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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(routes_assets.router, prefix="/api", tags=["assets"])
    app.include_router(routes_data.router, prefix="/api", tags=["data"])
    app.include_router(routes_features.router, prefix="/api", tags=["features"])
    app.include_router(routes_predictions.router, prefix="/api", tags=["predictions"])
    app.include_router(routes_signals.router, prefix="/api", tags=["signals"])
    app.include_router(routes_targets.router, prefix="/api", tags=["targets"])
    app.include_router(routes_transforms.router, prefix="/api", tags=["transforms"])
    app.include_router(routes_experiments.router, prefix="/api", tags=["experiments"])
    app.include_router(routes_backtests.router, prefix="/api", tags=["backtests"])
    app.include_router(routes_layouts.router, prefix="/api", tags=["layouts"])
    app.include_router(routes_execution.router, prefix="/api", tags=["execution"])
    _configure_frontend_routes(app)
    return app


app = create_app()
