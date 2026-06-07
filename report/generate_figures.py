from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.charts.theme import TOPIC_COLORS
from app.charts.utils import country_display, explode_tokens


DATA_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "report"

CANVAS = "#ffffff"
INK = "#141413"
MUTED = "#4b5563"
HAIRLINE = "#e5e7eb"
CORAL = "#cc785c"
BLUE = "#4a7fb5"
GREEN = "#6b8e6b"
AMBER = "#e8a55a"
GREY = "#a09d96"

SHORT_TOPIC = {
    "Deep Learning Architectures": "Deep Learning",
    "Natural Language Processing & LLMs": "NLP & LLMs",
    "Computer Vision & Multimodal Learning": "Computer Vision",
    "Reinforcement Learning & Decision Making": "Reinforcement Learning",
    "Generative Models": "Generative Models",
    "Optimization & Learning Algorithms": "Optimization",
    "Data, Evaluation & Benchmarks": "Data & Evaluation",
    "Robustness, Safety & Alignment": "Safety & Alignment",
    "Foundations & Theory": "Theory",
    "Probabilistic Modeling & Bayesian Inference": "Bayesian Methods",
    "Applications & Scientific ML": "Scientific ML",
    "Graph Learning & Network Science": "Graph Learning",
    "Neuroscience & Cognitive Science": "Neuroscience",
    "Fairness, Privacy & Security": "Fairness & Privacy",
    "Robotics & Control": "Robotics",
    "General / Other ML": "Other ML",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": CANVAS,
            "axes.facecolor": CANVAS,
            "savefig.facecolor": CANVAS,
            "font.family": "DejaVu Sans",
            "font.size": 20,
            "axes.labelsize": 24,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "legend.fontsize": 19,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "axes.edgecolor": HAIRLINE,
            "axes.grid": True,
            "grid.color": HAIRLINE,
            "grid.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )


def finish(fig: plt.Figure, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    fig.savefig(
        OUTPUT_DIR / filename,
        dpi=300,
        facecolor=CANVAS,
    )
    plt.close(fig)


def add_event_markers(ax: plt.Axes, ymax: float, labels: bool = True) -> None:
    events = [(2012, "AlexNet"), (2017, "Transformer"), (2022, "ChatGPT")]
    for index, (year, label) in enumerate(events):
        ax.axvline(year, color=GREY, linewidth=0.8, linestyle="--", alpha=0.75)
        if labels:
            ax.text(
                year + 0.15,
                ymax * (0.93 - 0.08 * (index % 2)),
                label,
                color=MUTED,
                fontsize=17,
                rotation=90,
                va="top",
            )


def publication_growth(papers: pd.DataFrame) -> None:
    counts = papers.groupby("year").size().sort_index()
    fig, ax = plt.subplots(figsize=(14, 7.2))
    ax.fill_between(counts.index, counts.values, color=CORAL, alpha=0.14)
    ax.plot(counts.index, counts.values, color=CORAL, linewidth=2.4)
    ax.scatter([counts.index[0], counts.index[-1]], [counts.iloc[0], counts.iloc[-1]], color=CORAL, s=28, zorder=3)
    ax.annotate(
        f"{counts.iloc[0]:,}",
        (counts.index[0], counts.iloc[0]),
        xytext=(8, 12),
        textcoords="offset points",
        color=CORAL,
        fontsize=20,
    )
    ax.annotate(
        f"{counts.iloc[-1]:,}",
        (counts.index[-1], counts.iloc[-1]),
        xytext=(-5, 12),
        textcoords="offset points",
        ha="right",
        color=CORAL,
        fontsize=20,
        fontweight="bold",
    )
    add_event_markers(ax, float(counts.max()))
    ax.set_xlabel("Year")
    ax.set_ylabel("Accepted papers")
    ax.set_xlim(int(counts.index.min()), int(counts.index.max()))
    ax.set_ylim(0, float(counts.max()) * 1.1)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    fig.subplots_adjust(left=0.15, right=0.97, bottom=0.17, top=0.96)
    finish(fig, "publication_growth.png")


def topic_evolution(papers: pd.DataFrame) -> None:
    counts = papers.groupby(["year", "topic_label"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0) * 100
    top_topics = counts.sum().sort_values(ascending=False).head(8).index.tolist()
    plot = shares[top_topics].copy()
    plot["Other topics"] = shares.drop(columns=top_topics).sum(axis=1)
    labels = [SHORT_TOPIC.get(topic, topic) for topic in top_topics] + ["Other topics"]
    colors = TOPIC_COLORS[: len(top_topics)] + [GREY]

    fig, ax = plt.subplots(figsize=(17, 10))
    ax.stackplot(plot.index, plot.T.values, labels=labels, colors=colors, alpha=0.92)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of papers")
    ax.set_xlim(int(plot.index.min()), int(plot.index.max()))
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=3,
        fontsize=18,
        columnspacing=1.4,
        handlelength=1.4,
    )
    fig.subplots_adjust(left=0.14, right=0.98, bottom=0.31, top=0.97)
    finish(fig, "topic_evolution.png")


def topic_three_eras(papers: pd.DataFrame) -> None:
    years = [1987, 2005, 2025]
    counts = papers.groupby(["year", "topic_label"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0) * 100
    top_topics = shares.loc[years].max(axis=0).sort_values(ascending=False).head(8).index.tolist()

    fig, axes = plt.subplots(1, 3, figsize=(25, 9), sharex=True)
    for ax, year in zip(axes, years):
        values = shares.loc[year, top_topics].sort_values()
        labels = [SHORT_TOPIC.get(topic, topic) for topic in values.index]
        colors = [CORAL if value == values.max() else GREY for value in values.values]
        ax.barh(labels, values.values, color=colors)
        ax.set_xlabel(f"Share of papers, {year}")
        ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=17)
        for y_position, value in enumerate(values.values):
            ax.text(value + 0.4, y_position, f"{value:.1f}%", va="center", fontsize=16, color=MUTED)
    max_share = float(shares.loc[years, top_topics].max().max()) * 1.25
    for ax in axes:
        ax.set_xlim(0, max_share)
    fig.subplots_adjust(left=0.14, right=0.96, bottom=0.18, top=0.97, wspace=0.82)
    finish(fig, "topic_three_eras.png")


def geographic_redistribution(papers: pd.DataFrame) -> None:
    countries = explode_tokens(papers, "countries_text", "country")
    countries["country"] = countries["country"].apply(country_display)
    counts = countries.groupby(["year", "country"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0) * 100
    top = counts.sum().sort_values(ascending=False).head(6).index.tolist()
    palette = [CORAL, BLUE, GREEN, AMBER, "#9b7bb8", "#6589b8"]

    fig, ax = plt.subplots(figsize=(14.5, 7.8))
    for country, color in zip(top, palette):
        ax.plot(shares.index, shares[country], label=country, color=color, linewidth=2.1)
    add_event_markers(ax, float(shares[top].max().max()), labels=False)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of country-paper\nparticipations")
    ax.set_xlim(int(shares.index.min()), int(shares.index.max()) + 1)
    ax.set_ylim(0, max(60, float(shares[top].max().max()) * 1.08))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=3,
        fontsize=19,
    )
    fig.subplots_adjust(left=0.15, right=0.96, bottom=0.29, top=0.97)
    finish(fig, "geographic_redistribution.png")


def _clean_institution(value: str) -> str:
    value = str(value).strip().rstrip("0123456789.").strip()
    if value.startswith("arnegie "):
        return "Carnegie Mellon University"
    return value


def institutional_change(institution_year: pd.DataFrame) -> None:
    data = institution_year[institution_year["institution"].ne("Unknown")].copy()
    data["institution"] = data["institution"].map(_clean_institution)

    def top_period(start: int, end: int, n: int = 10) -> pd.Series:
        subset = data[data["year"].between(start, end)]
        return subset.groupby("institution")["paper_count"].sum().sort_values(ascending=False).head(n).sort_values()

    early = top_period(1990, 2000)
    modern = top_period(2021, 2025)
    fig, axes = plt.subplots(1, 2, figsize=(25, 10))

    axes[0].barh(early.index, early.values, color=GREY)
    axes[0].set_xlabel("Accepted papers, 1990–2000")
    axes[0].xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))

    modern_colors = [CORAL if name in {"Google", "Tsinghua University", "University of Hong Kong", "Peking University", "Shanghai Jiao Tong University", "Meta", "Chinese Academy of Sciences"} else GREY for name in modern.index]
    axes[1].barh(modern.index, modern.values, color=modern_colors)
    axes[1].set_xlabel("Accepted papers, 2021–2025")
    axes[1].xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))

    for ax in axes:
        ax.set_ylabel("")
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=18)
    fig.subplots_adjust(left=0.22, right=0.96, bottom=0.17, top=0.97, wspace=0.90)
    finish(fig, "institutional_change.png")


def responsible_ai(papers: pd.DataFrame) -> None:
    topics = {
        "Robustness, Safety & Alignment": (CORAL, "Safety & Alignment"),
        "Fairness, Privacy & Security": (BLUE, "Fairness, Privacy & Security"),
        "Data, Evaluation & Benchmarks": (GREEN, "Data, Evaluation & Benchmarks"),
    }
    counts = papers.groupby(["year", "topic_label"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(14.5, 7.8))
    for topic, (color, label) in topics.items():
        ax.plot(shares.index, shares[topic], label=label, color=color, linewidth=2.3)
    add_event_markers(ax, float(shares[list(topics)].max().max()), labels=False)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of papers")
    ax.set_xlim(int(shares.index.min()), int(shares.index.max()) + 1)
    ax.set_ylim(0, float(shares[list(topics)].max().max()) * 1.12)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
        fontsize=19,
    )
    fig.subplots_adjust(left=0.14, right=0.96, bottom=0.31, top=0.97)
    finish(fig, "responsible_ai.png")


def main() -> None:
    configure_style()
    papers = pd.read_parquet(DATA_DIR / "papers.parquet")
    institution_year = pd.read_parquet(DATA_DIR / "institution_year.parquet")

    publication_growth(papers)
    topic_evolution(papers)
    topic_three_eras(papers)
    geographic_redistribution(papers)
    institutional_change(institution_year)
    responsible_ai(papers)

    for path in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
