"""Apply manual institution-feedback corrections to the interim parquet files.

Reads data/manual/institution_feedback.csv and applies three kinds of corrections
to the ``institutions`` column in topics.parquet (and enriched.parquet):

  TRUE   – keep canonical_institutions when it differs from [raw_institution]
            (cleanup: remove country suffixes, fix typos, etc.)
  FALSE  – replace raw string with the manual_split_institutions list
            (splitting merged multi-institution strings)
  REMOVE – drop the raw string entirely (not a real institution / extraction artefact)

Also derives country information from ``current_country_candidates``:
the column records which countries the institution group belongs to.
Papers whose country is Unknown are updated with derived ISO2 codes.
Papers that already have country data from OpenAlex are unchanged.

After patching the interim files the script re-runs step 07 to regenerate
data/processed/papers.parquet and all downstream app tables.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR
from pipeline.io import write_parquet

FEEDBACK_PATH = ROOT / "data" / "manual" / "institution_feedback.csv"

# Non-standard → standard ISO2 normalisation
_ISO2_NORM: dict[str, str] = {
    "UK": "GB",
    "ENG": "GB",
    "SCO": "GB",
    "WAL": "GB",
    "NIR": "GB",
}
_ABBREV_RE = re.compile(r"\b(Inc|Ltd|Corp|Co|Dr|Mr|Ms|Prof|St|Jr|Sr|No)\.$", re.IGNORECASE)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_list(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    s = str(value).strip()
    if not s or s == "[]":
        return []
    try:
        result = ast.literal_eval(s)
        return [str(x).strip() for x in result if str(x).strip()]
    except Exception:
        return [s]


def _clean_name(name: str) -> str:
    """Strip lone trailing-period artefacts (e.g. 'Stanford University.')."""
    if name.endswith(".") and not _ABBREV_RE.search(name):
        return name[:-1].rstrip()
    return name


def _parse_countries(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    s = str(value).strip()
    if s.startswith("["):
        try:
            raw = [str(x).strip() for x in ast.literal_eval(s) if str(x).strip()]
        except Exception:
            raw = [s]
    else:
        raw = [s] if s else []
    return [_ISO2_NORM.get(c, c) for c in raw if c]


def _to_list(val: object) -> list[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if hasattr(val, "tolist"):
        return val.tolist()
    if isinstance(val, (list, tuple)):
        return list(val)
    return [str(val)]


# ── 1. Build correction and country maps ──────────────────────────────────────

def build_maps(fb: pd.DataFrame) -> tuple[dict[str, list[str]], set[str], dict[str, set[str]]]:
    """Return (replace_map, remove_set, inst_to_countries).

    replace_map:       raw_institution → corrected institution list
    remove_set:        raw_institution strings to drop entirely
    inst_to_countries: corrected institution name → set of ISO2 country codes
    """
    replace_map: dict[str, list[str]] = {}
    remove_set: set[str] = set()
    inst_to_countries: dict[str, set[str]] = {}

    for _, row in fb.iterrows():
        raw = str(row["raw_institution"]).strip()
        approved = str(row.get("approved", "")).strip().upper()
        countries = _parse_countries(row.get("current_country_candidates"))

        if approved == "REMOVE":
            remove_set.add(raw)

        elif approved == "FALSE":
            manual = [_clean_name(n) for n in _parse_list(row.get("manual_split_institutions"))]
            manual = [n for n in manual if n]
            if manual:
                replace_map[raw] = manual
                for inst in manual:
                    inst_to_countries.setdefault(inst, set()).update(countries)
            else:
                remove_set.add(raw)

        elif approved == "TRUE":
            canonical = [_clean_name(n) for n in _parse_list(row.get("canonical_institutions"))]
            canonical = [n for n in canonical if n]
            if canonical != [raw]:
                replace_map[raw] = canonical
            for inst in (canonical if canonical else [raw]):
                inst_to_countries.setdefault(inst, set()).update(countries)

    return replace_map, remove_set, inst_to_countries


# ── 2. Apply institution corrections ─────────────────────────────────────────

def _correct_institutions(inst_list: object, replace_map: dict, remove_set: set) -> list[str]:
    items = _to_list(inst_list)
    result: list[str] = []
    for item in items:
        s = str(item).strip()
        if s in remove_set:
            continue
        if s in replace_map:
            replacement = replace_map[s]
            if replacement:
                result.extend(replacement)
        else:
            result.append(s)
    seen: set[str] = set()
    deduped = [x for x in result if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]
    return deduped if deduped else ["Unknown"]


# ── 3. Apply country improvements ────────────────────────────────────────────

def _improve_countries(countries: object, institutions: list[str], inst_to_countries: dict) -> list[str]:
    """Derive countries from the institution→country map.

    If the map produces at least one country for this paper's institutions,
    that result overrides OpenAlex data (manual labels are more trustworthy).
    If the map has no entry for any of this paper's institutions, fall back
    to the existing OpenAlex countries.
    """
    derived: list[str] = []
    seen: set[str] = set()
    for inst in institutions:
        for iso2 in inst_to_countries.get(inst, set()):
            if iso2 not in seen:
                seen.add(iso2)
                derived.append(iso2)

    if derived:
        return derived  # manual-label override

    # Fall back to existing data when no map entry exists
    current = [c for c in _to_list(countries) if c and c != "Unknown"]
    return current if current else ["Unknown"]


def apply_all_corrections(
    df: pd.DataFrame,
    replace_map: dict,
    remove_set: set,
    inst_to_countries: dict,
) -> pd.DataFrame:
    df = df.copy()

    df["institutions"] = df["institutions"].apply(
        lambda x: _correct_institutions(x, replace_map, remove_set)
    )

    df["countries"] = [
        _improve_countries(row["countries"], row["institutions"], inst_to_countries)
        for _, row in df.iterrows()
    ]

    if "institution_coverage" in df.columns:
        df["institution_coverage"] = df["institutions"].apply(
            lambda lst: any(x.strip() and x.strip() != "Unknown" for x in lst)
        )
    if "country_coverage" in df.columns:
        df["country_coverage"] = df["countries"].apply(
            lambda lst: any(c and c != "Unknown" for c in lst)
        )

    return df


# ── 4. Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    fb = pd.read_csv(FEEDBACK_PATH)
    replace_map, remove_set, inst_to_countries = build_maps(fb)

    print(f"Correction maps: {len(replace_map)} replacements, {len(remove_set)} removals.")
    print(f"Institution→country map: {len(inst_to_countries)} entries.")

    topics_path = INTERIM_DIR / "topics.parquet"
    if not topics_path.exists():
        raise FileNotFoundError(f"Missing {topics_path}. Run pipeline steps 01–05 first.")

    topics = pd.read_parquet(topics_path)

    before_country_unknown = int(
        topics["countries"].apply(lambda x: all(c == "Unknown" for c in _to_list(x))).sum()
    )

    topics = apply_all_corrections(topics, replace_map, remove_set, inst_to_countries)

    after_inst_unknown = int(
        topics["institutions"].apply(lambda x: x == ["Unknown"]).sum()
    )
    after_country_unknown = int(
        topics["countries"].apply(lambda x: all(c == "Unknown" for c in _to_list(x))).sum()
    )
    write_parquet(topics, topics_path)
    print(
        f"topics.parquet updated ({len(topics):,} rows). "
        f"Unknown-institution rows: {after_inst_unknown}. "
        f"Unknown-country rows: {before_country_unknown} → {after_country_unknown}."
    )

    enriched_path = INTERIM_DIR / "enriched.parquet"
    if enriched_path.exists():
        enriched = pd.read_parquet(enriched_path)
        enriched = apply_all_corrections(enriched, replace_map, remove_set, inst_to_countries)
        write_parquet(enriched, enriched_path)
        print(f"enriched.parquet updated ({len(enriched):,} rows).")

    print("\nRegenerating processed app data (step 07)…")
    import importlib.util
    spec = importlib.util.spec_from_file_location("step07", ROOT / "pipeline" / "07_aggregate_for_app.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.main()

    print("\nDone. Institution and country corrections applied; app data regenerated.")


if __name__ == "__main__":
    main()
