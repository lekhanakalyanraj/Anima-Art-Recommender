"""Append new artworks (e.g. NASA space photos) to an existing index in place.

Embeds only the new records with the SAME CLIP model the index was built with,
scores them for aesthetics, and appends to corpus.faiss / corpus_emb.npy /
corpus_meta.jsonl — keeping row alignment. Avoids re-embedding the whole corpus.

Usage:
    python -m ml.embeddings.append_index --index data/processed/index_world --sources nasa --limit 150
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def append(index_dir: Path, sources: list[str], limit: int, batch_size: int = 16) -> None:
    from ml.data.sources import REGISTRY

    from .clip_embed import ClipEncoder

    meta_path = index_dir / "corpus_meta.jsonl"
    emb_path = index_dir / "corpus_emb.npy"
    faiss_path = index_dir / "corpus.faiss"

    existing_uids = {json.loads(line)["uid"] for line in meta_path.open(encoding="utf-8")}

    # 1) ingest new records (skip anything already indexed)
    new_records: list[dict] = []
    for key in sources:
        ing = REGISTRY[key]()
        print(f"→ ingesting '{key}' (limit={limit}) …")
        for art in ing.iter_artworks(limit=limit):
            d = art.model_dump()
            if d["uid"] not in existing_uids and d.get("image_url"):
                new_records.append(d)
                existing_uids.add(d["uid"])
    print(f"ingested {len(new_records)} new records")
    if not new_records:
        print("nothing new to append")
        return

    # 2) embed + aesthetic score (same model as the index)
    encoder = ClipEncoder()
    from .aesthetic import AestheticScorer
    scorer = AestheticScorer(device=encoder.device)
    print(f"CLIP {encoder.dim}-d on {encoder.device}; embedding + scoring …")

    embs: list[np.ndarray] = []
    kept: list[dict] = []
    n = len(new_records)
    for start in range(0, n, batch_size):
        batch = new_records[start:start + batch_size]
        pils, rows = [], []
        for r in batch:
            try:
                pils.append(encoder._load_image(r["image_url"]))
                rows.append(r)
            except Exception:
                continue
        if not pils:
            continue
        vecs = encoder.embed_pil_batch(pils)
        scores = scorer.score_pil_batch(pils)
        for r, v, s in zip(rows, vecs, scores):
            r["aesthetic_score"] = round(float(s), 3)
            embs.append(v)
            kept.append(r)
        print(f"  processed {min(start + batch_size, n)}/{n} …", flush=True)

    if not kept:
        print("no usable images to append")
        return
    new_emb = np.vstack(embs).astype("float32")

    # 3) append to the index, embeddings, and metadata (order preserved)
    old_emb = np.load(emb_path)
    if old_emb.shape[1] != new_emb.shape[1]:
        raise SystemExit(f"dim mismatch: index is {old_emb.shape[1]}d, new is {new_emb.shape[1]}d "
                         f"— embed with the same CLIP model the index was built with.")
    import faiss
    index = faiss.read_index(str(faiss_path))
    index.add(new_emb)
    faiss.write_index(index, str(faiss_path))
    np.save(emb_path, np.vstack([old_emb, new_emb]))
    with meta_path.open("a", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    print(f"✓ appended {len(kept)} — index now {index.ntotal} vectors")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--sources", default="nasa")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()
    append(args.index, [s.strip() for s in args.sources.split(",")], args.limit, args.batch_size)


if __name__ == "__main__":
    main()
