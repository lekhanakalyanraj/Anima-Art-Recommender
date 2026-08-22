"""Build the FAISS index + aesthetic scores from a corpus.jsonl.

Loads each image once and computes BOTH its CLIP retrieval embedding and its
aesthetic score, so a museum-style curated ranking has beauty as a first-class
signal. Drops records whose image failed to load. Writes:
    corpus.faiss        — FAISS inner-product index over L2-normalized vectors
    corpus_meta.jsonl   — artwork metadata (+ aesthetic_score), row-aligned
    corpus_emb.npy      — the raw embeddings (for MMR diversity + eval)

Usage:
    python -m ml.embeddings.build_index --corpus data/processed/corpus.jsonl --out data/processed/index
    python -m ml.embeddings.build_index --corpus ... --no-aesthetic     # skip scoring
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

_DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "processed" / "corpus.jsonl"


def build(corpus_path: Path, out_dir: Path, batch_size: int = 32,
          score_aesthetics: bool = True) -> None:
    from .clip_embed import ClipEncoder  # torch first, faiss imported after

    records = [json.loads(line) for line in corpus_path.open(encoding="utf-8")]
    records = [r for r in records if r.get("image_url")]
    print(f"loaded {len(records)} artworks with images from {corpus_path.name}")

    encoder = ClipEncoder()
    scorer = None
    if score_aesthetics:
        from .aesthetic import AestheticScorer
        scorer = AestheticScorer(device=encoder.device)
        print(f"aesthetic scorer on {scorer.device}")
    print(f"CLIP {encoder.dim}-d on {encoder.device}; embedding + scoring …")

    embs: list[np.ndarray] = []
    kept: list[dict] = []
    n = len(records)
    for start in range(0, n, batch_size):
        batch = records[start:start + batch_size]
        pils, rows = [], []
        for r in batch:
            try:
                pils.append(encoder._load_image(r["image_url"]))
                rows.append(r)
            except Exception:
                continue  # unreachable/corrupt image → drop
        if not pils:
            continue
        vecs = encoder.embed_pil_batch(pils)
        scores = scorer.score_pil_batch(pils) if scorer else [None] * len(pils)
        for r, v, s in zip(rows, vecs, scores):
            if s is not None:
                r["aesthetic_score"] = round(float(s), 3)
            embs.append(v)
            kept.append(r)
        print(f"  processed {min(start + batch_size, n)}/{n} …", flush=True)

    emb_arr = np.vstack(embs).astype("float32") if embs else np.zeros((0, encoder.dim), "float32")
    print(f"embedded {len(kept)} usable images ({len(records) - len(kept)} failed to load)")

    import faiss  # only now, after all torch work

    index = faiss.IndexFlatIP(encoder.dim)
    index.add(emb_arr)

    out_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_dir / "corpus.faiss"))
    np.save(out_dir / "corpus_emb.npy", emb_arr)
    with (out_dir / "corpus_meta.jsonl").open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    print(f"✓ index built: {index.ntotal} vectors → {out_dir}")
    if scorer:
        vals = [r["aesthetic_score"] for r in kept if "aesthetic_score" in r]
        if vals:
            print(f"  aesthetic score: min={min(vals):.2f} mean={np.mean(vals):.2f} max={max(vals):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    ap.add_argument("--out", type=Path, default=_DEFAULT_CORPUS.parent / "index")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--no-aesthetic", action="store_true", help="skip aesthetic scoring")
    args = ap.parse_args()
    build(args.corpus, args.out, args.batch_size, score_aesthetics=not args.no_aesthetic)


if __name__ == "__main__":
    main()
