from __future__ import annotations

import math
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .theme import CORAL_SCALE, TOPIC_COLORS, apply_research_layout, empty_figure
from .utils import country_display, explode_tokens, split_tokens

_CANVAS    = "#faf9f5"
_INK       = "#141413"
_MUTED     = "#6c6a64"
_HAIRLINE  = "#e6dfd8"
_CORAL     = "#cc785c"
_CORAL_A   = "rgba(204, 120, 92, 0.22)"
_NODE_RING = _CANVAS

ERA_LABELS = [
    (1987, 1997, "1987–1997 · foundations"),
    (1998, 2007, "1998–2007 · probabilistic era"),
    (2008, 2015, "2008–2015 · deep learning rise"),
    (2016, 2021, "2016–2021 · scaling era"),
    (2022, 2030, "2022–2025 · generative era"),
]


def topic_year_counts(papers: pd.DataFrame) -> pd.DataFrame:
    if papers.empty:
        return pd.DataFrame(columns=["year", "topic_label", "paper_count", "topic_share"])
    data = (
        papers.groupby(["year", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values(["year", "paper_count"], ascending=[True, False])
    )
    totals = data.groupby("year")["paper_count"].transform("sum").replace(0, np.nan)
    data["topic_share"] = data["paper_count"] / totals
    return data


def topic_rank_table(papers: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    data = topic_year_counts(papers)
    if data.empty:
        return pd.DataFrame(columns=["year", "topic_label", "paper_count", "rank"])
    focus = data.groupby("topic_label")["paper_count"].sum().sort_values(ascending=False).head(top_n).index
    data = data[data["topic_label"].isin(focus)].copy()
    data["rank"] = data.groupby("year")["paper_count"].rank(method="first", ascending=False)
    return data.sort_values(["topic_label", "year"])


def topic_dna_table(papers: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    data = topic_year_counts(papers)
    if data.empty:
        return pd.DataFrame(columns=["year", "topic_label", "topic_share", "paper_count", "start", "end"])
    focus = data.groupby("topic_label")["paper_count"].sum().sort_values(ascending=False).head(top_n).index
    data["topic_label"] = data["topic_label"].where(data["topic_label"].isin(focus), "Other topics")
    data = (
        data.groupby(["year", "topic_label"], as_index=False)
        .agg(paper_count=("paper_count", "sum"))
        .sort_values(["year", "topic_label"])
    )
    totals = data.groupby("year")["paper_count"].transform("sum").replace(0, np.nan)
    data["topic_share"] = data["paper_count"] / totals
    data = data.sort_values(["year", "topic_share"], ascending=[True, False])
    data["start"] = data.groupby("year")["topic_share"].cumsum() - data["topic_share"]
    data["end"] = data.groupby("year")["topic_share"].cumsum()
    return data


def metadata_weather_table(papers: pd.DataFrame) -> pd.DataFrame:
    if papers.empty:
        return pd.DataFrame(columns=["year", "quality_score", "weather"])
    working = papers.copy()
    for column, default in [
        ("institution_known", False),
        ("country_known", False),
        ("affiliation_confidence", 0.0),
        ("topic_review_flag", False),
    ]:
        if column not in working.columns:
            working[column] = default
    data = (
        working.groupby("year", as_index=False)
        .agg(
            papers=("paper_id", "count"),
            institution_coverage=("institution_known", "mean"),
            country_coverage=("country_known", "mean"),
            confidence=("affiliation_confidence", "mean"),
            review_rate=("topic_review_flag", "mean"),
        )
        .sort_values("year")
    )
    data["quality_score"] = (
        0.32 * data["institution_coverage"].fillna(0)
        + 0.32 * data["country_coverage"].fillna(0)
        + 0.26 * data["confidence"].fillna(0)
        + 0.10 * (1 - data["review_rate"].fillna(0))
    ).clip(0, 1)
    data["weather"] = pd.cut(
        data["quality_score"],
        bins=[-0.01, 0.55, 0.75, 0.9, 1.01],
        labels=["stormy", "cloudy", "bright", "sunny"],
    ).astype(str)
    return data


def paper_universe_points(papers: pd.DataFrame, max_points: int = 3500) -> pd.DataFrame:
    if papers.empty:
        return pd.DataFrame(columns=["x", "y"])
    data = papers.copy()
    if len(data) > max_points:
        data = data.sample(max_points, random_state=42)
    text_parts = []
    for column in [
        "title", "authors_text", "topic_label", "secondary_topic_labels_text",
        "countries_text", "institutions_text", "affiliation_source",
    ]:
        if column in data.columns:
            text_parts.append(data[column].fillna("").astype(str))
    text = text_parts[0]
    for part in text_parts[1:]:
        text = text + " " + part
    out = data.reset_index(drop=True).copy()
    if len(out) >= 4 and text.str.strip().str.len().gt(0).any():
        try:
            max_features = min(1800, max(64, len(out) // 2))
            matrix = TfidfVectorizer(max_features=max_features, min_df=1, stop_words="english").fit_transform(text)
            if min(matrix.shape) >= 3:
                coords = TruncatedSVD(n_components=2, random_state=42).fit_transform(matrix)
                coords = normalize(coords, axis=0)
                out["x"] = coords[:, 0]
                out["y"] = coords[:, 1]
            else:
                raise ValueError("not enough TF-IDF dimensions")
        except Exception:
            angles = np.linspace(0, 2 * math.pi, len(out), endpoint=False)
            out["x"] = np.cos(angles)
            out["y"] = np.sin(angles)
    else:
        angles = np.linspace(0, 2 * math.pi, len(out), endpoint=False)
        out["x"] = np.cos(angles)
        out["y"] = np.sin(angles)
    return out


def _recent_growth(papers: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    if papers.empty:
        return pd.DataFrame(columns=["topic_label", "growth_pp"])
    years = sorted(papers["year"].astype(int).unique())
    if len(years) < 2:
        counts = papers["topic_label"].value_counts().rename_axis("topic_label").reset_index(name="paper_count")
        counts["growth_pp"] = 0.0
        return counts
    early_years = years[: min(window, len(years))]
    recent_years = years[-min(window, len(years)):]
    early = papers[papers["year"].isin(early_years)]["topic_label"].value_counts(normalize=True)
    recent = papers[papers["year"].isin(recent_years)]["topic_label"].value_counts(normalize=True)
    growth = ((recent - early).fillna(0) * 100).rename("growth_pp").reset_index()
    growth = growth.rename(columns={"index": "topic_label"})
    return growth


def _topic_graph_edges(papers: pd.DataFrame, max_edges: int = 36) -> pd.DataFrame:
    rows: list[dict] = []
    if "secondary_topic_labels_text" in papers.columns:
        for primary, secondary_text in papers[["topic_label", "secondary_topic_labels_text"]].itertuples(index=False):
            for secondary in split_tokens(secondary_text):
                if secondary and secondary != primary:
                    rows.append({"source": primary, "target": secondary, "weight": 1})
    if not rows:
        topics = papers["topic_label"].value_counts().head(10).index.tolist()
        rows = [{"source": a, "target": b, "weight": 1} for a, b in combinations(topics, 2)]
    edges = pd.DataFrame(rows)
    if edges.empty:
        return pd.DataFrame(columns=["source", "target", "weight"])
    return (
        edges.groupby(["source", "target"], as_index=False)
        .agg(weight=("weight", "sum"))
        .sort_values("weight", ascending=False)
        .head(max_edges)
    )


def make_topic_galaxy(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Topic Galaxy")
    counts = papers["topic_label"].value_counts().head(16)
    edges = _topic_graph_edges(papers)
    allowed = set(counts.index)
    graph = nx.Graph()
    for topic, count in counts.items():
        graph.add_node(topic, count=int(count))
    for row in edges.to_dict("records"):
        if row["source"] in allowed and row["target"] in allowed:
            graph.add_edge(row["source"], row["target"], weight=float(row["weight"]))
    if graph.number_of_edges() == 0 and graph.number_of_nodes() > 1:
        nodes = list(graph.nodes)
        for a, b in zip(nodes, nodes[1:]):
            graph.add_edge(a, b, weight=1)
    pos = nx.spring_layout(graph, seed=7, k=0.9, iterations=150, weight="weight")
    fig = go.Figure()
    for source, target, attrs in graph.edges(data=True):
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        w = float(attrs.get("weight", 1))
        opacity = 0.12 + 0.30 * math.sqrt(w / max(edges["weight"].max() if not edges.empty else 1, 1))
        fig.add_trace(
            go.Scatter(
                x=[x0, x1], y=[y0, y1], mode="lines",
                line={"color": f"rgba(204, 120, 92, {opacity:.2f})", "width": 1.2},
                hoverinfo="skip", showlegend=False,
            )
        )
    node_x, node_y, labels, sizes, colors = [], [], [], [], []
    max_count = max(counts.max(), 1)
    for idx, (node, attrs) in enumerate(graph.nodes(data=True)):
        x, y = pos[node]
        count = attrs["count"]
        node_x.append(x)
        node_y.append(y)
        labels.append(f"{node}<br>{count:,} papers")
        sizes.append(18 + 48 * math.sqrt(count / max_count))
        colors.append(TOPIC_COLORS[idx % len(TOPIC_COLORS)])
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers",
        marker={"size": [s + 18 for s in sizes], "color": colors, "opacity": 0.14},
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=list(graph.nodes), hovertext=labels, hoverinfo="text",
        textposition="top center",
        marker={"size": sizes, "color": colors, "opacity": 0.92,
                "line": {"color": _CANVAS, "width": 1.5}},
        textfont={"size": 10, "color": _INK},
        showlegend=False,
    ))
    fig.update_layout(
        title="Topic Galaxy · research constellation",
        xaxis={"visible": False}, yaxis={"visible": False},
    )
    return apply_research_layout(fig, height=540, legend=False)


def make_research_river(papers: pd.DataFrame) -> go.Figure:
    """Sankey from historical eras into dominant research topics."""
    if papers.empty:
        return empty_figure("Research River")
    data = papers.copy()
    data["era"] = data["year"].apply(
        lambda year: next((label for start, end, label in ERA_LABELS if start <= int(year) <= end), str(year))
    )
    top_topics = data["topic_label"].value_counts().head(10).index
    data["topic_focus"] = data["topic_label"].where(data["topic_label"].isin(top_topics), "Other topics")
    grouped = data.groupby(["era", "topic_focus"], as_index=False).agg(paper_count=("paper_id", "count"))
    eras = [label for _, _, label in ERA_LABELS if label in set(grouped["era"])]
    topics = grouped["topic_focus"].drop_duplicates().tolist()
    labels = eras + topics
    index = {label: idx for idx, label in enumerate(labels)}
    era_colors = [TOPIC_COLORS[4]] * len(eras)
    topic_colors = [TOPIC_COLORS[i % len(TOPIC_COLORS)] for i in range(len(topics))]
    fig = go.Figure(
        go.Sankey(
            arrangement="fixed",
            node={
                "pad": 14,
                "thickness": 14,
                "label": labels,
                "color": era_colors + topic_colors,
                "line": {"color": "rgba(169, 88, 62, 0.22)", "width": 0.6},
            },
            link={
                "source": grouped["era"].map(index),
                "target": grouped["topic_focus"].map(index),
                "value": grouped["paper_count"],
                "color": _CORAL_A,
                "hovertemplate": "%{source.label} → %{target.label}<br>%{value:,} papers<extra></extra>",
            },
        )
    )
    fig.update_layout(title="Research River · eras flowing into topics")
    return apply_research_layout(fig, height=500, legend=False)


def make_topic_race(papers: pd.DataFrame) -> go.Figure:
    """Line chart showing annual topic rank changes."""
    ranks = topic_rank_table(papers)
    if ranks.empty:
        return empty_figure("Topic Race")
    fig = go.Figure()
    for idx, topic in enumerate(ranks["topic_label"].drop_duplicates()):
        data = ranks[ranks["topic_label"].eq(topic)]
        fig.add_trace(
            go.Scatter(
                x=data["year"],
                y=data["rank"],
                mode="lines+markers",
                name=topic,
                line={"color": TOPIC_COLORS[idx % len(TOPIC_COLORS)], "width": 2.4},
                marker={"size": 6},
                customdata=data[["paper_count"]],
                hovertemplate="%{fullData.name}<br>%{x}<br>Rank #%{y:.0f}<br>%{customdata[0]:,} papers<extra></extra>",
            )
        )
    fig.update_layout(
        title="Topic Race · annual rank changes",
        yaxis={"autorange": "reversed", "dtick": 1},
        xaxis_title="Year",
        yaxis_title="Rank",
    )
    return apply_research_layout(fig, height=520)


def make_institution_country_treemap(
    papers: pd.DataFrame,
    top_countries: int = 8,
    top_institutions: int = 30,
) -> go.Figure:
    """Institution-Country treemap — hierarchical distribution of papers.

    Countries are parent tiles; institutions are child tiles.
    Tile area = paper participation count, colour = country.
    Much clearer than orbit edge-thickness encoding.
    """
    if papers.empty:
        return empty_figure("Institution-Country Distribution")

    pairs = (
        papers[["paper_id", "countries_text", "institutions_text"]]
        .assign(
            country=lambda d: d["countries_text"].apply(split_tokens),
            institution=lambda d: d["institutions_text"].apply(split_tokens),
        )
        .explode("country")
        .explode("institution")
    )
    pairs = pairs[
        pairs["country"].notna() & pairs["institution"].notna()
        & pairs["country"].ne("") & pairs["institution"].ne("")
    ]
    pairs["country"] = pairs["country"].apply(country_display)

    grouped = pairs.groupby(["country", "institution"], as_index=False).agg(papers=("paper_id", "count"))
    if grouped.empty:
        return empty_figure("Institution-Country Distribution", "No affiliation metadata in current selection.")

    top_c = (
        grouped.groupby("country")["papers"].sum()
        .sort_values(ascending=False).head(top_countries).index
    )
    top_i = (
        grouped.groupby("institution")["papers"].sum()
        .sort_values(ascending=False).head(top_institutions).index
    )
    grouped = grouped[grouped["country"].isin(top_c) & grouped["institution"].isin(top_i)]
    if grouped.empty:
        return empty_figure("Institution-Country Distribution")

    fig = px.treemap(
        grouped,
        path=["country", "institution"],
        values="papers",
        color="country",
        color_discrete_sequence=TOPIC_COLORS,
        title="Institution-country distribution · paper affiliations",
        custom_data=["papers"],
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>%{customdata[0]:,} papers<extra></extra>",
        textinfo="label+value",
        marker={"line": {"color": _CANVAS, "width": 1.5}},
        insidetextfont={"color": _CANVAS, "size": 11},
    )
    fig.update_layout(margin={"t": 52, "l": 10, "r": 10, "b": 10})
    return apply_research_layout(fig, height=520, legend=False)


def make_research_bloom(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Research Bloom")
    counts = papers["topic_label"].value_counts().head(16).rename_axis("topic_label").reset_index(name="paper_count")
    growth = _recent_growth(papers)
    data = counts.merge(growth[["topic_label", "growth_pp"]], on="topic_label", how="left").fillna({"growth_pp": 0})
    theta = np.linspace(0, 360, len(data), endpoint=False)
    color_values = data["growth_pp"].clip(-12, 12)
    fig = go.Figure(
        go.Barpolar(
            r=data["paper_count"],
            theta=theta,
            width=[360 / max(len(data), 1) * 0.82] * len(data),
            marker={
                "color": color_values,
                "colorscale": CORAL_SCALE,
                "cmin": -12,
                "cmax": 12,
                "line": {"color": _CANVAS, "width": 1},
                "colorbar": {"title": "Growth pp", "thickness": 12, "len": 0.62},
            },
            text=data["topic_label"],
            customdata=data[["growth_pp"]],
            hovertemplate="%{text}<br>%{r:,} papers<br>%{customdata[0]:+.1f} pp recent growth<extra></extra>",
        )
    )
    fig.update_layout(
        title="Research Bloom · topic petals by scale and growth",
        polar={
            "bgcolor": f"rgba(250, 249, 245, 0.35)",
            "angularaxis": {"visible": False},
            "radialaxis": {"visible": False},
        },
    )
    return apply_research_layout(fig, height=520, legend=False)


def make_metadata_weather(papers: pd.DataFrame) -> go.Figure:
    data = metadata_weather_table(papers)
    if data.empty:
        return empty_figure("Metadata Weather")
    colors = {"stormy": "#9b7bb8", "cloudy": "#5db8a6", "bright": "#e8a55a", "sunny": "#cc785c"}
    symbols = {"stormy": "x", "cloudy": "circle", "bright": "diamond", "sunny": "star"}
    fig = go.Figure()
    for weather, frame in data.groupby("weather"):
        fig.add_trace(
            go.Scatter(
                x=frame["year"],
                y=frame["quality_score"] * 100,
                mode="markers+text",
                name=weather.title(),
                text=[{"stormy": "⛈", "cloudy": "☁", "bright": "◐", "sunny": "☀"}.get(weather, "•")] * len(frame),
                textposition="middle center",
                marker={
                    "size": 34,
                    "symbol": symbols.get(weather, "circle"),
                    "color": colors.get(weather, TOPIC_COLORS[0]),
                    "opacity": 0.84,
                    "line": {"color": _CANVAS, "width": 1},
                },
                customdata=frame[["institution_coverage", "country_coverage", "confidence", "papers"]],
                hovertemplate=(
                    "%{x}<br>Quality %{y:.1f}%<br>"
                    "Institution %{customdata[0]:.1%}<br>"
                    "Country %{customdata[1]:.1%}<br>"
                    "Confidence %{customdata[2]:.1%}<br>"
                    "%{customdata[3]:,} papers<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="Metadata Weather · quality climate by year",
        yaxis={"range": [0, 105], "ticksuffix": "%"},
        xaxis_title="Year",
        yaxis_title="Quality score",
    )
    return apply_research_layout(fig, height=430)


def make_paper_universe(papers: pd.DataFrame, max_points: int = 3500) -> go.Figure:
    points = paper_universe_points(papers, max_points=max_points)
    if points.empty:
        return empty_figure("Paper Universe")
    hover_data: dict = {"x": False, "y": False}
    for column in ["year", "authors_text", "countries_text", "institutions_text"]:
        if column in points.columns:
            hover_data[column] = True

    if "affiliation_confidence" in points.columns:
        points = points.copy()
        points["affiliation_confidence"] = points["affiliation_confidence"].fillna(0.0).clip(lower=0.0)
        size_col = "affiliation_confidence" if points["affiliation_confidence"].gt(0).any() else None
        if size_col:
            hover_data["affiliation_confidence"] = ":.2f"
    else:
        size_col = None

    custom_data_cols = ["year"] if "year" in points.columns else None

    fig = px.scatter(
        points, x="x", y="y",
        color="topic_label" if "topic_label" in points.columns else None,
        size=size_col,
        hover_name="title" if "title" in points.columns else None,
        hover_data=hover_data,
        custom_data=custom_data_cols,
        color_discrete_sequence=TOPIC_COLORS,
        title="Paper Universe · sampled title/topic starfield",
    )
    fig.update_traces(marker={"opacity": 0.58, "line": {"width": 0}})
    fig.update_layout(xaxis={"visible": False}, yaxis={"visible": False})
    return apply_research_layout(fig, height=560, legend=True)


def make_topic_dna(papers: pd.DataFrame) -> go.Figure:
    data = topic_dna_table(papers)
    if data.empty:
        return empty_figure("Topic DNA")
    topics = data["topic_label"].drop_duplicates().tolist()
    color_map = {topic: TOPIC_COLORS[idx % len(TOPIC_COLORS)] for idx, topic in enumerate(topics)}
    fig = go.Figure()
    for topic, frame in data.groupby("topic_label", sort=False):
        fig.add_trace(
            go.Bar(
                x=frame["year"],
                y=frame["topic_share"] * 100,
                base=frame["start"] * 100,
                width=0.86,
                name=topic,
                marker={"color": color_map[topic], "line": {"width": 0}},
                customdata=frame[["paper_count"]],
                hovertemplate="%{fullData.name}<br>%{x}<br>%{y:.1f}% share<br>%{customdata[0]:,} papers<extra></extra>",
            )
        )
    fig.update_layout(
        title="Topic DNA · yearly research genome barcode",
        barmode="stack",
        xaxis_title="Year",
        yaxis={"range": [0, 100], "ticksuffix": "%"},
        yaxis_title="Topic composition",
    )
    return apply_research_layout(fig, height=500)
