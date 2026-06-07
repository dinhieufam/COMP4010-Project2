from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .annotations import add_era_bands, add_event_markers
from .creative import ERA_LABELS
from .geography import country_counts_by_year
from .theme import TOPIC_COLORS, apply_research_layout, empty_figure

_CORAL      = "#cc785c"
_CORAL_FILL = "rgba(204, 120, 92, 0.14)"
_GREY_BAR   = "rgba(140, 135, 128, 0.30)"
_CHINA_BLUE = "#4a7fb5"

# Verified exact topic labels from the dataset
_SHORT: dict[str, str] = {
    "Deep Learning Architectures":              "Deep Learning",
    "Natural Language Processing & LLMs":       "NLP & LLMs",
    "Computer Vision & Multimodal Learning":    "Computer Vision",
    "Reinforcement Learning & Decision Making": "Reinforcement Learning",
    "Generative Models":                        "Generative Models",
    "Optimization & Learning Algorithms":       "Optimization",
    "Data, Evaluation & Benchmarks":            "Data & Benchmarks",
    "Robustness, Safety & Alignment":           "Safety & Alignment",
    "Foundations & Theory":                     "Theory",
    "Probabilistic Modeling & Bayesian Inference": "Bayesian Methods",
    "Applications & Scientific ML":             "Scientific ML",
    "Graph Learning & Network Science":         "Graph Learning",
    "Neuroscience & Cognitive Science":         "Neuroscience",
    "Fairness, Privacy & Security":             "Fairness & Privacy",
    "Robotics & Control":                       "Robotics",
    "General / Other ML":                       "General ML",
}

_H = 440  # shared story chart height


def _after_layout(fig: go.Figure, *, legend: bool = False, legend_rows: int = 1) -> go.Figure:
    """Call after apply_research_layout to apply story-specific overrides."""
    if legend:
        b_margin = 40 + 36 * legend_rows  # 36px per legend row
        fig.update_layout(
            showlegend=True,
            margin={"b": b_margin},
            legend={
                "orientation": "h",
                "x": 0,
                "y": -(0.06 + 0.12 * legend_rows),
                "xanchor": "left",
                "yanchor": "top",
                "font": {"size": 10, "color": "#6c6a64"},
                "itemsizing": "constant",
                "itemwidth": 30,
            },
        )
    else:
        fig.update_layout(showlegend=False)
    return fig


def _topic_shares_year(papers: pd.DataFrame, year: int) -> pd.DataFrame:
    yr = papers[papers["year"] == year]
    if yr.empty:
        return pd.DataFrame(columns=["topic_label", "short", "share", "count"])
    counts = yr.groupby("topic_label", as_index=False).agg(count=("paper_id", "count"))
    total = counts["count"].sum()
    counts["share"] = counts["count"] / total * 100
    counts["short"] = counts["topic_label"].map(_SHORT).fillna(counts["topic_label"])
    return counts.sort_values("share", ascending=False)


# ── Chapter 2 ─────────────────────────────────────────────────────────────────

def make_ch2_topic_bar(papers: pd.DataFrame, year: int, highlight: str | None = None) -> go.Figure:
    """Horizontal bar: top 12 topics in a given year; highlight gets coral."""
    df = _topic_shares_year(papers, year)
    if df.empty:
        return empty_figure(f"Topic share · {year}")
    top = df.head(12)
    colors = [
        _CORAL if (highlight and row["topic_label"] == highlight) else _GREY_BAR
        for _, row in top.iterrows()
    ]
    fig = go.Figure(go.Bar(
        x=top["share"].tolist(),
        y=top["short"].tolist(),
        orientation="h",
        marker_color=colors,
        text=[f"{s:.1f}%" for s in top["share"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br><b>%{x:.1f}%</b> of papers<extra></extra>",
    ))
    fig.update_layout(
        title=f"Topic share of papers · {year}",
        xaxis=dict(title="Share (%)", range=[0, top["share"].max() * 1.38], showgrid=True),
        yaxis=dict(autorange="reversed"),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 155, "r": 80, "t": 52, "b": 40}, showlegend=False)
    return fig


def make_ch2_dl_neuro_line(papers: pd.DataFrame) -> go.Figure:
    """Dual line: Deep Learning and Neuroscience share % over all years with era bands."""
    counts = (
        papers.groupby(["year", "topic_label"], as_index=False)
        .agg(count=("paper_id", "count"))
    )
    totals = counts.groupby("year")["count"].transform("sum").replace(0, np.nan)
    counts["share"] = counts["count"] / totals * 100

    dl = (counts[counts["topic_label"] == "Deep Learning Architectures"]
          .copy().sort_values("year"))
    neuro = (counts[counts["topic_label"] == "Neuroscience & Cognitive Science"]
             .copy().sort_values("year"))
    if dl.empty and neuro.empty:
        return empty_figure("DL & Neuroscience share over time")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dl["year"].tolist(),
        y=dl["share"].tolist(),
        name="Deep Learning",
        mode="lines+markers",
        line=dict(color=_CORAL, width=2.5),
        marker=dict(size=5, color=_CORAL),
        fill="tozeroy",
        fillcolor=_CORAL_FILL,
        hovertemplate="%{x}<br>Deep Learning: <b>%{y:.1f}%</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=neuro["year"].tolist(),
        y=neuro["share"].tolist(),
        name="Neuroscience",
        mode="lines+markers",
        line=dict(color=_CHINA_BLUE, width=2.5),
        marker=dict(size=5, color=_CHINA_BLUE),
        fill="tozeroy",
        fillcolor="rgba(74,127,181,0.10)",
        hovertemplate="%{x}<br>Neuroscience: <b>%{y:.1f}%</b><extra></extra>",
    ))
    add_era_bands(fig)
    add_event_markers(fig)
    max_y = max(
        float(dl["share"].max()) if not dl.empty else 0,
        float(neuro["share"].max()) if not neuro.empty else 0,
    )
    fig.update_layout(
        title="Deep Learning & Neuroscience · % share of NeurIPS papers over time",
        xaxis=dict(title="Year"),
        yaxis=dict(title="Share of papers (%)", range=[0, max_y * 1.5]),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 60, "r": 30, "t": 52, "b": 80})
    _after_layout(fig, legend=True, legend_rows=1)
    return fig


def make_ch2_topic_compare(papers: pd.DataFrame) -> go.Figure:
    """Grouped bar: 8 topic shares in 1987 vs 2025, sorted by 1987 share descending."""
    targets = [
        "Neuroscience & Cognitive Science",
        "Natural Language Processing & LLMs",
        "Deep Learning Architectures",
        "Optimization & Learning Algorithms",
        "Probabilistic Modeling & Bayesian Inference",
        "Reinforcement Learning & Decision Making",
        "Computer Vision & Multimodal Learning",
        "Robustness, Safety & Alignment",
    ]

    rows: dict[int, list[float]] = {}
    for year in [1987, 2025]:
        df = _topic_shares_year(papers, year)
        rows[year] = []
        for t in targets:
            match = df[df["topic_label"] == t]
            rows[year].append(float(match["share"].iloc[0]) if not match.empty else 0.0)

    # Sort topics by 1987 share descending so the biggest early topics come first
    order = sorted(range(len(targets)), key=lambda i: rows[1987][i], reverse=True)
    targets = [targets[i] for i in order]
    rows[1987] = [rows[1987][i] for i in order]
    rows[2025] = [rows[2025][i] for i in order]
    shorts = [_SHORT.get(t, t) for t in targets]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="1987",
        x=shorts,
        y=rows[1987],
        marker_color=_CORAL,   # 1987 = coral/orange across all topics
        opacity=0.85,
        hovertemplate="%{x}<br>1987: <b>%{y:.1f}%</b><extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="2025",
        x=shorts,
        y=rows[2025],
        marker_color=_GREY_BAR,  # 2025 = grey across all topics
        hovertemplate="%{x}<br>2025: <b>%{y:.1f}%</b><extra></extra>",
    ))
    fig.update_layout(
        title="Topic shares · 1987 vs 2025",
        barmode="group",
        xaxis=dict(title="", tickangle=-30),
        yaxis=dict(title="Share of papers (%)"),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 52, "r": 20, "t": 52, "b": 130})
    _after_layout(fig, legend=True, legend_rows=1)
    return fig


# ── Chapter 3 ─────────────────────────────────────────────────────────────────

def make_ch3_era_composition(papers: pd.DataFrame) -> go.Figure:
    """100%-stacked horizontal bar: top 7 topics + Other for each research era."""
    all_topics_ranked = (
        papers.groupby("topic_label", as_index=False)
        .agg(count=("paper_id", "count"))
        .sort_values("count", ascending=False)["topic_label"].tolist()
    )
    top_n = 7
    top_topics = all_topics_ranked[:top_n]
    display_topics = top_topics + ["Other"]

    era_names: list[str] = []
    era_rows: list[dict] = []
    for start, end, label in ERA_LABELS:
        short = label.split("·")[1].strip() if "·" in label else label
        era_names.append(short)
        era_papers = papers[(papers["year"] >= start) & (papers["year"] <= end)]
        if era_papers.empty:
            for t in display_topics:
                era_rows.append({"era": short, "topic": t, "share": 0.0})
            continue
        counts = (era_papers.groupby("topic_label", as_index=False)
                  .agg(count=("paper_id", "count")))
        total = counts["count"].sum()
        counts["share"] = counts["count"] / total * 100
        g_map = dict(zip(counts["topic_label"], counts["share"]))
        for t in top_topics:
            era_rows.append({"era": short, "topic": t, "share": float(g_map.get(t, 0.0))})
        other_share = sum(v for k, v in g_map.items() if k not in top_topics)
        era_rows.append({"era": short, "topic": "Other", "share": other_share})

    df = pd.DataFrame(era_rows)
    fig = go.Figure()
    for i, topic in enumerate(display_topics):
        tdf = (df[df["topic"] == topic]
               .set_index("era").reindex(era_names, fill_value=0.0).reset_index())
        color = "rgba(140, 135, 128, 0.40)" if topic == "Other" else TOPIC_COLORS[i % len(TOPIC_COLORS)]
        short = _SHORT.get(topic, topic)
        fig.add_trace(go.Bar(
            name=short,
            x=tdf["share"].tolist(),
            y=tdf["era"].tolist(),
            orientation="h",
            marker_color=color,
            hovertemplate=f"<b>{short}</b><br>%{{y}}: %{{x:.1f}}%<extra></extra>",
        ))

    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(
        title="How topic composition changed across research eras",
        barmode="stack",
        xaxis=dict(title="Share of papers (%)", range=[0, 101]),
        yaxis=dict(categoryorder="array", categoryarray=era_names[::-1]),
        showlegend=True,
        margin={"l": 145, "r": 20, "t": 52, "b": 120},
        legend={
            "orientation": "h",
            "x": 0,
            "y": -0.30,
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 9, "color": "#6c6a64"},
            "itemsizing": "constant",
            "itemwidth": 30,
        },
    )
    return fig


# ── Chapter 4 ─────────────────────────────────────────────────────────────────

def make_ch4_country_bar(papers: pd.DataFrame, year: int, highlight: str | None = None) -> go.Figure:
    """Horizontal bar: top countries by share of participations in a single year."""
    counts = country_counts_by_year(papers)
    yr_all = counts[counts["year"] == year]
    if yr_all.empty:
        return empty_figure(f"Country participation · {year}")
    total = yr_all["participations"].sum()  # denominator = ALL countries, not just top-10
    yr = yr_all.sort_values("participations", ascending=False).head(10).copy()
    yr["pct"] = yr["participations"] / total * 100
    colors = [
        _CORAL if (highlight and row["country"] == highlight) else _GREY_BAR
        for _, row in yr.iterrows()
    ]
    fig = go.Figure(go.Bar(
        x=yr["pct"].tolist(),
        y=yr["country"].tolist(),
        orientation="h",
        marker_color=colors,
        text=[f"{p:.0f}%" for p in yr["pct"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br><b>%{x:.1f}%</b> of participations<extra></extra>",
    ))
    fig.update_layout(
        title=f"Country participation · {year}",
        xaxis=dict(title="Share of participations (%)", range=[0, yr["pct"].max() * 1.35]),
        yaxis=dict(autorange="reversed"),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 145, "r": 80, "t": 52, "b": 40}, showlegend=False)
    return fig


def make_ch4_us_china_line(papers: pd.DataFrame) -> go.Figure:
    """Line: US vs China share of paper-participations · reliable years only (2021+)."""
    counts = country_counts_by_year(papers)
    if counts.empty:
        return empty_figure("US vs China over time")

    # Only use years with reliable coverage (2021 onwards, >50% coverage)
    reliable = counts[counts["year"] >= 2021]
    if reliable.empty:
        return empty_figure("US vs China · insufficient data")

    yearly_totals = reliable.groupby("year")["participations"].sum()
    us = reliable[reliable["country"] == "United States"].set_index("year")["participations"]
    china = reliable[reliable["country"] == "China"].set_index("year")["participations"]
    years = sorted(reliable["year"].unique())
    us_pct    = [us.get(y, 0)    / yearly_totals.get(y, 1) * 100 for y in years]
    china_pct = [china.get(y, 0) / yearly_totals.get(y, 1) * 100 for y in years]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=us_pct, name="United States",
        mode="lines+markers",
        line=dict(color=_CORAL, width=2.8),
        marker=dict(size=7),
        hovertemplate="%{x}: US <b>%{y:.1f}%</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=china_pct, name="China",
        mode="lines+markers",
        line=dict(color=_CHINA_BLUE, width=2.8),
        marker=dict(size=7),
        hovertemplate="%{x}: China <b>%{y:.1f}%</b><extra></extra>",
    ))
    max_y = max(max(us_pct or [1]), max(china_pct or [1]))
    fig.update_layout(
        title="US vs China · share of NeurIPS paper-participations (2021–2025)",
        xaxis=dict(title="Year", dtick=1),
        yaxis=dict(title="Share of participations (%)", range=[0, max_y * 1.25]),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 60, "r": 20, "t": 52, "b": 80})
    _after_layout(fig, legend=True, legend_rows=1)
    return fig


# ── Chapter 5 ─────────────────────────────────────────────────────────────────

def make_ch5_institution_compare(institution_year: pd.DataFrame) -> go.Figure:
    """Side-by-side horizontal bars: top institutions 1990-1999 vs 2022-2025."""

    def _clean(name: str) -> str:
        if name.startswith("arnegie"):
            return "Carnegie Mellon University"
        # Strip trailing digits and punctuation that are data artifacts (e.g. "University of Toronto1")
        stripped = name.rstrip("0123456789.").rstrip()
        return stripped if stripped else name

    def _top(df: pd.DataFrame, y_min: int, y_max: int, n: int = 10) -> pd.Series:
        sub = df[
            (df["year"] >= y_min) & (df["year"] <= y_max) & (df["institution"] != "Unknown")
        ]
        totals = (sub.groupby("institution")["paper_count"].sum()
                  .sort_values(ascending=False))
        totals.index = [_clean(i) for i in totals.index]
        return totals.head(n)

    early  = _top(institution_year, 1990, 1999)
    recent = _top(institution_year, 2022, 2025)

    _US = {
        "Massachusetts Institute of Technology", "Carnegie Mellon University",
        "California Institute of Technology", "Stanford University",
        "University of California, Berkeley", "University of California San Diego",
        "Princeton University", "Microsoft", "Bell Labs",
        "Salk Institute for Biological Studies",
    }

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=["1990–1999  (Foundations era)", "2022–2025  (Generative era)"],
        vertical_spacing=0.16,
    )
    fig.add_trace(go.Bar(
        x=early.values.tolist(),
        y=early.index.tolist(),
        orientation="h",
        marker_color=_GREY_BAR,  # foundations era: all grey (no highlight needed)
        hovertemplate="%{y}<br><b>%{x}</b> papers<extra></extra>",
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=recent.values.tolist(),
        y=recent.index.tolist(),
        orientation="h",
        # generative era: coral = new entrants (non-US); grey = US incumbents
        marker_color=[_GREY_BAR if n in _US else _CORAL for n in recent.index],
        hovertemplate="%{y}<br><b>%{x}</b> papers<extra></extra>",
        showlegend=False,
    ), row=2, col=1)

    fig.update_yaxes(autorange="reversed", row=1, col=1)
    fig.update_yaxes(autorange="reversed", row=2, col=1)
    fig.update_layout(title="Who publishes at NeurIPS · then vs now")
    apply_research_layout(fig, height=700, legend=False)
    fig.update_layout(margin={"l": 220, "r": 30, "t": 80, "b": 40}, showlegend=False)
    return fig


# ── Chapter 7 ─────────────────────────────────────────────────────────────────

def make_ch7_rising_topics(papers: pd.DataFrame) -> go.Figure:
    """Line: share of the 5 fastest-growing topics since 2015."""
    recent = papers[papers["year"] >= 2015].copy()
    if recent.empty:
        return empty_figure("Rising topics 2015–present")
    counts = (recent.groupby(["year", "topic_label"], as_index=False)
              .agg(count=("paper_id", "count")))
    totals = counts.groupby("year")["count"].transform("sum").replace(0, np.nan)
    counts["share"] = counts["count"] / totals * 100

    year_min = int(counts["year"].min())
    year_max = int(counts["year"].max())
    early = (counts[counts["year"].isin([year_min, year_min + 1])]
             .groupby("topic_label")["share"].mean())
    late  = (counts[counts["year"].isin([year_max, year_max - 1])]
             .groupby("topic_label")["share"].mean())
    rising = (late - early).dropna().sort_values(ascending=False).head(5).index.tolist()

    fig = go.Figure()
    for i, topic in enumerate(rising):
        tdf = counts[counts["topic_label"] == topic].sort_values("year")
        color = TOPIC_COLORS[i % len(TOPIC_COLORS)]
        short = _SHORT.get(topic, topic)
        fig.add_trace(go.Scatter(
            x=tdf["year"].tolist(),
            y=tdf["share"].tolist(),
            name=short,
            mode="lines+markers",
            line=dict(color=color, width=2.2),
            marker=dict(size=5),
            hovertemplate=f"<b>{topic}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
    add_event_markers(fig, which=["GPT-3", "ChatGPT"])
    fig.update_layout(
        title="Fastest-growing topics · 2015 to present",
        xaxis=dict(title="Year"),
        yaxis=dict(title="Share of papers (%)"),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 60, "r": 20, "t": 52, "b": 80})
    _after_layout(fig, legend=True, legend_rows=1)
    return fig


# ── Chapter 6 (conscience) ────────────────────────────────────────────────────

_GREEN = "#6b8e6b"

def make_ch6_conscience_chart(papers: pd.DataFrame) -> go.Figure:
    """Line chart: growth of Safety, Fairness, and Evaluation topics from 2010 onward."""
    conscience_topics = [
        ("Robustness, Safety & Alignment",     _CORAL,      "Safety & Alignment"),
        ("Fairness, Privacy & Security",        _CHINA_BLUE, "Fairness & Privacy"),
        ("Data, Evaluation & Benchmarks",       _GREEN,      "Data & Evaluation"),
    ]

    counts = (
        papers.groupby(["year", "topic_label"], as_index=False)
        .agg(count=("paper_id", "count"))
    )
    totals = counts.groupby("year")["count"].transform("sum").replace(0, np.nan)
    counts["share"] = counts["count"] / totals * 100

    recent = counts[counts["year"] >= 2010].copy()

    fig = go.Figure()
    for topic, color, short in conscience_topics:
        tdf = recent[recent["topic_label"] == topic].sort_values("year")
        if tdf.empty:
            continue
        fig.add_trace(go.Scatter(
            x=tdf["year"].tolist(),
            y=tdf["share"].tolist(),
            name=short,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=6, color=color),
            hovertemplate=f"<b>{short}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))

    add_event_markers(fig, which=["GPT-3", "ChatGPT"])
    max_y = float(recent[recent["topic_label"].isin([t for t, _, _ in conscience_topics])]["share"].max() or 8)
    fig.update_layout(
        title="Safety, Fairness & Evaluation · % share of NeurIPS papers (2010–2025)",
        xaxis=dict(title="Year", dtick=2),
        yaxis=dict(title="Share of papers (%)", range=[0, max_y * 1.4]),
    )
    apply_research_layout(fig, height=_H, legend=False)
    fig.update_layout(margin={"l": 60, "r": 20, "t": 52, "b": 80})
    _after_layout(fig, legend=True, legend_rows=1)
    return fig
