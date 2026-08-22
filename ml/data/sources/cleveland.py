"""Cleveland Museum of Art — Open Access API (no key required).

Docs: https://openaccess-api.clevelandart.org/
CMA has one of the finest Indian, Himalayan and East Asian collections and
returns rich metadata in a single paginated endpoint, so ingestion is cheap.
We request only CC0 works that have a web image.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..normalize import normalize_category, normalize_region
from ..schema import Artwork
from .base import BaseIngestor, http_get_json

_BASE = "https://openaccess-api.clevelandart.org/api/artworks"
_PAGE = 100


class ClevelandIngestor(BaseIngestor):
    source = "cleveland"
    rate_limit = 0.2

    def _to_artwork(self, obj: dict) -> Artwork | None:
        images = obj.get("images") or {}
        web = (images.get("web") or {}).get("url")
        if not web:
            return None
        creators = obj.get("creators") or []
        artist = creators[0].get("description", "") if creators else ""
        culture = obj.get("culture") or []
        culture_str = ", ".join(culture) if isinstance(culture, list) else str(culture)
        return Artwork(
            uid=self.make_uid(obj["id"]),
            source=self.source,
            source_id=str(obj["id"]),
            title=obj.get("title") or "",
            artist=artist,
            date_text=obj.get("creation_date") or "",
            year_start=obj.get("creation_date_earliest"),
            year_end=obj.get("creation_date_latest"),
            category=normalize_category(obj.get("type")),
            medium=obj.get("technique") or "",
            style=obj.get("culture_str") or "",
            region=normalize_region(culture_str, obj.get("department")),
            culture_raw=culture_str,
            image_url=web,
            thumbnail_url=(images.get("web") or {}).get("url", web),
            source_url=obj.get("url") or "",
            license="CC0",
            is_public_domain=True,
        )

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        count = 0
        skip = 0
        while True:
            params = {
                "cc0": "1",
                "has_image": "1",
                "limit": _PAGE,
                "skip": skip,
            }
            data = http_get_json(_BASE, params=params)
            self._sleep()
            rows = (data or {}).get("data") or []
            if not rows:
                return
            for obj in rows:
                if limit is not None and count >= limit:
                    return
                art = self._to_artwork(obj)
                if art is not None:
                    count += 1
                    yield art
            skip += _PAGE
