from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

_LOG = logging.getLogger(__name__)

# Data lives next to this file (app/data/processed/) when deployed
PROCESSED_DIR = Path(__file__).resolve().parent / "data" / "processed"

REQUIRED_FILES = {
    "papers": "papers.parquet",
    "topic_year": "topic_year.parquet",
    "country_year": "country_year.parquet",
    "institution_year": "institution_year.parquet",
    "topic_edges": "topic_edges.parquet",
    "forecast": "forecast.parquet",
    "coverage": "coverage.parquet",
}


def load_data() -> dict[str, pd.DataFrame]:
    missing = [f for f in REQUIRED_FILES.values() if not (PROCESSED_DIR / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing processed data files: {missing}. "
            f"Expected in {PROCESSED_DIR}"
        )
    return {name: pd.read_parquet(PROCESSED_DIR / file_name) for name, file_name in REQUIRED_FILES.items()}
