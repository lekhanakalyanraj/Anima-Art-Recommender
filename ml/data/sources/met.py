"""The Metropolitan Museum of Art — Open Access API (no key required).

Docs: https://metmuseum.github.io/
The Met's global departments (Asian Art, Islamic Art, Arts of Africa/Oceania/the
Americas, Egyptian, Ancient Near Eastern) are the single biggest jump in world
coverage over WikiArt. We query those departments and keep only CC0 works that
have an image.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..normalize import normalize_category, normalize_region
from ..schema import Artwork
from .base import BaseIngestor, http_get_json

_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# departmentId -> label. IDs are stable in the Met API.
GLOBAL_DEPARTMENTS: dict[int, str] = {
    6: "Asian Art",
    14: "Islamic Art",
    5: "Arts of Africa, Oceania, and the Americas",
    10: "Egyptian Art",
    3: "Ancient Near Eastern Art",
    13: "Greek and Roman Art",
}


class MetIngestor(BaseIngestor):
    source = "met"
    rate_limit = 0.12  # Met asks for < ~80 req/s; stay well under

    def __init__(self, departments: dict[int, str] | None = None):
        self.departments = departments or GLOBAL_DEPARTMENTS

    def _object_ids(self) -> list[int]:
        ids: list[int] = []
        for dept_id in self.departments:
            data = http_get_json(f"{_BASE}/objects", params={"departmentIds": dept_id})
            self._sleep()
            if data and data.get("objectIDs"):
                ids.extend(data["objectIDs"])
        # de-dup, preserve order
        seen: set[int] = set()
        return [i for i in ids if not (i in seen or seen.add(i))]

    def _to_artwork(self, obj: dict) -> Artwork | None:
        image = obj.get("primaryImage") or obj.get("primaryImageSmall")
        if not image or not obj.get("isPublicDomain"):
            return None
        culture = " ".join(
            s for s in (obj.get("culture"), obj.get("country"), obj.get("dynasty")) if s
        )
        return Artwork(
            uid=self.make_uid(obj["objectID"]),
            source=self.source,
            source_id=str(obj["objectID"]),
            title=obj.get("title") or "",
            artist=obj.get("artistDisplayName") or "",
            date_text=obj.get("objectDate") or "",
            year_start=obj.get("objectBeginDate"),
            year_end=obj.get("objectEndDate"),
            category=normalize_category(obj.get("classification"), obj.get("objectName")),
            medium=obj.get("medium") or "",
            style=obj.get("period") or "",
            region=normalize_region(obj.get("culture"), obj.get("country"), obj.get("department")),
            culture_raw=culture,
            image_url=image,
            thumbnail_url=obj.get("primaryImageSmall") or image,
            source_url=obj.get("objectURL") or "",
            license="CC0",
            is_public_domain=True,
        )

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        count = 0
        for object_id in self._object_ids():
            if limit is not None and count >= limit:
                return
            obj = http_get_json(f"{_BASE}/objects/{object_id}")
            self._sleep()
            if not obj:
                continue
            art = self._to_artwork(obj)
            if art is not None:
                count += 1
                yield art
