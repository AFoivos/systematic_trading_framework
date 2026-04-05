from __future__ import annotations

from typing import Any


def plotly_chart_config() -> dict[str, Any]:
    return {
        "displaylogo": False,
        "displayModeBar": True,
        "scrollZoom": True,
        "responsive": True,
        "doubleClick": "reset",
    }
