from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet


OPENREVIEW_API = "https://api2.openreview.net"
CACHE_PATH = INTERIM_DIR / "openreview_profiles.json"
NOTE_CACHE_PATH = INTERIM_DIR / "openreview_notes.json"

COUNTRY_TLD = {
    "edu": "US",
    "gov": "US",
    "mil": "US",
    "com": "US",
    "org": "US",
    "net": "US",
    "ac.uk": "GB",
    "uk": "GB",
    "ca": "CA",
    "cn": "CN",
    "edu.cn": "CN",
    "de": "DE",
    "fr": "FR",
    "jp": "JP",
    "ac.jp": "JP",
    "kr": "KR",
    "ac.kr": "KR",
    "sg": "SG",
    "ch": "CH",
    "nl": "NL",
    "il": "IL",
    "ac.il": "IL",
    "au": "AU",
    "edu.au": "AU",
    "hk": "HK",
    "edu.hk": "HK",
    "in": "IN",
    "ac.in": "IN",
    "it": "IT",
    "es": "ES",
    "se": "SE",
    "dk": "DK",
    "no": "NO",
    "fi": "FI",
    "be": "BE",
    "at": "AT",
    "ie": "IE",
    "br": "BR",
    "mx": "MX",
    "cl": "CL",
    "nz": "NZ",
}

INSTITUTION_COUNTRY_HINTS = {
    "university of oxford": "GB",
    "university of cambridge": "GB",
    "university college london": "GB",
    "imperial college": "GB",
    "eth zurich": "CH",
    "epfl": "CH",
    "university of toronto": "CA",
    "mila": "CA",
    "tsinghua": "CN",
    "peking university": "CN",
    "zhejiang university": "CN",
    "national university of singapore": "SG",
    "kaist": "KR",
    "seoul national": "KR",
    "university of tokyo": "JP",
    "technion": "IL",
    "hebrew university": "IL",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill recent NeurIPS affiliations from OpenReview profiles.")
    parser.add_argument("--years", nargs="*", type=int, default=[2023, 2024, 2025])
    parser.add_argument("--limit-notes", type=int, default=None, help="Development limit per year.")
    parser.add_argument("--limit-profiles", type=int, default=None, help="Development limit for new profile fetches.")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--sleep", type=float, default=0.02)
    return parser.parse_args()


def normalize_title(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def value_of(field: Any) -> Any:
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def as_list(value: Any) -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
    elif value is None or (isinstance(value, float) and pd.isna(value)):
        cleaned = []
    else:
        cleaned = [str(value).strip()]
    return cleaned or ["Unknown"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp.replace(path)


def get_json(session: requests.Session, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(5):
        response = session.get(f"{OPENREVIEW_API}{endpoint}", params=params, timeout=45)
        if response.status_code in {429, 500, 502, 503, 504}:
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    return {}


def fetch_notes_for_year(session: requests.Session, year: int, limit_notes: int | None) -> list[dict[str, Any]]:
    cache = load_json(NOTE_CACHE_PATH)
    key = str(year)
    if key in cache and not limit_notes:
        return cache[key]

    venueid = f"NeurIPS.cc/{year}/Conference"
    notes: list[dict[str, Any]] = []
    offset = 0
    batch_size = 1000
    while True:
        payload = get_json(
            session,
            "/notes",
            {
                "content.venueid": venueid,
                "limit": batch_size,
                "offset": offset,
            },
        )
        batch = payload.get("notes", [])
        if not batch:
            break
        notes.extend(batch)
        if limit_notes and len(notes) >= limit_notes:
            notes = notes[:limit_notes]
            break
        if len(batch) < batch_size:
            break
        offset += batch_size

    if not limit_notes:
        cache[key] = notes
        save_json(NOTE_CACHE_PATH, cache)
    return notes


def note_record(note: dict[str, Any], year: int) -> dict[str, Any]:
    content = note.get("content", {})
    title = str(value_of(content.get("title")) or "")
    authorids = value_of(content.get("authorids")) or []
    authors = value_of(content.get("authors")) or []
    if isinstance(authorids, str):
        authorids = [authorids]
    if isinstance(authors, str):
        authors = [authors]
    return {
        "year": year,
        "title": title,
        "title_key": normalize_title(title),
        "authorids": [str(author_id) for author_id in authorids if str(author_id).startswith("~")],
        "authors": authors,
    }


def profile_institution(profile: dict[str, Any], year: int) -> tuple[str | None, str | None]:
    content = profile.get("content", {})
    histories = content.get("history") or []
    best = None
    for history in histories:
        start = history.get("start")
        end = history.get("end")
        try:
            start_year = int(start) if str(start or "").strip() else None
        except (TypeError, ValueError):
            start_year = None
        try:
            end_year = int(end) if str(end or "").strip() else None
        except (TypeError, ValueError):
            end_year = None
        start_ok = start_year is None or start_year <= year
        end_ok = end_year is None or end_year >= year
        if start_ok and end_ok and history.get("institution"):
            best = history
            break
    if best is None:
        for history in histories:
            if history.get("institution"):
                best = history
                break
    if best is None:
        return None, None
    institution = best.get("institution") or {}
    return institution.get("name"), institution.get("domain")


def country_from_institution(name: str | None, domain: str | None) -> str | None:
    domain = str(domain or "").lower().strip()
    labels = domain.split(".")
    suffixes = [".".join(labels[-2:]), labels[-1] if labels else ""]
    for suffix in suffixes:
        if suffix in COUNTRY_TLD:
            return COUNTRY_TLD[suffix]
    normalized_name = normalize_title(name)
    for hint, country in INSTITUTION_COUNTRY_HINTS.items():
        if hint in normalized_name:
            return country
    return None


def fetch_profile(
    profile_id: str,
    cache: dict[str, Any],
    sleep: float,
) -> dict[str, Any] | None:
    if profile_id in cache:
        return cache[profile_id]
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "COMP4010 AI Conference Research Observatory/1.0"})
        response = None
        for attempt in range(2):
            response = session.get(f"{OPENREVIEW_API}/profiles", params={"id": profile_id}, timeout=12)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1 + attempt)
                continue
            response.raise_for_status()
            break
        if response is None:
            return None
        payload = response.json()
        profiles = payload.get("profiles") or []
        profile = profiles[0] if profiles else None
        time.sleep(sleep)
        return profile
    except (requests.RequestException, ValueError) as exc:
        print(f"OpenReview profile failed for {profile_id}: {exc}")
        return None


def affiliations_for_note(
    note: dict[str, Any],
    profile_cache: dict[str, Any],
) -> tuple[list[str], list[str]]:
    institutions: set[str] = set()
    countries: set[str] = set()
    for profile_id in note["authorids"]:
        profile = profile_cache.get(profile_id)
        if not profile:
            continue
        institution, domain = profile_institution(profile, int(note["year"]))
        if institution:
            institutions.add(str(institution).strip())
        country = country_from_institution(institution, domain)
        if country:
            countries.add(country)
    return sorted(institutions) or ["Unknown"], sorted(countries) or ["Unknown"]


def main() -> None:
    args = parse_args()
    ensure_dirs()
    path = INTERIM_DIR / "enriched.parquet"
    if not path.exists():
        raise RuntimeError("Missing data/interim/enriched.parquet. Run 02_enrich_openalex.py first.")

    papers = pd.read_parquet(path)
    for column in ("institutions", "institution_rors", "countries", "countries_iso2"):
        if column not in papers.columns:
            papers[column] = [["Unknown"] for _ in range(len(papers))]
        papers[column] = papers[column].astype(object)
    papers["title_key"] = papers["title"].apply(normalize_title)
    session = requests.Session()
    session.headers.update({"User-Agent": "COMP4010 AI Conference Research Observatory/1.0"})
    profile_cache = load_json(CACHE_PATH)

    notes_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for year in args.years:
        notes = [note_record(note, year) for note in fetch_notes_for_year(session, year, args.limit_notes)]
        notes = [note for note in notes if note["title_key"]]
        notes_by_key.update({(int(note["year"]), note["title_key"]): note for note in notes})
        print(f"Loaded {len(notes)} OpenReview notes for {year}.")

    matched_notes = []
    for _, row in papers.iterrows():
        if int(row["year"]) not in set(args.years):
            continue
        note = notes_by_key.get((int(row["year"]), str(row["title_key"])))
        if note:
            matched_notes.append(note)

    stale_failures = [profile_id for profile_id, profile in profile_cache.items() if not profile]
    for profile_id in stale_failures:
        profile_cache.pop(profile_id, None)

    needed_profile_ids = []
    seen_profile_ids = set()
    for note in matched_notes:
        for profile_id in note["authorids"]:
            if not profile_id or profile_id in profile_cache or profile_id in seen_profile_ids:
                continue
            needed_profile_ids.append(profile_id)
            seen_profile_ids.add(profile_id)
    if args.limit_profiles is not None:
        needed_profile_ids = needed_profile_ids[: args.limit_profiles]
    print(f"Matched {len(matched_notes)} papers to OpenReview notes; fetching {len(needed_profile_ids)} new profiles.")

    if needed_profile_ids:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(fetch_profile, profile_id, profile_cache, args.sleep): profile_id
                for profile_id in needed_profile_ids
            }
            for i, future in enumerate(tqdm(as_completed(futures), total=len(futures), desc="OpenReview profiles"), start=1):
                profile_id = futures[future]
                profile = future.result()
                if profile:
                    profile_cache[profile_id] = profile
                if i % 50 == 0:
                    save_json(CACHE_PATH, profile_cache)
        save_json(CACHE_PATH, profile_cache)

    filled = 0
    matched = 0
    for index, row in tqdm(papers.iterrows(), total=len(papers), desc="OpenReview affiliations"):
        if int(row["year"]) not in set(args.years):
            continue
        note = notes_by_key.get((int(row["year"]), str(row["title_key"])))
        if not note:
            continue
        matched += 1
        if as_list(row.get("institutions")) != ["Unknown"] and as_list(row.get("countries")) != ["Unknown"]:
            continue
        institutions, countries = affiliations_for_note(note, profile_cache)
        if institutions == ["Unknown"] and countries == ["Unknown"]:
            continue
        papers.at[index, "institutions"] = institutions
        papers.at[index, "institution_rors"] = ["Unknown"]
        papers.at[index, "countries"] = countries
        papers.at[index, "countries_iso2"] = countries
        papers.at[index, "affiliation_source"] = "openreview"
        papers.at[index, "affiliation_confidence"] = 0.9
        papers.at[index, "institution_coverage"] = institutions != ["Unknown"]
        papers.at[index, "country_coverage"] = countries != ["Unknown"]
        filled += 1
        if filled % 500 == 0:
            save_json(CACHE_PATH, profile_cache)
            write_parquet(papers.drop(columns=["title_key"]), path)

    save_json(CACHE_PATH, profile_cache)
    for column in ("institutions", "institution_rors", "countries", "countries_iso2"):
        papers[column] = papers[column].apply(as_list)
    output = papers.drop(columns=["title_key"])
    write_parquet(output, path)
    write_parquet(output, INTERIM_DIR / "enriched.partial.parquet")
    print(f"Matched {matched} papers to OpenReview notes; filled {filled} affiliation rows.")


if __name__ == "__main__":
    main()
