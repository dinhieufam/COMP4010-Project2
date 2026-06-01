from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PaperRecord:
    venue: str
    year: int
    paper_id: str
    title: str
    authors: list[str]
    abstract: str | None
    url: str | None
    pdf_url: str | None
    doi: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

