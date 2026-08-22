"""Plutchik mood metadata for the UI — label, color, and a gentle description.

Colors follow Plutchik's wheel so the frontend selector can mirror it.
"""

from __future__ import annotations

from ml.data.mood import PLUTCHIK_PRIMARIES

# key -> (label, hex color, short invitation shown under the mood)
MOOD_META: dict[str, tuple[str, str, str]] = {
    "joy": ("Joy", "#F4D03F", "Something bright and warm"),
    "trust": ("Trust", "#82C46C", "Something calm and safe"),
    "fear": ("Fear", "#1E8449", "Sit with unease"),
    "surprise": ("Surprise", "#5DADE2", "Wonder and the unexpected"),
    "sadness": ("Sadness", "#2E86C1", "Something quiet and tender"),
    "disgust": ("Disgust", "#8E44AD", "The unsettling"),
    "anger": ("Anger", "#E74C3C", "Heat and intensity"),
    "anticipation": ("Anticipation", "#E67E22", "Curiosity and momentum"),
}


def list_moods() -> list[dict]:
    out = []
    for key in PLUTCHIK_PRIMARIES:
        label, color, blurb = MOOD_META.get(key, (key.title(), "#999999", ""))
        out.append({"key": key, "label": label, "color": color, "blurb": blurb})
    return out
