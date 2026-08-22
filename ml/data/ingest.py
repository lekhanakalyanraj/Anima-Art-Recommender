"""Ingest orchestrator.

Runs selected sources with per-source limits, de-duplicates by uid, writes the
unified corpus to data/processed, and prints a coverage report by region and
category so 'world coverage' is a measured number, not an assumption.

Usage:
    python -m ml.data.ingest --sources met,cleveland,aic --limit 200
    python -m ml.data.ingest --sources all --limit 500 --out data/processed/corpus.jsonl
    python -m ml.data.ingest --sources wikiart --limit 1000            # HF, downloads images
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .schema import Artwork
from .sources import REGISTRY

_DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "corpus.jsonl"


def run_ingest(sources: list[str], limit: int | None, out_path: Path) -> list[Artwork]:
    corpus: dict[str, Artwork] = {}  # uid -> Artwork (dedup)
    per_source: Counter[str] = Counter()

    for key in sources:
        ingestor_cls = REGISTRY.get(key)
        if ingestor_cls is None:
            print(f"  ! unknown source '{key}' (known: {', '.join(REGISTRY)})")
            continue
        print(f"→ ingesting '{key}' (limit={limit}) …")
        ingestor = ingestor_cls()
        try:
            for art in ingestor.iter_artworks(limit=limit):
                if art.uid not in corpus:
                    corpus[art.uid] = art
                    per_source[key] += 1
        except Exception as e:  # keep partial progress from other sources
            print(f"  ! '{key}' failed after {per_source[key]} records: {type(e).__name__}: {e}")

    artworks = list(corpus.values())
    _write(artworks, out_path)
    _report(artworks, per_source)
    return artworks


def _write(artworks: list[Artwork], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for art in artworks:
            f.write(art.model_dump_json() + "\n")
    print(f"\n✓ wrote {len(artworks)} artworks → {out_path}")


def _report(artworks: list[Artwork], per_source: Counter[str]) -> None:
    print("\n=== Coverage report ===")
    print(f"total unique artworks: {len(artworks)}")

    print("\nby source:")
    for src, n in per_source.most_common():
        print(f"  {src:12} {n:>7}")

    print("\nby world region:")
    regions = Counter(a.region for a in artworks)
    for region, n in regions.most_common():
        pct = 100 * n / len(artworks) if artworks else 0
        print(f"  {region:22} {n:>7}  ({pct:4.1f}%)")

    print("\nby category:")
    cats = Counter(a.category for a in artworks)
    for cat, n in cats.most_common():
        print(f"  {cat:16} {n:>7}")

    non_western = sum(
        n for r, n in regions.items()
        if r not in ("european", "north_american", "unknown")
    )
    pct_nw = 100 * non_western / len(artworks) if artworks else 0
    print(f"\nnon-Western coverage: {non_western}/{len(artworks)} ({pct_nw:.1f}%)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest and normalize the world-art corpus.")
    ap.add_argument(
        "--sources", default="met,cleveland,aic",
        help="comma-separated source keys, or 'all'. Known: " + ", ".join(REGISTRY),
    )
    ap.add_argument("--limit", type=int, default=100, help="max records per source (omit for all)")
    ap.add_argument("--all-records", action="store_true", help="ignore --limit; pull everything")
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="output .jsonl path")
    args = ap.parse_args()

    sources = list(REGISTRY) if args.sources == "all" else [s.strip() for s in args.sources.split(",")]
    limit = None if args.all_records else args.limit
    run_ingest(sources, limit, args.out)


if __name__ == "__main__":
    main()
