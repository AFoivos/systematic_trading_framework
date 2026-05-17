from __future__ import annotations

from html import escape as html_escape
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.offline.offline import get_plotlyjs


DASHBOARD_COLORS: dict[str, str] = {
    "text": "#1f2933",
    "muted": "#6b7280",
    "heading": "#111827",
    "page": "#f6f7f9",
    "surface": "#ffffff",
    "border": "#d9dee5",
    "subtle_border": "#edf0f3",
    "grid": "#edf0f3",
    "teal": "#0f766e",
    "amber": "#d97706",
    "purple": "#7c3aed",
    "blue": "#2563eb",
    "rose": "#be123c",
    "gray": "#4b5563",
}

DASHBOARD_PLOT_COLORWAY: list[str] = [
    DASHBOARD_COLORS["teal"],
    DASHBOARD_COLORS["amber"],
    DASHBOARD_COLORS["purple"],
    DASHBOARD_COLORS["blue"],
    DASHBOARD_COLORS["rose"],
    DASHBOARD_COLORS["gray"],
    "#15803d",
    "#b45309",
]


def dashboard_html_style() -> str:
    return """
    :root {
      color: #1f2933;
      background: #f6f7f9;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      color: #1f2933;
      background: #f6f7f9;
      font-size: 13px;
      line-height: 1.5;
    }
    .app-shell { min-height: 100vh; background: #f6f7f9; }
    .top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 64px;
      padding: 12px 22px;
      border-bottom: 1px solid #d9dee5;
      background: #ffffff;
    }
    .top-bar h1 {
      margin: 0;
      color: #111827;
      font-size: 18px;
      line-height: 1.2;
      font-weight: 750;
      letter-spacing: 0;
    }
    .top-bar p {
      margin: 4px 0 0;
      color: #6b7280;
      font-size: 12px;
    }
    .workspace {
      min-width: 0;
      padding: 14px;
    }
    .workspace-status {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 10px;
      color: #5f6b7a;
      font-size: 12px;
    }
    .workspace-status span {
      border: 1px solid #d9dee5;
      border-radius: 999px;
      padding: 4px 8px;
      background: #ffffff;
    }
    .content-surface,
    .chart-canvas {
      width: 100%;
      background: #ffffff;
      border: 1px solid #d9dee5;
      border-radius: 8px;
    }
    .chart-canvas {
      min-height: 680px;
      overflow: hidden;
    }
    .plotly-graph-div { min-height: 640px; }
    .report-content {
      max-width: 1240px;
      margin: 0 auto;
      padding: 22px;
    }
    .report-content h1,
    .report-content h2,
    .report-content h3,
    .report-content h4,
    .report-content h5,
    .report-content h6 {
      color: #111827;
      line-height: 1.25;
      letter-spacing: 0;
    }
    .report-content h1 {
      margin: 0 0 14px;
      font-size: 20px;
    }
    .report-content h2 {
      margin: 24px 0 10px;
      padding-top: 14px;
      border-top: 1px solid #edf0f3;
      font-size: 15px;
    }
    .report-content h3 { margin: 18px 0 8px; font-size: 13px; }
    .report-content p,
    .report-content ul,
    .report-content pre,
    .report-content .table-wrap {
      margin: 0 0 12px;
    }
    .report-content ul { padding-left: 18px; }
    .report-content li + li { margin-top: 4px; }
    .report-content code {
      background: #f3f5f7;
      border: 1px solid #edf0f3;
      border-radius: 4px;
      padding: 1px 5px;
      color: #27313f;
      font: 0.92em/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .report-content pre {
      overflow-x: auto;
      background: #fbfcfd;
      border: 1px solid #d9dee5;
      border-radius: 8px;
      padding: 12px 14px;
    }
    .report-content pre code {
      background: transparent;
      border: 0;
      padding: 0;
    }
    .report-content a { color: #0f766e; font-weight: 650; text-decoration-thickness: 1px; }
    .report-content img {
      display: block;
      max-width: 100%;
      height: auto;
      margin: 10px 0 18px;
      border: 1px solid #d9dee5;
      border-radius: 8px;
      background: #ffffff;
    }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid #d9dee5;
      border-radius: 8px;
      background: #ffffff;
    }
    table {
      width: 100%;
      min-width: 560px;
      border-collapse: collapse;
      font-size: 12px;
    }
    th,
    td {
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid #edf0f3;
      vertical-align: top;
    }
    th {
      background: #fbfcfd;
      color: #111827;
      font-weight: 750;
      position: sticky;
      top: 0;
    }
    tr:nth-child(even) td { background: #fbfcfd; }
    em { color: #6b7280; }
    @media (max-width: 820px) {
      .top-bar { align-items: flex-start; padding: 12px 14px; }
      .workspace { padding: 10px; }
      .report-content { padding: 14px; }
      .chart-canvas { min-height: 560px; }
    }
    """


def plotly_chart_config() -> dict[str, Any]:
    return {
        "displaylogo": False,
        "displayModeBar": True,
        "scrollZoom": True,
        "responsive": True,
        "doubleClick": "reset",
    }


def apply_dashboard_plotly_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=DASHBOARD_COLORS["surface"],
        plot_bgcolor=DASHBOARD_COLORS["surface"],
        colorway=DASHBOARD_PLOT_COLORWAY,
        font={
            "family": "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "size": 12,
            "color": DASHBOARD_COLORS["text"],
        },
        title={
            "font": {"size": 16, "color": DASHBOARD_COLORS["heading"]},
            "x": 0.01,
            "xanchor": "left",
        },
        legend={
            "bgcolor": "rgba(255,255,255,0.88)",
            "bordercolor": DASHBOARD_COLORS["border"],
            "borderwidth": 1,
            "font": {"size": 11, "color": DASHBOARD_COLORS["text"]},
        },
    )
    fig.update_xaxes(
        gridcolor=DASHBOARD_COLORS["grid"],
        zerolinecolor=DASHBOARD_COLORS["subtle_border"],
        linecolor=DASHBOARD_COLORS["border"],
        tickfont={"color": DASHBOARD_COLORS["muted"], "size": 11},
        title_font={"color": DASHBOARD_COLORS["muted"], "size": 11},
    )
    fig.update_yaxes(
        gridcolor=DASHBOARD_COLORS["grid"],
        zerolinecolor=DASHBOARD_COLORS["subtle_border"],
        linecolor=DASHBOARD_COLORS["border"],
        tickfont={"color": DASHBOARD_COLORS["muted"], "size": 11},
        title_font={"color": DASHBOARD_COLORS["muted"], "size": 11},
    )
    return fig


def render_dashboard_html_document(
    *,
    title: str,
    subtitle: str,
    body_html: str,
    content_class: str,
    status_items: list[str] | None = None,
) -> str:
    safe_title = html_escape(title)
    safe_subtitle = html_escape(subtitle)
    status_html = "".join(f"<span>{html_escape(item)}</span>" for item in (status_items or []))
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        f"{dashboard_html_style()}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <div class=\"app-shell\">\n"
        "    <header class=\"top-bar\">\n"
        "      <div>\n"
        f"        <h1>{safe_title}</h1>\n"
        f"        <p>{safe_subtitle}</p>\n"
        "      </div>\n"
        "    </header>\n"
        "    <main class=\"workspace\">\n"
        f"      <div class=\"workspace-status\">{status_html}</div>\n"
        f"      <section class=\"{html_escape(content_class, quote=True)}\">\n"
        f"{body_html}\n"
        "      </section>\n"
        "    </main>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def _ensure_directory_plotlyjs(path: Path, include_plotlyjs: str | bool) -> None:
    if include_plotlyjs != "directory":
        return
    plotly_js_path = path.parent / "plotly.min.js"
    if not plotly_js_path.exists():
        plotly_js_path.write_text(get_plotlyjs(), encoding="utf-8")


def write_plotly_dashboard_html(
    fig: go.Figure,
    path: str | Path,
    *,
    title: str | None = None,
    subtitle: str = "Local experiment graph artifact",
    include_plotlyjs: str | bool = "directory",
    config: dict[str, Any] | None = None,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    themed = go.Figure(fig)
    apply_dashboard_plotly_theme(themed)
    _ensure_directory_plotlyjs(output_path, include_plotlyjs)
    graph_html = themed.to_html(
        include_plotlyjs=include_plotlyjs,
        full_html=False,
        config=config or plotly_chart_config(),
    )
    document = render_dashboard_html_document(
        title=title or str(themed.layout.title.text or "Experiment Graph"),
        subtitle=subtitle,
        body_html=graph_html,
        content_class="chart-canvas",
        status_items=["Experiment artifact", "Interactive Plotly graph"],
    )
    output_path.write_text(document, encoding="utf-8")
