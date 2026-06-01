from __future__ import annotations

import plotly.graph_objects as go


TOPIC_COLORS = [
    "#c0266b",
    "#2f6f73",
    "#6f5fb7",
    "#d18b2f",
    "#1f77b4",
    "#8f3f71",
    "#3a7d44",
    "#b94b4b",
    "#6f8f2f",
    "#7b5b3a",
    "#5167a9",
    "#c05a93",
    "#4d858d",
    "#a8643d",
    "#7f6fa8",
    "#87909c",
]

PINK_SCALE = [
    [0.0, "#fff7fb"],
    [0.22, "#fde2ef"],
    [0.45, "#f8b8d3"],
    [0.68, "#de6e9f"],
    [1.0, "#9f174f"],
]

TEAL_ROSE_SCALE = [
    [0.0, "#f7fbfb"],
    [0.25, "#d6eeee"],
    [0.5, "#92c9ca"],
    [0.75, "#d978a2"],
    [1.0, "#9f174f"],
]


def apply_research_layout(fig: go.Figure, *, height: int = 430, legend: bool = True) -> go.Figure:
    bottom_margin = 104 if legend else 44
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fffafd",
        font={"family": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", "color": "#211827"},
        title={"font": {"size": 17, "color": "#211827"}, "x": 0.0, "xanchor": "left"},
        height=height,
        margin={"l": 48, "r": 24, "t": 58, "b": bottom_margin},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.34,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
            "itemsizing": "constant",
            "itemwidth": 30,
        },
        showlegend=legend,
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#f2dbe7",
        zeroline=False,
        linecolor="#ead4df",
        tickfont={"size": 11, "color": "#5f5360"},
        title_font={"size": 12, "color": "#5f5360"},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#f2dbe7",
        zeroline=False,
        linecolor="#ead4df",
        tickfont={"size": 11, "color": "#5f5360"},
        title_font={"size": 12, "color": "#5f5360"},
    )
    return fig
