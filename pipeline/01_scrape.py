from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import ensure_dirs
from pipeline.io import raw_file, write_jsonl
from pipeline.sources import get_adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape accepted paper lists for a venue.")
    parser.add_argument("--venue", default="neurips", choices=["neurips"])
    parser.add_argument("--years", nargs="*", type=int, help="Optional explicit years to scrape.")
    parser.add_argument("--force", action="store_true", help="Re-scrape years that already have raw files.")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent detail-page fetches per year.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    adapter = get_adapter(args.venue)
    if hasattr(adapter, "workers"):
        adapter.workers = max(1, args.workers)
    years = sorted(args.years or adapter.list_years())
    if not years:
        raise RuntimeError("No years discovered. Check network access or the source adapter.")

    for year in tqdm(years, desc=f"Scraping {args.venue}"):
        path = raw_file(args.venue, year)
        if path.exists() and not args.force:
            continue
        papers = adapter.fetch_papers(year)
        write_jsonl(path, papers)
        print(f"{args.venue} {year}: wrote {len(papers)} records to {path}")


if __name__ == "__main__":
    main()
