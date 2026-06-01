from __future__ import annotations

import plotly.graph_objects as go


TOPIC_COLORS = [
    "#d94f83",
    "#327c83",
    "#8f63a9",
    "#c9824a",
    "#5d7fb6",
    "#e17a9e",
    "#6c9a69",
    "#bd645c",
    "#a7a85b",
    "#7d6a58",
    "#7883bf",
    "#cf72ad",
    "#5f9da3",
    "#b67655",
    "#927eb5",
    "#92919a",
]

PINK_SCALE = [
    [0.0, "#fff9fb"],
    [0.2, "#fde9ef"],
    [0.45, "#f7c2d1"],
    [0.72, "#e9799d"],
    [1.0, "#ae2558"],
]

TEAL_ROSE_SCALE = [
    [0.0, "#fff9fb"],
    [0.22, "#fae5ec"],
    [0.48, "#b7d9d6"],
    [0.72, "#e57fa0"],
    [1.0, "#a71f52"],
]


def apply_research_layout(fig: go.Figure, *, height: int = 430, legend: bool = True) -> go.Figure:
    bottom_margin = 92 if legend else 44
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,249,251,0.82)",
        font={"family": "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", "color": "#2b1722"},
        title={"font": {"size": 17, "color": "#2b1722"}, "x": 0.0, "xanchor": "left"},
        height=height,
        margin={"l": 52, "r": 26, "t": 58, "b": bottom_margin},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.28,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
            "itemsizing": "constant",
            "itemwidth": 34,
        },
        showlegend=legend,
        hoverlabel={
            "bgcolor": "#fff9fb",
            "bordercolor": "#e98ead",
            "font": {"color": "#2b1722", "size": 12},
        },
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(238, 178, 196, 0.55)",
        zeroline=False,
        linecolor="rgba(224, 132, 163, 0.72)",
        tickfont={"size": 11, "color": "#745462"},
        title_font={"size": 12, "color": "#745462"},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(238, 178, 196, 0.55)",
        zeroline=False,
        linecolor="rgba(224, 132, 163, 0.72)",
        tickfont={"size": 11, "color": "#745462"},
        title_font={"size": 12, "color": "#745462"},
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
        font={"size": 14, "color": "#7a5967"},
        align="center",
        bgcolor="rgba(255, 249, 251, 0.78)",
        bordercolor="#efabc0",
        borderpad=12,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return apply_research_layout(fig, height=height, legend=False)
