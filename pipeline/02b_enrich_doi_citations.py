from __future__ import annotations

import argparse
import os
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import DEFAULT_MAILTO, INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet

try:
    import requests_cache
except ImportError:  # pragma: no cover
    requests_cache = None


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
NEURIPS_CONTAINER_RE = re.compile(
    r"\b(neurips|nips|neural information processing systems)\b", re.I
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cautious DOI and non-OpenAlex citation enrichment."
    )
    parser.add_argument("--input", default=str(INTERIM_DIR / "enriched.parquet"))
    parser.add_argument("--output", default=str(INTERIM_DIR / "enriched.parquet"))
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for probes.")
    parser.add_argument("--mailto", default=os.getenv("CROSSREF_MAILTO", DEFAULT_MAILTO))
    parser.add_argument(
        "--crossref-title-limit",
        type=int,
        default=0,
        help="Maximum rows without DOI to search in Crossref by title. Default 0 because DOI coverage is low and false positives are common.",
    )
    parser.add_argument(
        "--semantic-scholar-limit",
        type=int,
        default=0,
        help="Maximum rows without DOI to search in Semantic Scholar by title. Use with SEMANTIC_SCHOLAR_API_KEY when available.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.12,
        help="Delay between uncached external API calls.",
    )
    return parser.parse_args()


def make_session(cache_name: str) -> requests.Session:
    if requests_cache is not None:
        session = requests_cache.CachedSession(
            str(INTERIM_DIR / cache_name),
            expire_after=60 * 60 * 24 * 90,
        )
    else:
        session = requests.Session()
    session.headers.update(
        {"User-Agent": f"COMP4010 AI Conference Research Observatory/1.0 ({DEFAULT_MAILTO})"}
    )
    return session


def normalize_title(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def normalize_doi(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    match = DOI_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,;)]}").lower()


def has_doi(value: Any) -> bool:
    return normalize_doi(value) is not None


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    sleep: float = 0.12,
) -> dict[str, Any] | None:
    for attempt in range(5):
        response = session.get(url, params=params, headers=headers, timeout=30)
        if response.status_code in {403, 404}:
            return None
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(delay)
            continue
        response.raise_for_status()
        if not getattr(response, "from_cache", False):
            time.sleep(sleep)
        return response.json()
    return None


def crossref_by_doi(
    session: requests.Session, doi: str, mailto: str, sleep: float
) -> dict[str, Any] | None:
    payload = request_json(
        session,
        f"{CROSSREF_WORKS_URL}/{quote(doi, safe='')}",
        params={"mailto": mailto},
        sleep=sleep,
    )
    if not payload:
        return None
    message = payload.get("message", {})
    return {
        "doi": normalize_doi(message.get("DOI")) or doi,
        "citation_count": int(message.get("is-referenced-by-count") or 0),
        "source": "crossref_doi",
        "score": 1.0,
    }


def crossref_title_search(
    session: requests.Session,
    title: str,
    year: int,
    mailto: str,
    sleep: float,
) -> dict[str, Any] | None:
    payload = request_json(
        session,
        CROSSREF_WORKS_URL,
        params={
            "query.bibliographic": title,
            "filter": f"from-pub-date:{year - 1}-01-01,until-pub-date:{year + 1}-12-31",
            "rows": 5,
            "mailto": mailto,
        },
        sleep=sleep,
    )
    if not payload:
        return None

    best: dict[str, Any] | None = None
    best_score = 0.0
    for item in payload.get("message", {}).get("items", []):
        candidate_title = (item.get("title") or [""])[0]
        score = title_similarity(title, candidate_title)
        if score < 0.98:
            continue
        published = item.get("published-print") or item.get("published-online") or {}
        years = published.get("date-parts") or []
        item_year = years[0][0] if years and years[0] else None
        if item_year is not None and abs(int(item_year) - int(year)) > 1:
            continue
        container = " ".join(item.get("container-title") or [])
        if not container or not NEURIPS_CONTAINER_RE.search(container):
            continue
        doi = normalize_doi(item.get("DOI"))
        if doi and score > best_score:
            best_score = score
            best = {
                "doi": doi,
                "citation_count": int(item.get("is-referenced-by-count") or 0),
                "source": "crossref_title",
                "score": score,
            }
    return best


def semantic_scholar_title_search(
    session: requests.Session, title: str, year: int, sleep: float
) -> dict[str, Any] | None:
    headers = {}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    payload = request_json(
        session,
        SEMANTIC_SCHOLAR_SEARCH_URL,
        params={
            "query": title,
            "limit": 5,
            "fields": "title,year,citationCount,externalIds,venue,publicationVenue",
        },
        headers=headers,
        sleep=sleep,
    )
    if not payload:
        return None

    best: dict[str, Any] | None = None
    best_score = 0.0
    for item in payload.get("data", []):
        score = title_similarity(title, item.get("title", ""))
        item_year = item.get("year")
        if score < 0.98 or (item_year is not None and abs(int(item_year) - int(year)) > 1):
            continue
        doi = normalize_doi((item.get("externalIds") or {}).get("DOI"))
        if score > best_score:
            best_score = score
            best = {
                "doi": doi,
                "citation_count": int(item.get("citationCount") or 0),
                "source": "semantic_scholar_title",
                "score": score,
            }
    return best


def apply_candidate(row: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(row)
    if not candidate:
        return row

    if candidate.get("doi") and not has_doi(row.get("doi")):
        row["doi"] = candidate["doi"]
        row["doi_source"] = candidate["source"]
        row["doi_match_score"] = candidate["score"]

    candidate_citations = int(candidate.get("citation_count") or 0)
    current_citations = int(row.get("citation_count") or 0)
    if candidate_citations > current_citations:
        row["citation_count"] = candidate_citations
        row["citation_source"] = candidate["source"]
    return row


def main() -> None:
    args = parse_args()
    ensure_dirs()
    input_path = Path(args.input)
    if not input_path.exists():
        raise RuntimeError(f"Missing {input_path}. Run 02_enrich_openalex.py first.")

    df = pd.read_parquet(input_path)
    if args.limit:
        df = df.head(args.limit).copy()

    for column, default in (
        ("doi_source", "none"),
        ("doi_match_score", 0.0),
        ("citation_source", "openalex"),
    ):
        if column not in df.columns:
            df[column] = default

    df["doi"] = df["doi"].apply(normalize_doi)
    stale_crossref_title = df["citation_source"].eq("crossref_title") & df["doi"].isna()
    df.loc[stale_crossref_title, "citation_count"] = 0
    df.loc[stale_crossref_title, "citation_source"] = "none"
    df.loc[df["doi"].notna() & df["doi_source"].eq("none"), "doi_source"] = "existing"
    df.loc[df["doi"].notna() & df["doi_match_score"].eq(0.0), "doi_match_score"] = 1.0
    df.loc[pd.to_numeric(df["citation_count"], errors="coerce").fillna(0).le(0), "citation_source"] = "none"

    crossref = make_session("crossref_http_cache")
    semantic = make_session("semantic_scholar_http_cache")
    rows: list[dict[str, Any]] = []
    crossref_title_budget = max(0, args.crossref_title_limit)
    semantic_budget = max(0, args.semantic_scholar_limit)

    for row in tqdm(df.to_dict("records"), desc="DOI/citation enrichment"):
        doi = normalize_doi(row.get("doi"))
        candidate = None
        if doi:
            candidate = crossref_by_doi(crossref, doi, args.mailto, args.sleep)
        elif crossref_title_budget > 0:
            candidate = crossref_title_search(
                crossref,
                str(row.get("title") or ""),
                int(row.get("year")),
                args.mailto,
                args.sleep,
            )
            crossref_title_budget -= 1

        row = apply_candidate(row, candidate)
        if not has_doi(row.get("doi")) and semantic_budget > 0:
            s2_candidate = semantic_scholar_title_search(
                semantic,
                str(row.get("title") or ""),
                int(row.get("year")),
                args.sleep,
            )
            row = apply_candidate(row, s2_candidate)
            semantic_budget -= 1
        rows.append(row)

    output = pd.DataFrame(rows).sort_values(["year", "paper_id"]).reset_index(drop=True)
    write_parquet(output, Path(args.output))
    print(
        "Wrote "
        f"{len(output)} rows; DOI coverage={int(output['doi'].notna().sum())}; "
        f"nonzero citations={int(pd.to_numeric(output['citation_count'], errors='coerce').fillna(0).gt(0).sum())}."
    )


if __name__ == "__main__":
    main()
