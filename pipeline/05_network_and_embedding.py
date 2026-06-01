from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet


def keyword_set(value: str) -> set[str]:
    return {part.strip().lower() for part in str(value).split(",") if part.strip()}


def main() -> None:
    ensure_dirs()
    path = INTERIM_DIR / "topics.parquet"
    if not path.exists():
        raise RuntimeError("Missing data/interim/topics.parquet. Run 04_topic_modeling.py first.")
    papers = pd.read_parquet(path)
    topics = (
        papers.groupby(["topic_id", "topic_label"], as_index=False)
        .agg(topic_keywords=("topic_keywords", "first"), paper_count=("paper_id", "count"))
        .sort_values("paper_count", ascending=False)
    )

    edge_rows = []
    for left, right in combinations(topics.to_dict("records"), 2):
        left_words = keyword_set(left["topic_keywords"])
        right_words = keyword_set(right["topic_keywords"])
        union = left_words | right_words
        similarity = len(left_words & right_words) / len(union) if union else 0.0
        size_weight = min(left["paper_count"], right["paper_count"]) / max(left["paper_count"], right["paper_count"], 1)
        weight = round(max(similarity, 0.15 * size_weight), 3)
        if weight >= 0.05:
            edge_rows.append(
                {
                    "source_topic_id": int(left["topic_id"]),
                    "source_topic_label": left["topic_label"],
                    "target_topic_id": int(right["topic_id"]),
                    "target_topic_label": right["topic_label"],
                    "weight": weight,
                }
            )

    write_parquet(pd.DataFrame(edge_rows), INTERIM_DIR / "topic_edges.parquet")
    print(f"Wrote {len(edge_rows)} topic edges.")


if __name__ == "__main__":
    main()
