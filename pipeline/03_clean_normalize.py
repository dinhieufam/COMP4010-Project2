from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet


def as_list(value: Any, default: str = "Unknown") -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
    elif value is None or (isinstance(value, float) and pd.isna(value)):
        cleaned = []
    else:
        cleaned = [str(value).strip()]
    return cleaned or [default]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def main() -> None:
    ensure_dirs()
    path = INTERIM_DIR / "enriched.parquet"
    if not path.exists():
        raise RuntimeError("Missing data/interim/enriched.parquet. Run 02_enrich_openalex.py first.")
    df = pd.read_parquet(path)
    df["title"] = df["title"].apply(clean_text)
    df["abstract"] = df["abstract"].fillna("").apply(clean_text)
    df["authors"] = df["authors"].apply(as_list)
    df["institutions"] = df["institutions"].apply(as_list)
    df["countries"] = df["countries"].apply(as_list)
    df["citation_count"] = pd.to_numeric(df["citation_count"], errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["has_abstract"] = df["abstract"].str.len() > 0
    df["metadata_quality_flag"] = df.apply(
        lambda row: "usable" if row["title"] and row["authors"] != ["Unknown"] else "needs_review",
        axis=1,
    )
    write_parquet(df, INTERIM_DIR / "clean.parquet")
    print(f"Wrote {len(df)} normalized records.")


if __name__ == "__main__":
    main()
