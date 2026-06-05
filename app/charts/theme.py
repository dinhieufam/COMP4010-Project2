from __future__ import annotations

import plotly.graph_objects as go


# Warm editorial palette — 16 colours anchored on Anthropic coral/cream/navy.
# Muted saturation keeps charts readable on the cream canvas (#faf9f5).
TOPIC_COLORS = [
    "#cc785c",  # coral (brand primary)
    "#5db8a6",  # accent teal
    "#e8a55a",  # accent amber
    "#9b7bb8",  # warm purple
    "#6589b8",  # muted slate blue
    "#7ab870",  # muted sage green
    "#b85875",  # deep rose
    "#5482a0",  # steel blue
    "#c99b48",  # golden
    "#5e8a5e",  # forest green
    "#c05555",  # warm terracotta red
    "#6a86a0",  # cooler slate
    "#c47898",  # dusty mauve
    "#8a6e58",  # warm brown
    "#8aa882",  # sage
    "#938f86",  # warm grey
]

# Coral sequential scale — canvas (near-white cream) → deep coral
CORAL_SCALE = [
    [0.00, "#faf9f5"],
    [0.20, "#f5e9e2"],
    [0.45, "#e8b49a"],
    [0.72, "#cc785c"],
    [1.00, "#7a3a24"],
]

# Teal-to-coral diverging scale for provenance/coverage charts
TEAL_CORAL_SCALE = [
    [0.00, "#faf9f5"],
    [0.22, "#d8f0ec"],
    [0.48, "#5db8a6"],
    [0.72, "#e8a55a"],
    [1.00, "#a9583e"],
]

# Keep old names so existing chart modules import without breaking
PINK_SCALE = CORAL_SCALE
TEAL_ROSE_SCALE = TEAL_CORAL_SCALE

_CANVAS   = "#faf9f5"
_INK      = "#141413"
_MUTED    = "#6c6a64"
_HAIRLINE = "rgba(230, 223, 216, 0.85)"
_CORAL    = "#cc785c"


def apply_research_layout(fig: go.Figure, *, height: int = 430, legend: bool = True) -> go.Figure:
    bottom_margin = 88 if legend else 40
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_CANVAS,
        font={
            "family": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
            "color": _INK,
        },
        title={"font": {"size": 15, "color": _INK}, "x": 0.0, "xanchor": "left"},
        height=height,
        margin={"l": 52, "r": 26, "t": 52, "b": bottom_margin},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.26,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11, "color": _MUTED},
            "itemsizing": "constant",
            "itemwidth": 34,
        },
        showlegend=legend,
        hoverlabel={
            "bgcolor": _CANVAS,
            "bordercolor": _CORAL,
            "font": {"color": _INK, "size": 12},
        },
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=_HAIRLINE,
        zeroline=False,
        linecolor="rgba(230, 223, 216, 0.9)",
        tickfont={"size": 11, "color": _MUTED},
        title_font={"size": 12, "color": _MUTED},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=_HAIRLINE,
        zeroline=False,
        linecolor="rgba(230, 223, 216, 0.9)",
        tickfont={"size": 11, "color": _MUTED},
        title_font={"size": 12, "color": _MUTED},
    )
    return fig


def empty_figure(title: str, message: str = "No matching papers for the current filters.", *, height: int = 430) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title)
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.52,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 14, "color": _MUTED},
        align="center",
        bgcolor=_CANVAS,
        bordercolor=_CORAL,
        borderpad=12,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return apply_research_layout(fig, height=height, legend=False)
