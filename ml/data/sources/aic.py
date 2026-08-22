"""Art Institute of Chicago — public API (no key required).

Docs: https://api.artic.edu/docs/
AIC's Alsdorf Galleries (Indian, Himalayan, Southeast Asian) and African and
Amerindian collections broaden non-Western coverage. Images are served via IIIF;
we build the image URL from the object's ``image_id`` and the IIIF base.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..normalize import normalize_category, normalize_region
from ..schema import Artwork
from .base import BaseIngestor, http_get_json

_BASE = "https://api.artic.edu/api/v1/artworks/search"
_PAGE = 100
_FIELDS = (
    "id,title,artist_display,date_display,date_start,date_end,place_of_origin,"
    "artwork_type_title,medium_display,classification_title,image_id,is_public_domain,style_title"
)


class AICIngestor(BaseIngestor):
    source = "aic"
    rate_limit = 0.15

    def __init__(self, iiif_size: str = "843"):
        # IIIF full/{size}/0/default.jpg — 843px is AIC's recommended default.
        self.iiif_size = iiif_size

    def _iiif_url(self, iiif_base: str, image_id: str) -> str:
        return f"{iiif_base}/{image_id}/full/{self.iiif_size},/0/default.jpg"

    def _to_artwork(self, obj: dict, iiif_base: str) -> Artwork | None:
        image_id = obj.get("image_id")
        if not image_id or not obj.get("is_public_domain"):
            return None
        return Artwork(
            uid=self.make_uid(obj["id"]),
            source=self.source,
            source_id=str(obj["id"]),
            title=obj.get("title") or "",
            artist=obj.get("artist_display") or "",
            date_text=obj.get("date_display") or "",
            year_start=obj.get("date_start"),
            year_end=obj.get("date_end"),
            category=normalize_category(obj.get("classification_title"), obj.get("artwork_type_title")),
            medium=obj.get("medium_display") or "",
            style=obj.get("style_title") or "",
            region=normalize_region(obj.get("place_of_origin")),
            culture_raw=obj.get("place_of_origin") or "",
            image_url=self._iiif_url(iiif_base, image_id),
            thumbnail_url=f"{iiif_base}/{image_id}/full/200,/0/default.jpg",
            source_url=f"https://www.artic.edu/artworks/{obj['id']}",
            license="CC0",
            is_public_domain=True,
        )

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        count = 0
        page = 1
        while True:
            params = {
                "query[term][is_public_domain]": "true",
                "fields": _FIELDS,
                "limit": _PAGE,
                "page": page,
            }
            data = http_get_json(_BASE, params=params)
            self._sleep()
            if not data:
                return
            iiif_base = (data.get("config") or {}).get("iiif_url", "https://www.artic.edu/iiif/2")
            rows = data.get("data") or []
            if not rows:
                return
            for obj in rows:
                if limit is not None and count >= limit:
                    return
                art = self._to_artwork(obj, iiif_base)
                if art is not None:
                    count += 1
                    yield art
            page += 1
