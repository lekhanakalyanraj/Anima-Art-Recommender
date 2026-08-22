"""Source registry — maps a source key to its ingestor class."""

from __future__ import annotations

from .aic import AICIngestor
from .base import BaseIngestor
from .cleveland import ClevelandIngestor
from .indian_art import IndianArtIngestor
from .met import MetIngestor
from .nasa import NasaIngestor
from .wikiart import WikiArtIngestor

# The Wikimedia Commons temple ingestor is added in its own (fast-follow) task.
REGISTRY: dict[str, type[BaseIngestor]] = {
    WikiArtIngestor.source: WikiArtIngestor,
    MetIngestor.source: MetIngestor,
    ClevelandIngestor.source: ClevelandIngestor,
    AICIngestor.source: AICIngestor,
    IndianArtIngestor.source: IndianArtIngestor,
    NasaIngestor.source: NasaIngestor,
}

__all__ = [
    "REGISTRY", "BaseIngestor", "WikiArtIngestor", "MetIngestor",
    "ClevelandIngestor", "AICIngestor", "IndianArtIngestor",
]
