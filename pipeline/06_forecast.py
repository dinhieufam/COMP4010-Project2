from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet


def forecast_topic(topic_df: pd.DataFrame, horizon: int = 2) -> list[dict]:
    topic_df = topic_df.sort_values("year")
    years = topic_df["year"].astype(float).to_numpy()
    counts = topic_df["paper_count"].astype(float).to_numpy()
    if len(topic_df) >= 2 and counts.sum() > 0:
        slope, intercept = np.polyfit(years, counts, 1)
        residual = counts - (slope * years + intercept)
        spread = float(np.std(residual)) if len(residual) > 1 else 1.0
    else:
        slope, intercept, spread = 0.0, float(counts[-1] if len(counts) else 0), 1.0
    rows = []
    for year in range(int(years.max()) + 1, int(years.max()) + horizon + 1):
        estimate = max(0.0, slope * year + intercept)
        rows.append(
            {
                "venue": topic_df["venue"].iloc[0],
                "year": year,
                "topic_id": int(topic_df["topic_id"].iloc[0]),
                "topic_label": topic_df["topic_label"].iloc[0],
                "forecast_count": estimate,
                "lower": max(0.0, estimate - 1.96 * spread),
                "upper": estimate + 1.96 * spread,
            }
        )
    return rows


def main() -> None:
    ensure_dirs()
    path = INTERIM_DIR / "topics.parquet"
    if not path.exists():
        raise RuntimeError("Missing data/interim/topics.parquet. Run 04_topic_modeling.py first.")
    papers = pd.read_parquet(path)
    topic_year = (
        papers.groupby(["venue", "year", "topic_id", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
    )
    rows: list[dict] = []
    for _, topic_df in topic_year.groupby(["venue", "topic_id", "topic_label"], dropna=False):
        rows.extend(forecast_topic(topic_df))
    write_parquet(pd.DataFrame(rows), INTERIM_DIR / "forecast.parquet")
    print(f"Wrote {len(rows)} forecast rows.")


if __name__ == "__main__":
    main()
