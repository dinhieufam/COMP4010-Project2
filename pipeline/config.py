from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"
AUDITS_DIR = PROJECT_ROOT / "audits"
CACHE_DIR = DATA_DIR / "http_cache"
TOPIC_TAXONOMY_PATH = PROJECT_ROOT / "pipeline" / "topic_taxonomy.json"

NEURIPS_BASE_URL = "https://proceedings.neurips.cc"
OPENALEX_BASE_URL = "https://api.openalex.org/works"
DEFAULT_MAILTO = "research-observatory@example.com"


def ensure_dirs() -> None:
    for path in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, MANUAL_DIR, AUDITS_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
