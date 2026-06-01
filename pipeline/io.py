from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from pipeline.config import RAW_DIR


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def raw_file(venue: str, year: int) -> Path:
    return RAW_DIR / f"{venue}_{year}.jsonl"


def load_raw_papers(venue: str | None = None) -> pd.DataFrame:
    pattern = f"{venue}_*.jsonl" if venue else "*.jsonl"
    rows: list[dict] = []
    for path in sorted(RAW_DIR.glob(pattern)):
        rows.extend(read_jsonl(path))
    if not rows:
        return pd.DataFrame(
            columns=[
                "venue",
                "year",
                "paper_id",
                "title",
                "authors",
                "abstract",
                "url",
                "pdf_url",
                "doi",
                "source",
            ]
        )
    return pd.DataFrame(rows)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
