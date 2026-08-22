"""Precompute the fixed mood-query CLIP vectors.

The serving API only ever needs the 24 mood-room queries (8 Plutchik prompts x 3
intensity suffixes). Those never change, so we embed them once here — wherever the
CLIP model is available — and the deployed API loads the vectors instead of
running torch + CLIP at request time. That drops the serve image from ~3GB to a
couple hundred MB and lets it run on a free host.

Run once (needs torch + open_clip + the CLIP weights):

    python -m ml.embeddings.precompute_moods --index data/processed/index_world

Writes <index>/mood_vectors.npz:
    keys : "<mood>|<intensity>"   e.g. "trust|mild"  (aligned to rows of vecs)
    vecs : float32 [24, dim]      L2-normalized, same space as the corpus index
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from .retrieval import MOOD_PROMPTS, _INTENSITY_SUFFIX


def build(index_dir: str | Path) -> Path:
    """Embed every (mood, intensity) prompt and save them next to the index."""
    from .clip_embed import ClipEncoder

    enc = ClipEncoder()
    keys: list[str] = []
    prompts: list[str] = []
    for mood, base in MOOD_PROMPTS.items():
        for intensity, suffix in _INTENSITY_SUFFIX.items():
            keys.append(f"{mood}|{intensity}")
            prompts.append(base + suffix)

    vecs = np.asarray(enc.embed_text(prompts), dtype="float32")
    out = Path(index_dir) / "mood_vectors.npz"
    np.savez(out, keys=np.array(keys), vecs=vecs)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", default="data/processed/index_world")
    args = ap.parse_args()
    out = build(args.index)
    d = np.load(out, allow_pickle=True)
    print(f"wrote {out}  ({len(d['keys'])} vectors, dim={d['vecs'].shape[1]})")
