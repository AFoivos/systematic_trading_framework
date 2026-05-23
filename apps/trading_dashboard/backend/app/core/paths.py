from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_project_root() -> Path:
    configured = os.environ.get("TRADING_DASHBOARD_PROJECT_ROOT") or os.environ.get("PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class DashboardPaths:
    project_root: Path
    app_root: Path
    frontend_dist_root: Path
    data_root: Path
    raw_data_root: Path
    processed_data_root: Path
    experiments_root: Path
    layouts_root: Path

    @classmethod
    def from_project_root(cls, project_root: Path | None = None) -> "DashboardPaths":
        root = (project_root or _default_project_root()).expanduser().resolve()
        app_root = root / "apps" / "trading_dashboard"
        frontend_dist_root = Path(
            os.environ.get("TRADING_DASHBOARD_FRONTEND_DIST", app_root / "frontend" / "dist")
        ).expanduser().resolve()
        return cls(
            project_root=root,
            app_root=app_root,
            frontend_dist_root=frontend_dist_root,
            data_root=root / "data",
            raw_data_root=root / "data" / "raw",
            processed_data_root=root / "data" / "processed",
            experiments_root=root / "logs" / "experiments",
            layouts_root=app_root / "layouts",
        )

    def resolve_project_path(self, value: str | Path) -> Path:
        raw = str(value)
        raw = raw.replace("$PROJECT_ROOT", str(self.project_root))
        path = Path(os.path.expandvars(raw)).expanduser()
        if path.is_absolute():
            # Existing manifests were generated inside a container at /workspace.
            # Map those paths back onto the local repository when possible.
            try:
                rel = path.relative_to("/workspace")
            except ValueError:
                return path.resolve()
            return (self.project_root / rel).resolve()
        return (self.project_root / path).resolve()


def get_paths() -> DashboardPaths:
    return DashboardPaths.from_project_root()
