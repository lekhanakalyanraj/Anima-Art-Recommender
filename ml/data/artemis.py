"""ArtEmis emotion layer -> Plutchik mood scores.

ArtEmis (Achlioptas et al., 2021) has ~439k affective annotations over ~81k
WikiArt paintings, each an <art_style, painting, emotion, utterance> row across
9 emotion categories. We aggregate to a per-painting mood distribution and map
the 9 categories to Plutchik primaries (see ml/data/mood.py), so a mood-wheel
selection can rank real paintings by how strongly people felt that emotion.

Sourcing the CSV:
    ArtEmis v1/v2 require agreeing to terms at https://www.artemisdataset.org/ .
    Download `artemis_dataset_release_v0.csv` (or v2) and pass its path.

The join wrinkle:
    ArtEmis keys paintings by (art_style, painting_filename). `huggan/wikiart`
    does NOT expose filenames, so an exact per-painting join needs a WikiArt
    source that preserves filenames (e.g. the original WikiArt export, or an HF
    mirror that keeps `file_name`). Until then, `style_mood_prior()` gives a
    per-style mood prior that attaches to any WikiArt work as a defensible
    fallback. Both paths are provided below.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .mood import ARTEMIS_TO_PLUTCHIK
from .schema import Artwork


def _artemis_key(art_style: str, painting: str) -> str:
    return f"{art_style.strip().lower()}/{painting.strip().lower()}"


def load_artemis_moods(csv_path: str | Path) -> dict[str, dict[str, float]]:
    """Return {(<style>/<painting>): {plutchik_primary: normalized_weight}}.

    Counts emotion votes per painting, maps each to a Plutchik primary, and
    normalizes so weights sum to 1.0 per painting.
    """
    import csv

    votes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            primary = ARTEMIS_TO_PLUTCHIK.get((row.get("emotion") or "").strip().lower())
            if primary is None:
                continue
            key = _artemis_key(row.get("art_style", ""), row.get("painting", ""))
            votes[key][primary] += 1.0

    moods: dict[str, dict[str, float]] = {}
    for key, prim_counts in votes.items():
        total = sum(prim_counts.values())
        if total > 0:
            moods[key] = {p: round(c / total, 4) for p, c in prim_counts.items()}
    return moods


def style_mood_prior(moods: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Collapse per-painting moods to a per-style prior (fallback join key).

    Key is the WikiArt style (the part before '/'). Useful when painting-level
    filenames are unavailable, so every work of a style inherits its mood prior.
    """
    agg: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for key, dist in moods.items():
        style = key.split("/", 1)[0]
        for p, w in dist.items():
            agg[style][p] += w
    priors: dict[str, dict[str, float]] = {}
    for style, prim in agg.items():
        total = sum(prim.values())
        if total > 0:
            priors[style] = {p: round(w / total, 4) for p, w in prim.items()}
    return priors


def attach_moods(
    artworks: list[Artwork],
    moods: dict[str, dict[str, float]],
    style_priors: dict[str, dict[str, float]] | None = None,
) -> int:
    """Attach ArtEmis moods to WikiArt works in place. Returns count attached.

    Tries an exact (style/painting) join first; falls back to the per-style prior
    when a painting-level key is unavailable.
    """
    attached = 0
    for art in artworks:
        if art.source != "wikiart":
            continue
        style = (art.style or art.culture_raw or "").strip().lower().replace(" ", "_")
        # Exact join if the work carries a painting filename in source_id/title.
        painting = (art.source_id or "").strip().lower()
        dist = moods.get(_artemis_key(style, painting))
        if dist is None and style_priors is not None:
            dist = style_priors.get(style)
        if dist:
            for primary, weight in dist.items():
                art.add_mood(primary, weight)
            art.normalize_mood_scores()
            attached += 1
    return attached


# --- self-test (no gated data needed) --------------------------------------

def _selftest() -> None:
    """Prove the aggregation + Plutchik mapping with a synthetic sample."""
    import csv
    import tempfile

    rows = [
        # impressionism/starry_night — mostly awe (->surprise) + contentment (->joy)
        ("Impressionism", "starry_night.jpg", "awe"),
        ("Impressionism", "starry_night.jpg", "awe"),
        ("Impressionism", "starry_night.jpg", "contentment"),
        ("Impressionism", "starry_night.jpg", "something else"),  # dropped
        # expressionism/scream — fear + sadness
        ("Expressionism", "the_scream.jpg", "fear"),
        ("Expressionism", "the_scream.jpg", "sadness"),
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
        w = csv.writer(f)
        w.writerow(["art_style", "painting", "emotion", "utterance"])
        for s, p, e in rows:
            w.writerow([s, p, e, "..."])
        path = f.name

    moods = load_artemis_moods(path)
    starry = moods["impressionism/starry_night.jpg"]
    assert abs(sum(starry.values()) - 1.0) < 1e-6, starry
    assert starry["surprise"] > starry["joy"], starry          # 2 awe > 1 contentment
    assert "impressionism/starry_night.jpg" in moods
    scream = moods["expressionism/the_scream.jpg"]
    assert set(scream) == {"fear", "sadness"}, scream

    priors = style_mood_prior(moods)
    assert "impressionism" in priors and "expressionism" in priors

    art = Artwork(uid="wikiart:0", source="wikiart", source_id="starry_night.jpg",
                  style="Impressionism")
    n = attach_moods([art], moods, priors)
    assert n == 1 and art.top_mood == "surprise", (n, art.mood_scores)
    print("artemis self-test OK:", starry, "| top_mood:", art.top_mood)


if __name__ == "__main__":
    _selftest()
