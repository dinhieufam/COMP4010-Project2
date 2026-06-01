from __future__ import annotations

import re
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from pipeline.config import CACHE_DIR, NEURIPS_BASE_URL, ensure_dirs
from pipeline.models import PaperRecord
from pipeline.sources.base import VenueSource

try:
    import requests_cache
except ImportError:  # pragma: no cover
    requests_cache = None


YEAR_RE = re.compile(r"/paper_files/paper/(\d{4})")


class NeurIPSSource(VenueSource):
    venue = "neurips"

    def __init__(self, throttle_seconds: float = 0.05, timeout: int = 30, workers: int = 6) -> None:
        ensure_dirs()
        self.throttle_seconds = throttle_seconds
        self.timeout = timeout
        self.workers = workers
        if requests_cache is not None:
            self.session = requests_cache.CachedSession(
                str(CACHE_DIR / "neurips"),
                expire_after=60 * 60 * 24 * 30,
            )
        else:
            self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "COMP4010 AI Conference Research Observatory/1.0"}
        )

    def _get(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        if not getattr(response, "from_cache", False):
            time.sleep(self.throttle_seconds)
        return response.text

    def list_years(self) -> list[int]:
        years: set[int] = set()
        for url in (NEURIPS_BASE_URL, f"{NEURIPS_BASE_URL}/papers"):
            try:
                html = self._get(url)
            except requests.RequestException:
                continue
            years.update(int(match.group(1)) for match in YEAR_RE.finditer(html))
        if not years:
            years.update(self._probe_years())
        return sorted(year for year in years if 1987 <= year <= 2100)

    def _probe_years(self) -> list[int]:
        years = []
        for year in range(1987, date.today().year + 1):
            try:
                response = self.session.get(self.index_url(year), timeout=self.timeout)
                if response.status_code == 200 and "-Abstract" in response.text:
                    years.append(year)
                if not getattr(response, "from_cache", False):
                    time.sleep(self.throttle_seconds)
            except requests.RequestException:
                continue
        return years

    def index_url(self, year: int) -> str:
        return f"{NEURIPS_BASE_URL}/paper_files/paper/{year}"

    def detail_links(self, year: int) -> list[str]:
        soup = BeautifulSoup(self._get(self.index_url(year)), "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "-Abstract" not in href or (
                f"/paper/{year}/" not in href and f"/paper_files/paper/{year}/" not in href
            ):
                continue
            full = urljoin(NEURIPS_BASE_URL, href)
            if full not in seen:
                links.append(full)
                seen.add(full)
        return links

    def index_count(self, year: int) -> int:
        return len(self.detail_links(year))

    def fetch_papers(self, year: int) -> list[dict]:
        links = self.detail_links(year)
        if self.workers <= 1:
            return [self.fetch_detail(url, year).to_dict() for url in links]

        papers: list[dict] = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.fetch_detail, url, year): url for url in links}
            for future in as_completed(futures):
                papers.append(future.result().to_dict())
        return sorted(papers, key=lambda row: row["paper_id"])

    def fetch_detail(self, url: str, year: int) -> PaperRecord:
        soup = BeautifulSoup(self._get(url), "html.parser")
        title = parse_title(soup)
        title = re.sub(r"^Abstract\s*", "", title).strip()

        return PaperRecord(
            venue=self.venue,
            year=year,
            paper_id=parse_paper_id(url, year, title),
            title=title,
            authors=parse_authors(soup),
            abstract=parse_abstract(soup),
            url=url,
            pdf_url=parse_pdf_url(soup),
            doi=parse_doi(soup),
            source="proceedings.neurips.cc",
        )


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_title(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "citation_title"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])
    for tag in ("h1", "h2", "title", "h3", "h4"):
        node = soup.find(tag)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if text and text.lower() not in {"abstract", "name change policy"}:
                return text
    return ""


def parse_authors(soup: BeautifulSoup) -> list[str]:
    meta_authors = [
        clean_text(node.get("content", ""))
        for node in soup.find_all("meta", attrs={"name": "citation_author"})
    ]
    if meta_authors:
        return [author for author in meta_authors if author] or ["Unknown"]

    for css in ("i", ".author", ".authors"):
        for node in soup.select(css):
            text = clean_text(node.get_text(" ", strip=True))
            if text and not text.lower().startswith("abstract"):
                return [part.strip() for part in re.split(r",|\band\b", text) if part.strip()]
    return ["Unknown"]


def parse_abstract(soup: BeautifulSoup) -> str | None:
    heading = soup.find(string=re.compile(r"^\s*Abstract\s*$", re.I))
    if heading:
        for sibling in heading.parent.find_all_next(["p", "div"], limit=4):
            text = clean_text(sibling.get_text(" ", strip=True))
            if text and text.lower() != "abstract":
                return text
    for meta_name in ("description", "citation_abstract"):
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            return clean_text(meta["content"])
    return None


def parse_pdf_url(soup: BeautifulSoup) -> str | None:
    for link in soup.find_all("a", href=True):
        href = link["href"]
        label = clean_text(link.get_text(" ", strip=True)).lower()
        if href.lower().endswith(".pdf") or label == "paper":
            return urljoin(NEURIPS_BASE_URL, href)
    return None


def parse_doi(soup: BeautifulSoup) -> str | None:
    for meta_name in ("citation_doi", "dc.identifier", "dc.identifier.doi", "doi"):
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            doi = normalize_doi(meta["content"])
            if doi:
                return doi
    for link in soup.find_all("a", href=True):
        doi = normalize_doi(link["href"])
        if doi:
            return doi
    return None


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    text = clean_text(value)
    text = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.I)
    if not match:
        return None
    return match.group(0).rstrip(".,;)]}").lower()


def parse_paper_id(url: str, year: int, title: str) -> str:
    match = re.search(r"/hash/([^/]+)-Abstract", url)
    if match:
        suffix = match.group(1)
    else:
        suffix = sha1(f"{year}:{title}:{url}".encode("utf-8")).hexdigest()[:16]
    return f"neurips_{year}_{suffix}"
