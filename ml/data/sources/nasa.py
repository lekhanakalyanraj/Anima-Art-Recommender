"""NASA Image Library — public-domain space photography.

Adds cosmic imagery (nebulae, galaxies, auroras, planets) to the corpus. These
are awe-inspiring and map naturally onto the mood wheel (surprise/awe, serenity).
Public API, no key required. https://images-api.nasa.gov/
"""

from __future__ import annotations

from collections.abc import Iterator

from ..schema import Artwork
from .base import BaseIngestor, http_get_json

_SEARCH = "https://images-api.nasa.gov/search"

# Visually rich search terms — the corpus of beautiful, evocative space images.
_QUERIES = [
    "nebula", "galaxy", "aurora", "star cluster", "supernova remnant",
    "planetary nebula", "deep field", "hubble", "webb telescope", "milky way",
    "saturn", "jupiter", "cosmic", "star forming region",
]


class NasaIngestor(BaseIngestor):
    source = "nasa"
    rate_limit = 0.1

    def __init__(self, queries: list[str] | None = None):
        self.queries = queries or _QUERIES

    def _best_image(self, nasa_id: str) -> str | None:
        """Pick the best available JPEG for an asset (sizes vary per image)."""
        data = http_get_json(f"https://images-api.nasa.gov/asset/{nasa_id}")
        self._sleep()
        items = ((data or {}).get("collection") or {}).get("items") or []
        hrefs = [i.get("href", "").replace("http://", "https://") for i in items]
        hrefs = [h for h in hrefs if h.lower().endswith((".jpg", ".jpeg", ".png"))]
        for tag in ("~large", "~medium", "~small", "~orig", "~thumb"):
            for h in hrefs:
                if tag in h:
                    return h
        return hrefs[0] if hrefs else None

    def _to_artwork(self, item: dict) -> Artwork | None:
        data = (item.get("data") or [{}])[0]
        links = item.get("links") or []
        nasa_id = data.get("nasa_id")
        if not nasa_id or not links:
            return None
        thumb = links[0].get("href")
        image = self._best_image(nasa_id)
        if not image:
            return None
        return Artwork(
            uid=self.make_uid(nasa_id),
            source=self.source,
            source_id=str(nasa_id),
            title=data.get("title") or "Untitled",
            artist=data.get("secondary_creator") or data.get("center") or "NASA",
            date_text=(data.get("date_created") or "")[:10],
            category="photograph",
            style="space photography",
            region="space",
            culture_raw="Cosmos — NASA",
            image_url=image,
            thumbnail_url=thumb,
            source_url=f"https://images.nasa.gov/details-{nasa_id}",
            license="Public Domain (NASA)",
            is_public_domain=True,
        )

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        count = 0
        seen: set[str] = set()
        for q in self.queries:
            data = http_get_json(_SEARCH, params={"q": q, "media_type": "image"})
            self._sleep()
            items = ((data or {}).get("collection") or {}).get("items") or []
            for item in items:
                if limit is not None and count >= limit:
                    return
                art = self._to_artwork(item)
                if art is None or art.source_id in seen:
                    continue
                seen.add(art.source_id)
                count += 1
                yield art
