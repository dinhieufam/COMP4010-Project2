from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import DEFAULT_MAILTO, INTERIM_DIR, OPENALEX_BASE_URL, ensure_dirs
from pipeline.io import load_raw_papers, write_parquet

try:
    import requests_cache
except ImportError:  # pragma: no cover
    requests_cache = None


DEFAULT_NEURIPS_SOURCE_ID = "S4306420609"
NEURIPS_HASH_RE = re.compile(r"/(?:hash|file)/([0-9a-f]{32})", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Best-effort OpenAlex enrichment.")
    parser.add_argument("--offline", action="store_true", help="Skip API calls and keep unmatched papers.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for quick development runs.")
    parser.add_argument("--mailto", default=os.getenv("OPENALEX_MAILTO", DEFAULT_MAILTO))
    parser.add_argument("--workers", type=int, default=6, help="Concurrent OpenAlex lookups.")
    parser.add_argument("--candidates", type=int, default=1, help="OpenAlex candidates to inspect per title search.")
    parser.add_argument("--checkpoint-every", type=int, default=1000, help="Write a partial parquet every N rows.")
    parser.add_argument("--resume", action="store_true", help="Reuse data/interim/enriched.partial.parquet if present.")
    parser.add_argument(
        "--bulk-source-id",
        default=DEFAULT_NEURIPS_SOURCE_ID,
        help="Pull OpenAlex works for a source id once, then match locally by title/year.",
    )
    parser.add_argument("--title-search", action="store_true", help="Use per-title OpenAlex search instead of bulk source pull.")
    return parser.parse_args()


def normalize_list(value: Any) -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [str(value)]


def make_session() -> requests.Session:
    if requests_cache is not None:
        session = requests_cache.CachedSession(
            str(INTERIM_DIR / "openalex_http_cache"),
            expire_after=60 * 60 * 24 * 90,
        )
    else:
        session = requests.Session()
    session.headers.update({"User-Agent": "COMP4010 AI Conference Research Observatory/1.0"})
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
    text = str(value).strip().lower()
    if not text:
        return None
    text = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", text)
    return match.group(0).rstrip(".,;)]}") if match else None


def neurips_hash(value: Any) -> str | None:
    text = str(value or "")
    match = NEURIPS_HASH_RE.search(text)
    if match:
        return match.group(1).lower()
    match = re.search(r"neurips_\d{4}_([0-9a-f]{32})", text, flags=re.I)
    return match.group(1).lower() if match else None


def work_hashes(work: dict) -> set[str]:
    hashes: set[str] = set()
    for location in work.get("locations", []) or []:
        for key in ("landing_page_url", "pdf_url"):
            extracted = neurips_hash(location.get(key))
            if extracted:
                hashes.add(extracted)
    primary = work.get("primary_location") or {}
    for key in ("landing_page_url", "pdf_url"):
        extracted = neurips_hash(primary.get(key))
        if extracted:
            hashes.add(extracted)
    return hashes


def surname(value: str) -> str:
    parts = re.findall(r"[A-Za-z][A-Za-z'-]+", str(value))
    return parts[-1].lower() if parts else ""


def paper_surnames(row: dict) -> set[str]:
    return {surname(author) for author in normalize_list(row.get("authors")) if surname(author)}


def work_surnames(work: dict) -> set[str]:
    names = []
    for authorship in work.get("authorships", []):
        author = authorship.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    return {surname(name) for name in names if surname(name)}


def author_overlap_score(row: dict, work: dict) -> float:
    left = paper_surnames(row)
    right = work_surnames(work)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def search_openalex(
    session: requests.Session, title: str, year: int, mailto: str, candidates: int = 1
) -> tuple[dict | None, float]:
    params = {
        "search": title,
        "filter": f"publication_year:{year}",
        "per-page": max(1, min(candidates, 10)),
        "mailto": mailto,
    }
    response = None
    for attempt in range(4):
        response = session.get(OPENALEX_BASE_URL, params=params, timeout=30)
        if response.status_code == 429:
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        break
    if response is None:
        return None, 0.0
    results = response.json().get("results", [])
    best_work = None
    best_score = 0.0
    for work in results:
        score = title_similarity(title, work.get("display_name", ""))
        if score > best_score:
            best_work = work
            best_score = score
    if best_score < 0.86:
        return None, best_score
    return best_work, best_score


def extract_enrichment(work: dict | None, match_score: float = 0.0, match_method: str = "title_year") -> dict:
    if not work:
        return {
            "openalex_id": None,
            "doi": None,
            "institutions": ["Unknown"],
            "institution_rors": ["Unknown"],
            "countries": ["Unknown"],
            "concepts": [],
            "openalex_match_method": "unmatched",
            "openalex_match_score": 0.0,
            "openalex_title_score": match_score,
            "affiliation_source": "none",
            "affiliation_confidence": 0.0,
        }

    institutions: set[str] = set()
    institution_rors: set[str] = set()
    countries: set[str] = set()
    for authorship in work.get("authorships", []):
        for inst in authorship.get("institutions", []):
            if inst.get("display_name"):
                institutions.add(inst["display_name"])
            if inst.get("ror"):
                institution_rors.add(inst["ror"])
            if inst.get("country_code"):
                countries.add(inst["country_code"])

    concepts = [concept.get("display_name", "") for concept in work.get("concepts", [])[:8]]
    return {
        "openalex_id": work.get("id"),
        "doi": normalize_doi(work.get("doi")),
        "institutions": sorted(institutions) or ["Unknown"],
        "institution_rors": sorted(institution_rors) or ["Unknown"],
        "countries": sorted(countries) or ["Unknown"],
        "concepts": [concept for concept in concepts if concept],
        "openalex_match_method": match_method,
        "openalex_match_score": match_score,
        "openalex_title_score": match_score,
        "affiliation_source": match_method if institutions else "none",
        "affiliation_confidence": 1.0 if institutions and match_method in {"openalex_hash", "openalex_doi"} else (0.86 if institutions else 0.0),
    }


def fetch_bulk_source_works(source_id: str, mailto: str) -> list[dict]:
    session = make_session()
    cursor = "*"
    works: list[dict] = []
    while cursor:
        response = None
        params = {
            "filter": f"locations.source.id:{source_id}",
            "per-page": 200,
            "cursor": cursor,
            "mailto": mailto,
        }
        for attempt in range(6):
            response = session.get(OPENALEX_BASE_URL, params=params, timeout=60)
            if response.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            break
        if response is None:
            break
        payload = response.json()
        works.extend(payload.get("results", []))
        next_cursor = payload.get("meta", {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return works


def build_bulk_index(works: list[dict]) -> tuple[dict[int, list[dict]], dict[str, dict]]:
    by_year: dict[int, list[dict]] = {}
    by_hash: dict[str, dict] = {}
    for work in works:
        year = work.get("publication_year")
        if year is None:
            continue
        by_year.setdefault(int(year), []).append(work)
        for extracted_hash in work_hashes(work):
            by_hash.setdefault(extracted_hash, work)
    return by_year, by_hash


def best_bulk_match(row: dict, by_year: dict[int, list[dict]], by_hash: dict[str, dict]) -> tuple[dict | None, float, str]:
    for key in ("url", "pdf_url", "paper_id"):
        extracted_hash = neurips_hash(row.get(key))
        if extracted_hash and extracted_hash in by_hash:
            return by_hash[extracted_hash], 1.0, "openalex_hash"

    candidates = by_year.get(int(row["year"]), [])
    row_doi = normalize_doi(row.get("doi"))
    if row_doi:
        for work in candidates:
            if normalize_doi(work.get("doi")) == row_doi:
                return work, 1.0, "openalex_doi"

    best_work = None
    best_score = 0.0
    best_author_overlap = 0.0
    for work in candidates:
        score = title_similarity(str(row["title"]), work.get("display_name", ""))
        overlap = author_overlap_score(row, work)
        if score > best_score:
            best_work = work
            best_score = score
            best_author_overlap = overlap
    if best_score >= 0.90:
        return best_work, best_score, "openalex_title"
    if best_score >= 0.82 and best_author_overlap >= 0.50:
        return best_work, best_score, "openalex_title_author"
    if best_score >= 0.80 and best_author_overlap >= 0.34:
        return best_work, best_score, "openalex_title_author"
    if best_score < 0.90:
        return None, best_score, "unmatched"
    return best_work, best_score, "openalex_title"


def enrich_row(row: dict, mailto: str, offline: bool, candidates: int = 1) -> dict:
    work = None
    match_score = 0.0
    if not offline:
        session = make_session()
        try:
            work, match_score = search_openalex(
                session, str(row["title"]), int(row["year"]), mailto, candidates
            )
        except requests.RequestException as exc:
            print(f"OpenAlex lookup failed for {row.get('paper_id')}: {exc}")
    enriched = {**row, **extract_enrichment(work, match_score)}
    enriched["authors"] = normalize_list(enriched.get("authors"))
    enriched["has_abstract"] = bool(str(enriched.get("abstract") or "").strip())
    enriched["metadata_quality_flag"] = "matched" if enriched["openalex_id"] else "openalex_unmatched"
    enriched["institution_coverage"] = enriched["institutions"] != ["Unknown"]
    enriched["country_coverage"] = enriched["countries"] != ["Unknown"]
    return enriched


def enrich_from_bulk(papers: pd.DataFrame, source_id: str, mailto: str) -> pd.DataFrame:
    works = fetch_bulk_source_works(source_id, mailto)
    print(f"Fetched {len(works)} OpenAlex works for source {source_id}.")
    by_year, by_hash = build_bulk_index(works)
    print(f"Indexed {sum(len(values) for values in by_year.values())} works by year and {len(by_hash)} by NeurIPS URL hash.")
    rows = []
    for row in tqdm(papers.to_dict("records"), desc="Bulk matching"):
        work, match_score, match_method = best_bulk_match(row, by_year, by_hash)
        enriched = {**row, **extract_enrichment(work, match_score, match_method)}
        enriched["authors"] = normalize_list(enriched.get("authors"))
        enriched["has_abstract"] = bool(str(enriched.get("abstract") or "").strip())
        enriched["metadata_quality_flag"] = "matched" if enriched["openalex_id"] else "openalex_unmatched"
        enriched["institution_coverage"] = enriched["institutions"] != ["Unknown"]
        enriched["country_coverage"] = enriched["countries"] != ["Unknown"]
        rows.append(enriched)
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    ensure_dirs()
    papers = load_raw_papers()
    if papers.empty:
        raise RuntimeError("No raw JSONL files found. Run pipeline/01_scrape.py or pipeline/00_seed_sample.py first.")
    if args.limit:
        papers = papers.head(args.limit).copy()

    if args.bulk_source_id and not args.title_search and not args.offline:
        output = enrich_from_bulk(papers, args.bulk_source_id, args.mailto)
        output = output.sort_values(["year", "paper_id"]).reset_index(drop=True)
        write_parquet(output, INTERIM_DIR / "enriched.parquet")
        write_parquet(output, INTERIM_DIR / "enriched.partial.parquet")
        print(f"Wrote {len(output)} enriched records.")
        return

    partial_path = INTERIM_DIR / "enriched.partial.parquet"
    completed: dict[str, dict] = {}
    if args.resume and partial_path.exists():
        partial = pd.read_parquet(partial_path)
        completed = {str(row["paper_id"]): row for row in partial.to_dict("records")}
        print(f"Resuming from {len(completed)} previously enriched records.")

    rows = list(completed.values())
    pending = [row for row in papers.to_dict("records") if str(row["paper_id"]) not in completed]
    if args.offline or args.workers <= 1:
        for row in tqdm(pending, desc="Enriching"):
            rows.append(enrich_row(row, args.mailto, args.offline, args.candidates))
            if len(rows) % args.checkpoint_every == 0:
                write_parquet(pd.DataFrame(rows), partial_path)
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(enrich_row, row, args.mailto, False, args.candidates)
                for row in pending
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Enriching"):
                rows.append(future.result())
                if len(rows) % args.checkpoint_every == 0:
                    write_parquet(pd.DataFrame(rows), partial_path)

    output = pd.DataFrame(rows)
    output = output.sort_values(["year", "paper_id"]).reset_index(drop=True)
    write_parquet(output, INTERIM_DIR / "enriched.parquet")
    write_parquet(output, partial_path)
    print(f"Wrote {len(output)} enriched records.")


if __name__ == "__main__":
    main()
