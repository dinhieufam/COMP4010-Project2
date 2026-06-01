from __future__ import annotations

import argparse
import hashlib
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from pypdf import PdfReader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, ensure_dirs
from pipeline.io import write_parquet


PDF_CACHE_DIR = INTERIM_DIR / "pdf_cache"
TEXT_CACHE_DIR = INTERIM_DIR / "pdf_text_cache"

COUNTRY_TLD = {
    "edu": "US",
    "gov": "US",
    "mil": "US",
    "us": "US",
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
    "sa": "SA",
}

COUNTRY_HINTS = {
    "united states": "US",
    "usa": "US",
    "u.s.a": "US",
    "canada": "CA",
    "united kingdom": "GB",
    "uk": "GB",
    "china": "CN",
    "germany": "DE",
    "france": "FR",
    "switzerland": "CH",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "singapore": "SG",
    "australia": "AU",
    "israel": "IL",
    "india": "IN",
    "italy": "IT",
    "spain": "ES",
    "sweden": "SE",
    "denmark": "DK",
    "norway": "NO",
    "finland": "FI",
    "netherlands": "NL",
    "belgium": "BE",
    "austria": "AT",
    "ireland": "IE",
    "brazil": "BR",
    "mexico": "MX",
    "chile": "CL",
    "new zealand": "NZ",
    "saudi arabia": "SA",
}

STATIC_INSTITUTIONS = {
    "Massachusetts Institute of Technology": ["mit", "massachusetts institute of technology"],
    "Stanford University": ["stanford university"],
    "Carnegie Mellon University": ["carnegie mellon"],
    "University of California, Berkeley": ["uc berkeley", "university of california berkeley", "berkeley ai research"],
    "University of Toronto": ["university of toronto"],
    "University of Washington": ["university of washington"],
    "University of Oxford": ["university of oxford"],
    "University of Cambridge": ["university of cambridge"],
    "University College London": ["university college london", "ucl"],
    "Imperial College London": ["imperial college london"],
    "Tsinghua University": ["tsinghua university"],
    "Peking University": ["peking university"],
    "Zhejiang University": ["zhejiang university"],
    "Shanghai Jiao Tong University": ["shanghai jiao tong university"],
    "National University of Singapore": ["national university of singapore"],
    "ETH Zurich": ["eth zurich", "eth zürich"],
    "EPFL": ["epfl", "ecole polytechnique federale de lausanne"],
    "University of Tokyo": ["university of tokyo"],
    "KAIST": ["kaist"],
    "Seoul National University": ["seoul national university"],
    "Technion": ["technion"],
    "Hebrew University of Jerusalem": ["hebrew university"],
    "Google": ["google research", "google brain", "google deepmind", "google"],
    "DeepMind": ["deepmind"],
    "Microsoft": ["microsoft research", "microsoft"],
    "Meta": ["meta ai", "facebook ai", "facebook research", "meta"],
    "OpenAI": ["openai"],
    "NVIDIA": ["nvidia"],
    "Amazon": ["amazon web services", "amazon", "aws ai"],
    "IBM": ["ibm research", "ibm"],
    "Adobe": ["adobe research", "adobe"],
    "Alibaba Group": ["alibaba group", "alibaba"],
    "Iambic Therapeutics": ["iambic therapeutics"],
    "CyberAgent": ["cyberagent"],
    "Boson AI": ["boson ai"],
    "KAUST": ["kaust", "king abdullah university of science and technology"],
    "Houmo AI": ["houmo ai"],
    "Agency for Defense Development": ["agency for defense development"],
    "POSTECH": ["postech", "pohang university of science and technology"],
    "Flagship Pioneering": ["flagship pioneering"],
    "Fudan University": ["fudan university", "fudan.edu.cn"],
    "Shandong University": ["shandong university", "sdu.edu.cn"],
    "Beihang University": ["beihang university", "buaa.edu.cn"],
    "University of Edinburgh": ["university of edinburgh"],
    "Cornell University": ["cornell university"],
    "UMass Amherst": ["umass amherst", "university of massachusetts amherst"],
    "Peng Cheng Laboratory": ["peng cheng laboratory"],
    "Nanyang Technological University": ["nanyang technological university"],
    "University of Virginia": ["university of virginia"],
    "University of California, Davis": ["university of california davis", "uc davis", "ucdavis.edu"],
    "Beijing Institute of Technology": ["beijing institute of technology"],
    "Fraunhofer Institute IVI": ["fraunhofer institute ivi"],
    "Technical University of Munich": ["technical university of munich"],
    "Vector Institute": ["vector institute"],
    "Johns Hopkins University": ["johns hopkins university"],
    "Sun Yat-sen University": ["sun yat-sen university"],
    "Jinan University": ["jinan university"],
    "Rutgers University": ["rutgers university"],
    "Shenzhen University": ["shenzhen university"],
}

STATIC_INSTITUTION_COUNTRY = {
    "Massachusetts Institute of Technology": {"US"},
    "Stanford University": {"US"},
    "Carnegie Mellon University": {"US"},
    "University of California, Berkeley": {"US"},
    "University of Washington": {"US"},
    "Harvard University": {"US"},
    "The Ohio State University": {"US"},
    "Rice University": {"US"},
    "Georgia Institute of Technology": {"US"},
    "Northeastern University": {"US"},
    "Northwestern University": {"US"},
    "University of Texas at Austin": {"US"},
    "University of Toronto": {"CA"},
    "University of Waterloo": {"CA"},
    "University of Oxford": {"GB"},
    "University of Cambridge": {"GB"},
    "University College London": {"GB"},
    "Imperial College London": {"GB"},
    "University of Warwick": {"GB"},
    "University of Manchester": {"GB"},
    "University of Liverpool": {"GB"},
    "Tsinghua University": {"CN"},
    "Peking University": {"CN"},
    "Zhejiang University": {"CN"},
    "Shanghai Jiao Tong University": {"CN"},
    "Fudan University": {"CN"},
    "Nanjing University": {"CN"},
    "Xiamen University": {"CN"},
    "Sichuan University": {"CN"},
    "Beijing Jiaotong University": {"CN"},
    "Harbin Institute of Technology": {"CN"},
    "Beihang University": {"CN"},
    "South China University of Technology": {"CN"},
    "Chinese Academy of Sciences": {"CN"},
    "Chinese University of Hong Kong": {"HK"},
    "University of Hong Kong": {"HK"},
    "Hong Kong University of Science and Technology": {"HK"},
    "National University of Singapore": {"SG"},
    "ETH Zurich": {"CH"},
    "EPFL": {"CH"},
    "University of Basel": {"CH"},
    "University of Tokyo": {"JP"},
    "KAIST": {"KR"},
    "Seoul National University": {"KR"},
    "Sungkyunkwan University": {"KR"},
    "Kyungpook National University": {"KR"},
    "Technion": {"IL"},
    "Hebrew University of Jerusalem": {"IL"},
    "Aalto University": {"FI"},
    "École Polytechnique": {"FR"},
    "École Polytechnique Fédérale de Lausanne": {"CH"},
    "Fontys University of Applied Sciences": {"NL"},
    "Technical University of Eindhoven": {"NL"},
    "University of Maryland": {"US"},
    "University of Texas at Austin": {"US"},
    "Beijing Jiaotong University": {"CN"},
    "Harbin Institute of Technology": {"CN"},
    "Jilin University": {"CN"},
    "Nanjing University": {"CN"},
    "Shanghai Jiao Tong University": {"CN"},
    "Sichuan University": {"CN"},
    "Sungkyunkwan University": {"KR"},
    "Kyungpook National University": {"KR"},
    "Xiamen University": {"CN"},
    "Alibaba Group": {"CN"},
    "Iambic Therapeutics": {"US"},
    "CyberAgent": {"JP"},
    "Boson AI": {"US"},
    "KAUST": {"SA"},
    "Houmo AI": {"CN"},
    "Agency for Defense Development": {"KR"},
    "POSTECH": {"KR"},
    "Flagship Pioneering": {"US"},
    "Fudan University": {"CN"},
    "Shandong University": {"CN"},
    "Beihang University": {"CN"},
    "University of Edinburgh": {"GB"},
    "Cornell University": {"US"},
    "UMass Amherst": {"US"},
    "Peng Cheng Laboratory": {"CN"},
    "Nanyang Technological University": {"SG"},
    "University of Virginia": {"US"},
    "University of California, Davis": {"US"},
    "Beijing Institute of Technology": {"CN"},
    "Fraunhofer Institute IVI": {"DE"},
    "Technical University of Munich": {"DE"},
    "Vector Institute": {"CA"},
    "Johns Hopkins University": {"US"},
    "Sun Yat-sen University": {"CN"},
    "Jinan University": {"CN"},
    "Rutgers University": {"US"},
    "Shenzhen University": {"CN"},
    "Google": {"US"},
    "DeepMind": {"GB"},
    "Microsoft": {"US"},
    "Meta": {"US"},
    "OpenAI": {"US"},
    "NVIDIA": {"US"},
    "Amazon": {"US"},
    "IBM": {"US"},
    "Adobe": {"US"},
}

ORG_KEYWORDS = re.compile(
    r"\b(university|institute|college|school|laborator(?:y|ies)|labs?|research|centre|center|"
    r"polytechnic|technology|technion|kaist|inria|cnrs|max planck|deepmind|openai|google|microsoft|meta|"
    r"facebook|nvidia|amazon|ibm|adobe|alibaba|therapeutics|cyberagent|kaust|postech|"
    r"boson ai|houmo ai|agency for defense development|flagship pioneering|peng cheng|"
    r"nanyang technological|umass|cornell|fudan|beihang|shandong|fraunhofer|vector institute)\b",
    re.I,
)

GENERIC_ORG_BLOCKLIST = {
    "abstract",
    "introduction",
    "department of computer science",
    "computer science",
    "university of technology",
    "engineering design research",
    "college park",
    "college park engineering design research",
    "robotics institute",
    "robotics institute germany",
    "mellon university",
    "key laboratory",
    "state key laboratory",
    "technological university",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF first-page affiliation extraction for unknown institution/country rows.")
    parser.add_argument("--input", default=str(INTERIM_DIR / "enriched.parquet"))
    parser.add_argument("--output", default=str(INTERIM_DIR / "enriched.parquet"))
    parser.add_argument("--limit", type=int, default=500, help="Maximum unknown-affiliation PDFs to inspect in one run.")
    parser.add_argument("--years", nargs="*", type=int, default=None, help="Optional years to prioritize/filter.")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--min-confidence", type=float, default=0.50)
    parser.add_argument(
        "--refresh-source",
        default=None,
        help="Reset rows from this affiliation_source before selecting candidates, e.g. pdf_text.",
    )
    return parser.parse_args()


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


def is_unknown(value: Any) -> bool:
    return as_list(value) == ["Unknown"]


def safe_filename(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9@._+\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def header_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text or "")
    cut_points = []
    for marker in (r"\babstract\b", r"\bintroduction\b", r"\bkeywords\b"):
        match = re.search(marker, text, flags=re.I)
        if match:
            cut_points.append(match.start())
    if cut_points:
        text = text[: min(cut_points)]
    return text[:6000]


def build_known_institution_aliases(df: pd.DataFrame) -> dict[str, list[str]]:
    aliases = {key: list(values) for key, values in STATIC_INSTITUTIONS.items()}
    counts: dict[str, int] = {}
    for values in df.get("institutions", pd.Series(dtype=object)).apply(as_list):
        for value in values:
            if value != "Unknown" and len(value) >= 4:
                counts[value] = counts.get(value, 0) + 1
    for institution, count in counts.items():
        if count < 2:
            continue
        if institution.lower().strip() in GENERIC_ORG_BLOCKLIST:
            continue
        aliases.setdefault(institution, []).append(institution.lower())
    return aliases


def build_institution_country_lookup(df: pd.DataFrame) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    for row in df.to_dict("records"):
        institutions = as_list(row.get("institutions"))
        countries = [country for country in as_list(row.get("countries")) if country != "Unknown"]
        for institution in institutions:
            if institution == "Unknown":
                continue
            lookup.setdefault(institution, set()).update(countries)
    return lookup


def is_valid_org_candidate(value: str) -> bool:
    normalized = value.lower().strip(" ,;:-")
    if normalized in GENERIC_ORG_BLOCKLIST:
        return False
    if re.search(r"\b(abstract|introduction|references|appendix|proceedings)\b", normalized):
        return False
    if len(normalized.split()) > 12:
        return False
    return bool(ORG_KEYWORDS.search(value))


def countries_for_institution(institution: str, country_lookup: dict[str, set[str]]) -> set[str]:
    static_countries = set(STATIC_INSTITUTION_COUNTRY.get(institution, set()))
    if static_countries:
        return static_countries
    lookup_countries = country_lookup.get(institution, set())
    if 0 < len(lookup_countries) <= 2:
        return set(lookup_countries)
    return set()


def cached_pdf_bytes(paper_id: str, pdf_url: str, timeout: int) -> bytes:
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = PDF_CACHE_DIR / f"{safe_filename(paper_id or pdf_url)}.pdf"
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    response = requests.get(
        pdf_url,
        timeout=timeout,
        headers={"User-Agent": "COMP4010 AI Conference Research Observatory/1.0"},
    )
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF") and b"%PDF" not in content[:1024]:
        raise ValueError("Not a PDF response.")
    path.write_bytes(content)
    return content


def cached_first_pages_text(paper_id: str, pdf_url: str, timeout: int, pages: int) -> str:
    TEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = TEXT_CACHE_DIR / f"{safe_filename(paper_id or pdf_url)}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    pdf_path = PDF_CACHE_DIR / f"{safe_filename(paper_id or pdf_url)}.pdf"
    try:
        content = cached_pdf_bytes(paper_id, pdf_url, timeout)
        reader = PdfReader(BytesIO(content))
        texts = []
        for page in reader.pages[: max(1, pages)]:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(texts)
        path.write_text(text, encoding="utf-8", errors="ignore")
        return text
    finally:
        # The extracted first-page text is the reusable artifact. Keeping every
        # downloaded PDF can consume tens of GB during a full-corpus crawl. Also
        # clean up after failed/invalid PDFs so bad files do not accumulate.
        try:
            pdf_path.unlink(missing_ok=True)
        except OSError:
            pass


def countries_from_text(text: str) -> set[str]:
    countries: set[str] = set()
    normalized = normalize_text(text)
    for phrase, country in COUNTRY_HINTS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            countries.add(country)
    domains = re.findall(r"\b[a-z0-9.-]+\.[a-z]{2,}\b", normalized)
    for domain in domains:
        parts = domain.split(".")
        suffixes = [".".join(parts[-2:]), parts[-1]]
        for suffix in suffixes:
            if suffix in COUNTRY_TLD:
                countries.add(COUNTRY_TLD[suffix])
    return countries


def clean_org_candidate(value: str) -> str:
    value = re.sub(r"\s*\d+(?=[A-Z])", "; ", value)
    value = re.sub(r"[\*\u2020\u2021§¶]+", " ", value)
    value = re.sub(r"\b\d+\b", " ", value)
    value = re.sub(r"^\d+", "", value)
    value = re.sub(r"\S+@\S+", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;:-")
    value = value.replace("V ector Institute", "Vector Institute")
    value = re.sub(r"^(and|with|at|from|the)\s+", "", value, flags=re.I)
    return value.strip()


def remove_subsumed_candidates(candidates: set[str]) -> set[str]:
    cleaned: set[str] = set(candidates)
    normalized = {candidate: normalize_text(candidate) for candidate in cleaned}
    for candidate, candidate_norm in list(normalized.items()):
        for other, other_norm in normalized.items():
            if candidate == other:
                continue
            if len(other_norm) > len(candidate_norm) and re.search(rf"\b{re.escape(candidate_norm)}\b", other_norm):
                cleaned.discard(candidate)
                break
    return cleaned


def organization_candidates(text: str) -> set[str]:
    candidates: set[str] = set()
    for raw_line in header_text(text).splitlines():
        line = raw_line.strip()
        if not line or len(line) > 220:
            continue
        if not ORG_KEYWORDS.search(line):
            continue
        line = re.sub(r"\s*\d+(?=[A-Z])", "; ", line)
        pieces = re.split(r";| \| | • | · |, (?=[A-Z])", line)
        for piece in pieces:
            candidate = clean_org_candidate(piece)
            if not candidate or len(candidate) < 4 or len(candidate) > 120:
                continue
            if not is_valid_org_candidate(candidate):
                continue
            candidates.add(candidate)

    pattern = re.compile(
        r"\b([A-Z][A-Za-z&.\- ]{2,80}?(?:University|Institute of Technology|Institute|College|School|Laboratory|Labs|Research|Centre|Center))\b"
    )
    for match in pattern.finditer(header_text(text)):
        candidate = clean_org_candidate(match.group(1))
        if 4 <= len(candidate) <= 120 and is_valid_org_candidate(candidate):
            candidates.add(candidate)
    return remove_subsumed_candidates(candidates)


def extract_affiliations(
    text: str,
    aliases: dict[str, list[str]],
    country_lookup: dict[str, set[str]],
) -> tuple[list[str], list[str], float]:
    header = header_text(text)
    normalized = normalize_text(header)
    institutions: set[str] = set()
    country_codes = countries_from_text(header)
    matched_known = False

    for display, patterns in aliases.items():
        for pattern in patterns:
            pattern_norm = normalize_text(pattern)
            if len(pattern_norm) < 3:
                continue
            if re.search(rf"\b{re.escape(pattern_norm)}\b", normalized):
                institutions.add(display)
                country_codes.update(countries_for_institution(display, country_lookup))
                matched_known = True
                break

    if not institutions:
        for candidate in organization_candidates(header):
            institutions.add(candidate)
            country_codes.update(countries_for_institution(candidate, country_lookup))

    confidence = 0.0
    institution_countries = set()
    institutions_with_country = 0
    for institution in institutions:
        this_institution_countries = countries_for_institution(institution, country_lookup)
        if this_institution_countries:
            institutions_with_country += 1
            institution_countries.update(this_institution_countries)
    if institutions and institutions_with_country == len(institutions):
        country_codes = institution_countries
    if institution_countries and (len(country_codes) > len(institution_countries) + 1 or len(country_codes) > 5):
        country_codes = institution_countries

    if institutions:
        confidence = 0.68 if matched_known else 0.54
        if country_codes:
            confidence += 0.07
    return (
        sorted(institutions) or ["Unknown"],
        sorted(country_codes) or ["Unknown"],
        min(confidence, 0.75),
    )


def main() -> None:
    ensure_dirs()
    args = parse_args()
    df = pd.read_parquet(args.input)
    for column in ("institutions", "institution_rors", "countries", "countries_iso2"):
        if column not in df.columns:
            df[column] = [["Unknown"] for _ in range(len(df))]
        df[column] = df[column].apply(as_list)
    if "affiliation_source" not in df.columns:
        df["affiliation_source"] = "none"
    if "affiliation_confidence" not in df.columns:
        df["affiliation_confidence"] = 0.0

    if args.refresh_source:
        refresh_mask = df["affiliation_source"].fillna("").eq(args.refresh_source)
        refreshed = int(refresh_mask.sum())
        if refreshed:
            df.loc[refresh_mask, "institutions"] = pd.Series([["Unknown"] for _ in range(refreshed)], index=df.index[refresh_mask])
            df.loc[refresh_mask, "institution_rors"] = pd.Series([["Unknown"] for _ in range(refreshed)], index=df.index[refresh_mask])
            df.loc[refresh_mask, "countries"] = pd.Series([["Unknown"] for _ in range(refreshed)], index=df.index[refresh_mask])
            df.loc[refresh_mask, "countries_iso2"] = pd.Series([["Unknown"] for _ in range(refreshed)], index=df.index[refresh_mask])
            df.loc[refresh_mask, "affiliation_source"] = "none"
            df.loc[refresh_mask, "affiliation_confidence"] = 0.0
            print(f"Reset {refreshed} rows from affiliation_source={args.refresh_source}.")

    aliases = build_known_institution_aliases(df)
    country_lookup = build_institution_country_lookup(df)

    mask = df["institutions"].apply(is_unknown) & df["pdf_url"].fillna("").astype(str).str.len().gt(0)
    if args.years:
        mask &= df["year"].isin(args.years)
    candidates = df[mask].sort_values(["year", "paper_id"], ascending=[False, True])
    if args.limit:
        candidates = candidates.head(args.limit)

    inspected = 0
    recovered = 0
    for index, row in tqdm(candidates.iterrows(), total=len(candidates), desc="PDF affiliations"):
        inspected += 1
        try:
            text = cached_first_pages_text(str(row["paper_id"]), str(row["pdf_url"]), args.timeout, args.pages)
            institutions, countries, confidence = extract_affiliations(text, aliases, country_lookup)
        except Exception as exc:
            continue
        if institutions == ["Unknown"] or confidence < args.min_confidence:
            continue
        df.at[index, "institutions"] = institutions
        df.at[index, "institution_rors"] = ["Unknown"]
        df.at[index, "countries"] = countries
        df.at[index, "countries_iso2"] = countries
        df.at[index, "affiliation_source"] = "pdf_text"
        df.at[index, "affiliation_confidence"] = confidence
        df.at[index, "institution_coverage"] = True
        df.at[index, "country_coverage"] = countries != ["Unknown"]
        recovered += 1
        if recovered % 100 == 0:
            write_parquet(df, Path(args.output))

    write_parquet(df, Path(args.output))
    print(f"Inspected {inspected} PDFs; recovered affiliations for {recovered} papers.")


if __name__ == "__main__":
    main()
