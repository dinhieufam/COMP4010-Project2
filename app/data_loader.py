from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

_LOG = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import PROCESSED_DIR
from pipeline.sample_data import write_sample_processed


REQUIRED_FILES = {
    "papers": "papers.parquet",
    "topic_year": "topic_year.parquet",
    "country_year": "country_year.parquet",
    "institution_year": "institution_year.parquet",
    "topic_edges": "topic_edges.parquet",
    "forecast": "forecast.parquet",
    "coverage": "coverage.parquet",
}


def ensure_processed_data() -> None:
    missing = [name for name in REQUIRED_FILES.values() if not (PROCESSED_DIR / name).exists()]
    if missing:
        _LOG.warning(
            "Processed data files not found (%s). Falling back to synthetic sample data. "
            "Run the pipeline (pipeline/00_seed_sample.py through 07_aggregate_for_app.py) "
            "to populate %s.",
            missing,
            str(PROCESSED_DIR),
        )
        write_sample_processed()


def load_data() -> dict[str, pd.DataFrame]:
    ensure_processed_data()
    return {name: pd.read_parquet(PROCESSED_DIR / file_name) for name, file_name in REQUIRED_FILES.items()}
