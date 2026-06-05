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


def join_institutions(values: object) -> str:
    """Join institution names with '|' to avoid ambiguity with comma-in-name institutions."""
    if hasattr(values, "tolist"):
        values = values.tolist()
    if isinstance(values, (list, tuple, set)):
        return " | ".join(str(v) for v in values if str(v).strip()) or "Unknown"
    if values is None or (isinstance(values, float) and pd.isna(values)):
        return "Unknown"
    return str(values)


def has_known(values: object) -> bool:
    if hasattr(values, "tolist"):
        values = values.tolist()
    if isinstance(values, (list, tuple, set)):
        return any(str(value).strip() and str(value).strip() != "Unknown" for value in values)
    if values is None or (isinstance(values, float) and pd.isna(values)):
        return False
    return str(values).strip() != "Unknown"


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
    papers["institutions_text"] = papers["institutions"].apply(join_institutions)
    if "countries_iso2" not in papers.columns:
        papers["countries_iso2"] = papers["countries"]
    if "institution_rors" not in papers.columns:
        papers["institution_rors"] = [["Unknown"] for _ in range(len(papers))]
    if "affiliation_source" not in papers.columns:
        papers["affiliation_source"] = "none"
    if "affiliation_confidence" not in papers.columns:
        papers["affiliation_confidence"] = 0.0
    papers["countries_iso2_text"] = papers["countries_iso2"].apply(join_text)
    papers["institution_rors_text"] = papers["institution_rors"].apply(join_text)
    papers["affiliation_source"] = papers["affiliation_source"].fillna("none").astype(str)
    papers["affiliation_confidence"] = pd.to_numeric(papers["affiliation_confidence"], errors="coerce").fillna(0.0)
    papers["country_known"] = papers["countries"].apply(has_known)
    papers["institution_known"] = papers["institutions"].apply(has_known)
    papers["secondary_topic_labels_text"] = papers.get("secondary_topic_labels", pd.Series([[]] * len(papers))).apply(join_text)
    for column, default in (
        ("topic_score", 0.0),
        ("secondary_topic_score", 0.0),
        ("topic_review_flag", False),
    ):
        if column not in papers.columns:
            papers[column] = default

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
            "countries_text",
            "countries_iso2_text",
            "institutions_text",
            "institution_rors_text",
            "affiliation_source",
            "affiliation_confidence",
            "country_known",
            "institution_known",
            "url",
            "pdf_url",
            "openalex_match_method",
            "has_abstract",
        ]
    ].copy()

    topic_year = (
        papers.groupby(["venue", "year", "topic_id", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values(["year", "topic_label"])
    )
    country_year = (
        papers.explode("countries")
        .rename(columns={"countries": "country"})
        .groupby(["venue", "year", "country"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
    )
    institution_year = (
        papers.explode("institutions")
        .rename(columns={"institutions": "institution"})
        .groupby(["venue", "year", "institution"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
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
            institution_coverage=("institution_known", "mean"),
            country_coverage=("country_known", "mean"),
            affiliation_confidence=("affiliation_confidence", "mean"),
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
            "institution_coverage",
            "country_coverage",
            "affiliation_confidence",
        ]
    ]

    source_breakdown = (
        papers.groupby(["venue", "year", "affiliation_source"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
    )

    outputs = {
        "papers": app_papers,
        "topic_year": topic_year,
        "country_year": country_year,
        "institution_year": institution_year,
        "topic_edges": topic_edges,
        "forecast": forecast,
        "coverage": coverage,
        "affiliation_source_year": source_breakdown,
    }
    for name, frame in outputs.items():
        write_parquet(frame, PROCESSED_DIR / f"{name}.parquet")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(REPORTS_DIR / "coverage.csv", index=False)
    print(f"Wrote processed app data to {Path(PROCESSED_DIR).relative_to(PROCESSED_DIR.parents[1])}.")


if __name__ == "__main__":
    main()
