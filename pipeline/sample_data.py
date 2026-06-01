from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pandas as pd

from pipeline.config import PROCESSED_DIR, RAW_DIR, REPORTS_DIR, ensure_dirs
from pipeline.io import write_jsonl


TOPICS = {
    0: ("Optimization", "optimization, gradient, convex, learning"),
    1: ("Neural Networks", "neural networks, representation, deep learning"),
    2: ("Probabilistic Models", "bayesian, inference, graphical models"),
    3: ("Reinforcement Learning", "reinforcement learning, policy, control"),
    4: ("Language Models", "language, transformers, large models"),
    5: ("Vision and Multimodal", "vision, image, multimodal, diffusion"),
}


def sample_raw_rows() -> list[dict]:
    countries = [["United States"], ["United Kingdom"], ["Canada"], ["China"], ["Germany"], ["Unknown"]]
    institutions = [
        ["Stanford University"],
        ["University of Oxford"],
        ["University of Toronto"],
        ["Tsinghua University"],
        ["Max Planck Institute"],
        ["Unknown"],
    ]
    rows: list[dict] = []
    for idx, year in enumerate(range(1987, 2026)):
        topic_id = idx % len(TOPICS)
        label = TOPICS[topic_id][0]
        rows.append(
            {
                "venue": "neurips",
                "year": year,
                "paper_id": f"neurips_{year}_sample_{idx}",
                "title": f"{label} methods for AI research in {year}",
                "authors": [f"Author {idx + 1}", f"Collaborator {idx + 1}"],
                "abstract": f"This paper studies {label.lower()} for machine learning systems and evaluation.",
                "url": f"https://proceedings.neurips.cc/paper_files/paper/{year}",
                "pdf_url": None,
                "doi": None,
                "doi_source": "none",
                "doi_match_score": 0.0,
                "source": "sample",
                "citation_count": max(0, (2026 - year) * (topic_id + 2)),
                "citation_source": "sample",
                "institutions": institutions[idx % len(institutions)],
                "countries": countries[idx % len(countries)],
                "concepts": [label, "Machine learning"],
                "openalex_id": f"https://openalex.org/S{idx}",
                "openalex_match_method": "sample",
                "openalex_match_score": 1.0,
                "has_abstract": True,
                "metadata_quality_flag": "sample",
                "topic_id": topic_id,
                "topic_label": label,
                "secondary_topic_ids": [],
                "secondary_topic_labels": [],
                "topic_score": 8.0,
                "secondary_topic_score": 0.0,
                "topic_review_flag": False,
                "topic_probability": 1.0,
                "topic_keywords": TOPICS[topic_id][1],
            }
        )
    return rows


def processed_frames() -> dict[str, pd.DataFrame]:
    papers = pd.DataFrame(sample_raw_rows())
    papers["authors_text"] = papers["authors"].apply(lambda values: ", ".join(values))
    papers["countries_text"] = papers["countries"].apply(lambda values: ", ".join(values))
    papers["institutions_text"] = papers["institutions"].apply(lambda values: ", ".join(values))
    papers["secondary_topic_labels_text"] = papers["secondary_topic_labels"].apply(
        lambda values: ", ".join(values) if values else "Unknown"
    )
    papers["citation_per_year"] = papers.apply(
        lambda row: row["citation_count"] / max(1, 2026 - int(row["year"])), axis=1
    )

    topic_year = (
        papers.groupby(["venue", "year", "topic_id", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"), avg_citations=("citation_count", "mean"))
        .sort_values(["year", "topic_label"])
    )
    country_year = (
        papers.explode("countries")
        .rename(columns={"countries": "country"})
        .groupby(["venue", "year", "country"], as_index=False)
        .agg(paper_count=("paper_id", "count"), citation_count=("citation_count", "sum"))
    )
    institution_year = (
        papers.explode("institutions")
        .rename(columns={"institutions": "institution"})
        .groupby(["venue", "year", "institution"], as_index=False)
        .agg(paper_count=("paper_id", "count"), citation_count=("citation_count", "sum"))
    )
    citation_impact = (
        papers.groupby(["venue", "year", "topic_id", "topic_label"], as_index=False)
        .agg(
            paper_count=("paper_id", "count"),
            avg_citations=("citation_count", "mean"),
            normalized_impact=("citation_per_year", "mean"),
        )
    )
    topic_summary = topic_year.groupby(["topic_id", "topic_label"], as_index=False)["paper_count"].sum()
    edge_rows = []
    for left, right in combinations(topic_summary.itertuples(index=False), 2):
        distance = abs(int(left.topic_id) - int(right.topic_id))
        weight = round(1 / (distance + 1), 3)
        if weight >= 0.2:
            edge_rows.append(
                {
                    "source_topic_id": int(left.topic_id),
                    "source_topic_label": left.topic_label,
                    "target_topic_id": int(right.topic_id),
                    "target_topic_label": right.topic_label,
                    "weight": weight,
                }
            )
    forecast_rows = []
    for topic in topic_year["topic_label"].unique():
        topic_df = topic_year[topic_year["topic_label"] == topic]
        last_year = int(topic_df["year"].max())
        last_count = float(topic_df["paper_count"].tail(3).mean())
        topic_id = int(topic_df["topic_id"].iloc[0])
        for year in range(last_year + 1, last_year + 3):
            forecast_rows.append(
                {
                    "venue": "neurips",
                    "year": year,
                    "topic_id": topic_id,
                    "topic_label": topic,
                    "forecast_count": max(0, last_count),
                    "lower": max(0, last_count - 1),
                    "upper": last_count + 1,
                }
            )
    coverage = (
        papers.groupby(["venue", "year"], as_index=False)
        .agg(
            scraped_count=("paper_id", "count"),
            index_count=("paper_id", "count"),
            external_count=("paper_id", "count"),
            abstract_coverage=("has_abstract", "mean"),
            openalex_match_rate=("openalex_match_score", lambda s: float((s > 0).mean())),
            doi_coverage=("doi", lambda s: float(s.notna().mean())),
            citation_coverage=("citation_count", lambda s: float(s.gt(0).mean())),
        )
        .assign(count_status="sample")
    )
    app_papers = papers[
        [
            "venue",
            "year",
            "paper_id",
            "title",
            "authors_text",
            "topic_id",
            "topic_label",
            "secondary_topic_labels_text",
            "topic_score",
            "secondary_topic_score",
            "topic_review_flag",
            "citation_count",
            "citation_source",
            "doi",
            "doi_source",
            "countries_text",
            "institutions_text",
            "url",
            "pdf_url",
            "openalex_match_method",
            "has_abstract",
        ]
    ].copy()
    return {
        "papers": app_papers,
        "topic_year": topic_year,
        "country_year": country_year,
        "institution_year": institution_year,
        "citation_impact": citation_impact,
        "topic_edges": pd.DataFrame(edge_rows),
        "forecast": pd.DataFrame(forecast_rows),
        "coverage": coverage,
    }


def write_sample_raw(raw_dir: Path = RAW_DIR) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for row in sample_raw_rows():
        write_jsonl(raw_dir / f"neurips_{row['year']}.jsonl", [row])


def write_sample_processed(processed_dir: Path = PROCESSED_DIR) -> None:
    ensure_dirs()
    frames = processed_frames()
    processed_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(processed_dir / f"{name}.parquet", index=False)
    frames["coverage"].to_csv(REPORTS_DIR / "coverage.csv", index=False)
