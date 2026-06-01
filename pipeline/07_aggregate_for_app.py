from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR, ensure_dirs
from pipeline.io import write_parquet


def join_text(values: object) -> str:
    if hasattr(values, "tolist"):
        values = values.tolist()
    if isinstance(values, (list, tuple, set)):
        return ", ".join(str(value) for value in values if str(value).strip()) or "Unknown"
    if values is None or (isinstance(values, float) and pd.isna(values)):
        return "Unknown"
    return str(values)


def count_raw_records() -> pd.DataFrame:
    rows = []
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        stem = path.stem
        try:
            venue, year = stem.rsplit("_", 1)
            with path.open("r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
            rows.append({"venue": venue, "year": int(year), "scraped_count": count})
        except ValueError:
            continue
    return pd.DataFrame(rows)


def main() -> None:
    ensure_dirs()
    topics_path = INTERIM_DIR / "topics.parquet"
    if not topics_path.exists():
        raise RuntimeError("Missing data/interim/topics.parquet. Run 04_topic_modeling.py first.")

    papers = pd.read_parquet(topics_path)
    papers["authors_text"] = papers["authors"].apply(join_text)
    papers["countries_text"] = papers["countries"].apply(join_text)
    papers["institutions_text"] = papers["institutions"].apply(join_text)
    papers["secondary_topic_labels_text"] = papers.get("secondary_topic_labels", pd.Series([[]] * len(papers))).apply(join_text)
    papers["citation_count"] = pd.to_numeric(papers["citation_count"], errors="coerce").fillna(0).clip(lower=0)
    for column, default in (
        ("doi", None),
        ("doi_source", "none"),
        ("citation_source", "none"),
        ("topic_score", 0.0),
        ("secondary_topic_score", 0.0),
        ("topic_review_flag", False),
    ):
        if column not in papers.columns:
            papers[column] = default
    latest_year = max(int(papers["year"].max()), 2026)
    papers["citation_per_year"] = papers.apply(
        lambda row: row["citation_count"] / max(1, latest_year - int(row["year"]) + 1), axis=1
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

    edge_path = INTERIM_DIR / "topic_edges.parquet"
    forecast_path = INTERIM_DIR / "forecast.parquet"
    topic_edges = pd.read_parquet(edge_path) if edge_path.exists() else pd.DataFrame()
    forecast = pd.read_parquet(forecast_path) if forecast_path.exists() else pd.DataFrame()

    raw_counts = count_raw_records()
    coverage = (
        papers.groupby(["venue", "year"], as_index=False)
        .agg(
            abstract_coverage=("has_abstract", "mean"),
            openalex_match_rate=("openalex_match_score", lambda s: float((pd.to_numeric(s, errors="coerce").fillna(0) > 0).mean())),
            doi_coverage=("doi", lambda s: float(s.notna().mean())),
            citation_coverage=("citation_count", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0).gt(0).mean())),
            index_count=("paper_id", "count"),
            external_count=("paper_id", "count"),
        )
        .merge(raw_counts, on=["venue", "year"], how="left")
    )
    coverage["scraped_count"] = coverage["scraped_count"].fillna(coverage["index_count"]).astype(int)
    coverage["count_status"] = coverage.apply(
        lambda row: "ok" if int(row["scraped_count"]) == int(row["index_count"]) else "mismatch",
        axis=1,
    )
    coverage = coverage[
        [
            "venue",
            "year",
            "scraped_count",
            "index_count",
            "external_count",
            "count_status",
            "abstract_coverage",
            "openalex_match_rate",
            "doi_coverage",
            "citation_coverage",
        ]
    ]

    outputs = {
        "papers": app_papers,
        "topic_year": topic_year,
        "country_year": country_year,
        "institution_year": institution_year,
        "citation_impact": citation_impact,
        "topic_edges": topic_edges,
        "forecast": forecast,
        "coverage": coverage,
    }
    for name, frame in outputs.items():
        write_parquet(frame, PROCESSED_DIR / f"{name}.parquet")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(REPORTS_DIR / "coverage.csv", index=False)
    print(f"Wrote processed app data to {Path(PROCESSED_DIR).relative_to(PROCESSED_DIR.parents[1])}.")


if __name__ == "__main__":
    main()
