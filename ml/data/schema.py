"""The unified Artwork record every source normalizes into.

One schema for WikiArt, the Met, Cleveland, AIC, the Indian art styles set, and
(later) Wikimedia Commons temples. Pydantic so it doubles as the FastAPI
response model later in the API-first backend.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .mood import PLUTCHIK_PRIMARIES, normalize_mood
from .normalize import CATEGORIES, REGIONS


class Artwork(BaseModel):
    """A single normalized artwork, comparable across every source."""

    # Identity — ``{source}:{source_id}`` guarantees global uniqueness on merge.
    uid: str = Field(..., description="Globally unique: '<source>:<source_id>'")
    source: str = Field(..., description="Origin dataset/API: wikiart|met|cleveland|aic|indian_art|commons")
    source_id: str = Field(..., description="ID within the source")

    # Descriptive
    title: str = ""
    artist: str = ""
    date_text: str = Field("", description="Human-readable date as given by source")
    year_start: int | None = None
    year_end: int | None = None

    # Classification
    category: str = Field("other", description="painting|sculpture|architecture|...")
    style: str = ""
    medium: str = ""

    # Geography — the axis that makes 'world coverage' measurable
    region: str = Field("unknown", description="Controlled world region")
    culture_raw: str = Field("", description="Original culture/place string from source")

    # Media
    image_url: str = ""
    thumbnail_url: str = ""
    source_url: str = Field("", description="Link back to the object page")

    # Rights — mixed-license corpus, so track it per record
    license: str = ""
    is_public_domain: bool | None = None

    # Mood — Plutchik primaries with weights, summing loosely to 1.0. Filled from
    # ArtEmis for WikiArt works and inferred (CLIP / rules) for the rest.
    mood_scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        return v if v in CATEGORIES else "other"

    @field_validator("region")
    @classmethod
    def _valid_region(cls, v: str) -> str:
        return v if v in REGIONS else "unknown"

    @field_validator("mood_scores")
    @classmethod
    def _clean_moods(cls, v: dict[str, float]) -> dict[str, float]:
        # Keep only recognized Plutchik primaries; drop noise.
        return {k: float(w) for k, w in v.items() if k in PLUTCHIK_PRIMARIES}

    @property
    def top_mood(self) -> str | None:
        if not self.mood_scores:
            return None
        return max(self.mood_scores, key=self.mood_scores.get)

    def add_mood(self, label: str, weight: float = 1.0) -> None:
        """Accumulate a mood signal (any wheel/ArtEmis label) onto this work."""
        primary = normalize_mood(label)
        if primary is None:
            return
        self.mood_scores[primary] = self.mood_scores.get(primary, 0.0) + weight

    def normalize_mood_scores(self) -> None:
        """Scale mood_scores to sum to 1.0 (no-op if empty)."""
        total = sum(self.mood_scores.values())
        if total > 0:
            self.mood_scores = {k: round(w / total, 4) for k, w in self.mood_scores.items()}
