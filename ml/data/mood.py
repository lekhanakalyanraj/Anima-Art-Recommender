"""Mood taxonomy for the Art Therapy Recommender.

The app's mood input is Plutchik's Wheel of Emotions. Everything downstream —
ArtEmis emotion labels, temple mood tags, retrieval filters — is normalized to
these 8 primary emotions so a single mood vocabulary spans the whole corpus.

Plutchik's 8 primaries and their opposites:
    joy <-> sadness
    trust <-> disgust
    fear <-> anger
    surprise <-> anticipation
"""

from __future__ import annotations

# --- Plutchik primaries -----------------------------------------------------

PLUTCHIK_PRIMARIES: tuple[str, ...] = (
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
)

# Intensity tiers of the wheel (mild -> primary -> intense). The UI wheel lets a
# user pick any petal; we collapse to the primary for corpus-wide consistency.
PLUTCHIK_INTENSITY: dict[str, str] = {
    # joy
    "serenity": "joy", "joy": "joy", "ecstasy": "joy",
    # trust
    "acceptance": "trust", "trust": "trust", "admiration": "trust",
    # fear
    "apprehension": "fear", "fear": "fear", "terror": "fear",
    # surprise
    "distraction": "surprise", "surprise": "surprise", "amazement": "surprise",
    # sadness
    "pensiveness": "sadness", "sadness": "sadness", "grief": "sadness",
    # disgust
    "boredom": "disgust", "disgust": "disgust", "loathing": "disgust",
    # anger
    "annoyance": "anger", "anger": "anger", "rage": "anger",
    # anticipation
    "interest": "anticipation", "anticipation": "anticipation", "vigilance": "anticipation",
}

# --- ArtEmis -> Plutchik ----------------------------------------------------

# ArtEmis labels affective responses to WikiArt paintings with 9 categories.
# We map each to the closest Plutchik primary so ArtEmis annotations become
# mood tags in our vocabulary. "something_else" carries no mood signal.
ARTEMIS_TO_PLUTCHIK: dict[str, str | None] = {
    "amusement": "joy",
    "contentment": "joy",
    "excitement": "anticipation",
    "awe": "surprise",
    "anger": "anger",
    "disgust": "disgust",
    "fear": "fear",
    "sadness": "sadness",
    "something else": None,
    "something_else": None,
}

# --- Therapeutic intent -----------------------------------------------------

# The app aims to "soothe, uplift or inspire" (per the spec). Group primaries by
# the affective register a recommendation is trying to offer.
SOOTHING = {"joy", "trust"}        # calm, safety, contentment
UPLIFTING = {"joy", "surprise"}    # delight, wonder
INSPIRING = {"anticipation", "trust", "surprise"}  # curiosity, awe, reverence

# Moods a user is likely selecting *away from* — used to bias recommendations
# toward regulation rather than amplification of distress.
DISTRESS = {"sadness", "fear", "anger", "disgust"}


def normalize_mood(label: str) -> str | None:
    """Collapse any wheel petal or free label to a Plutchik primary.

    Returns None if the label carries no usable mood signal.
    """
    if not label:
        return None
    key = label.strip().lower().replace("-", "_")
    if key in PLUTCHIK_INTENSITY:
        return PLUTCHIK_INTENSITY[key]
    if key in ARTEMIS_TO_PLUTCHIK:
        return ARTEMIS_TO_PLUTCHIK[key]
    if key in PLUTCHIK_PRIMARIES:
        return key
    return None
