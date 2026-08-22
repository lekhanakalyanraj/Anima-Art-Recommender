"""Shared ingestor plumbing: an ABC plus a polite HTTP helper.

Each source subclasses BaseIngestor and yields normalized Artwork records. The
orchestrator treats every source identically through ``iter_artworks``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

import requests

from ..schema import Artwork

_SESSION = requests.Session()
_SESSION.headers.update(
    {"User-Agent": "art-therapy-recommender/0.1 (research/portfolio; contact via HF Lekhanakraj)"}
)


def http_get_json(url: str, *, params: dict | None = None, retries: int = 3,
                  backoff: float = 1.5, timeout: int = 30) -> dict | None:
    """GET JSON with simple exponential backoff. Returns None on persistent failure."""
    for attempt in range(retries):
        try:
            resp = _SESSION.get(url, params=params, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                return None
            time.sleep(backoff ** attempt)
    return None


class BaseIngestor(ABC):
    """Base class for every art source."""

    #: short, stable source key used in Artwork.source and the uid prefix
    source: str = "base"
    #: seconds to sleep between upstream requests (be a good API citizen)
    rate_limit: float = 0.0

    def make_uid(self, source_id: str | int) -> str:
        return f"{self.source}:{source_id}"

    def _sleep(self) -> None:
        if self.rate_limit:
            time.sleep(self.rate_limit)

    @abstractmethod
    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        """Yield up to ``limit`` normalized Artwork records (None = all)."""
        raise NotImplementedError
