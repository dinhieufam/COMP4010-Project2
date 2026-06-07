from __future__ import annotations

import plotly.graph_objects as go

from .creative import ERA_LABELS

_CORAL      = "#cc785c"
_CORAL_BAND = "rgba(204, 120, 92, 0.06)"
_GREY_LINE  = "rgba(140, 135, 128, 0.40)"
_GREY_FILL  = "rgba(140, 135, 128, 0.15)"

EVENT_MARKERS = [
    (2012, "AlexNet"),
    (2014, "GANs"),
    (2017, "Transformers"),
    (2020, "GPT-3"),
    (2022, "ChatGPT"),
]


def add_era_bands(fig: go.Figure) -> go.Figure:
    for start, end, label in ERA_LABELS:
        short_label = label.split("·")[1].strip() if "·" in label else label
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor=_CORAL_BAND,
            opacity=1,
            layer="below",
            line_width=0,
        )
        fig.add_annotation(
            x=(start + end) / 2,
            y=1.01,
            yref="paper",
            text=short_label,
            showarrow=False,
            font=dict(size=9, color="#8e8b82"),
            xanchor="center",
            yanchor="bottom",
        )
    return fig


def add_event_markers(fig: go.Figure, which: list[str] | None = None) -> go.Figure:
    markers = [
        (y, label) for y, label in EVENT_MARKERS
        if which is None or label in which
    ]
    for year, label in markers:
        fig.add_vline(
            x=year,
            line_dash="dot",
            line_color=_CORAL,
            line_width=1.2,
            opacity=0.5,
        )
        fig.add_annotation(
            x=year,
            y=0.97,
            yref="paper",
            text=label,
            textangle=-90,
            showarrow=False,
            font=dict(size=9, color=_CORAL),
            xanchor="right",
        )
    return fig


def highlight_series(fig: go.Figure, protagonists: list[str]) -> go.Figure:
    for trace in fig.data:
        name = getattr(trace, "name", "") or ""
        if name.endswith(" forecast"):
            continue
        if name in protagonists:
            updates: dict = {"opacity": 1.0}
            if hasattr(trace, "line") and trace.line is not None:
                updates["line"] = dict(color=_CORAL)
            if hasattr(trace, "fillcolor"):
                updates["fillcolor"] = "rgba(204,120,92,0.25)"
            trace.update(updates)
        else:
            updates = {"opacity": 0.4}
            if hasattr(trace, "line") and trace.line is not None:
                updates["line"] = dict(color=_GREY_LINE)
            if hasattr(trace, "fillcolor"):
                updates["fillcolor"] = _GREY_FILL
            trace.update(updates)
    return fig
