from __future__ import annotations

from abc import ABC, abstractmethod


class VenueSource(ABC):
    venue: str

    @abstractmethod
    def list_years(self) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def index_count(self, year: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def fetch_papers(self, year: int) -> list[dict]:
        raise NotImplementedError

