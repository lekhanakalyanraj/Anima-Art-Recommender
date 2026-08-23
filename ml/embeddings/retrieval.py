"""Curated, mood-aware, culturally-fair art retrieval — a museum, not a search.

Ranking blends three signals instead of raw CLIP similarity:
  * mood/CLIP match        — does the image fit the selected mood's visual prompt
  * aesthetic quality      — LAION aesthetic score, but normalized WITHIN each
                             world region so the model's Western/photographic bias
                             doesn't demote folk art, miniatures, and sculpture
  * region-aware MMR       — penalize redundancy AND monoculture, so a "room"
                             spans traditions with real variety
plus a per-region quality gate (drop works weak *for their own tradition*, not an
absolute cutoff that would cull whole cultures).

Therapeutic intent (spec: "soothe, uplift or inspire"): a distress selection
(sadness/fear/anger/disgust) is answered with regulating imagery.
"""

from __future__ import annotations

import json
import os
import statistics as st
from pathlib import Path

import numpy as np

from ..data.mood import DISTRESS

MOOD_PROMPTS: dict[str, str] = {
    "joy": "a bright, warm, joyful painting full of light and cheerful color",
    "trust": "a calm, gentle, harmonious artwork evoking safety and warmth",
    "fear": "a dark, ominous, tense painting with looming shadows",
    "surprise": "an awe-inspiring, wondrous artwork with a vast dramatic sky",
    "sadness": "a melancholic, muted, somber painting in cool tones",
    "disgust": "a grotesque, unsettling, murky artwork",
    "anger": "a turbulent, fiery, intense painting with violent red strokes",
    "anticipation": "a vivid, energetic artwork full of movement and curiosity",
}

THERAPEUTIC_REDIRECT: dict[str, str] = {
    "sadness": "trust", "fear": "trust", "anger": "joy", "disgust": "surprise",
}

# Plutchik intensity ring → a suffix that nudges CLIP toward calmer or more
# vivid imagery (serenity vs joy vs ecstasy).
_INTENSITY_SUFFIX: dict[str, str] = {
    "mild": ", soft, muted, understated and quiet",
    "base": "",
    "intense": ", intense, vivid, dramatic and overwhelming",
}

_DROP_CATEGORIES = {"other"}
_GLOBAL_AES_STD = 0.9  # fallback spread for small/thin regions


class MoodArtRetriever:
    def __init__(self, index_dir: str | Path):
        # When torch is installed its OpenMP runtime must initialize before faiss
        # (see __init__.py). In the lightweight serve build torch isn't present —
        # precomputed mood vectors mean we never need CLIP — so its absence is fine.
        try:
            import torch  # noqa: F401
        except ImportError:
            pass
        import faiss

        self.dir = Path(index_dir)
        self.index = faiss.read_index(str(self.dir / "corpus.faiss"))
        with (self.dir / "corpus_meta.jsonl").open(encoding="utf-8") as f:
            self.meta = [json.loads(line) for line in f]
        emb_path = self.dir / "corpus_emb.npy"
        self.embs = np.load(emb_path) if emb_path.exists() else None  # for MMR
        self._region_stats = self._compute_region_stats()
        self._encoder = None  # lazy

        # Sources to hide from results (comma-separated env). Used when a host's
        # images become unreachable — e.g. AIC put its IIIF server behind a
        # Cloudflare bot-challenge, so its images 403 and must be excluded.
        self.drop_sources = {
            s.strip() for s in os.environ.get("ART_EXCLUDE_SOURCES", "").split(",") if s.strip()
        }

        # Precomputed mood-query vectors (see precompute_moods.py). When present,
        # by_mood() uses them instead of embedding prompts live, so the server
        # needs no torch/CLIP at runtime.
        self._mood_vecs: dict[str, np.ndarray] | None = None
        mv = self.dir / "mood_vectors.npz"
        if mv.exists():
            d = np.load(mv, allow_pickle=True)
            self._mood_vecs = {
                k: v.astype("float32")
                for k, v in zip(d["keys"].tolist(), d["vecs"])
            }

    @property
    def encoder(self):
        if self._encoder is None:
            from .clip_embed import ClipEncoder
            self._encoder = ClipEncoder()
        return self._encoder

    def _query_vec(self, target: str, intensity: str, prompt: str) -> np.ndarray:
        """Vector for a mood query: precomputed if available, else embed live."""
        if self._mood_vecs is not None:
            v = self._mood_vecs.get(f"{target}|{intensity}")
            if v is not None:
                return v
        return self.encoder.embed_text([prompt])[0]

    # --- fairness: per-region aesthetic normalization -----------------------

    def _compute_region_stats(self) -> dict[str, tuple[float, float]]:
        """{region: (mean, std)} of aesthetic scores, for within-tradition z-scoring."""
        by_region: dict[str, list[float]] = {}
        for a in self.meta:
            if "aesthetic_score" in a:
                by_region.setdefault(a.get("region", "unknown"), []).append(a["aesthetic_score"])
        stats: dict[str, tuple[float, float]] = {}
        for region, vals in by_region.items():
            mean = st.mean(vals)
            std = st.pstdev(vals) if len(vals) >= 5 else _GLOBAL_AES_STD
            stats[region] = (mean, max(std, 0.3))
        return stats

    def _region_z(self, a: dict) -> float:
        """Aesthetic z-score within the work's own region (0.0 if unscored)."""
        if "aesthetic_score" not in a:
            return 0.0
        mean, std = self._region_stats.get(a.get("region", "unknown"), (a["aesthetic_score"], _GLOBAL_AES_STD))
        return (a["aesthetic_score"] - mean) / std

    def _fair_aesthetic(self, a: dict, fair: bool) -> float:
        """Aesthetic term in [0,1]. Fair mode: within-region z mapped to [0,1]."""
        if not fair:
            # absolute: map raw 4–9 band to [0,1]
            if "aesthetic_score" not in a:
                return 0.5
            return float(np.clip((a["aesthetic_score"] - 4.0) / 5.0, 0.0, 1.0))
        return float(np.clip((self._region_z(a) + 2.0) / 4.0, 0.0, 1.0))  # z in [-2,2] → [0,1]

    # --- candidate scoring (shared) -----------------------------------------

    def _score_candidates(
        self, qvec: np.ndarray, *,
        target_mood: str | None, region: str | None, category: str | None,
        w_clip: float, w_aesthetic: float, mood_boost: float,
        fair: bool, gate_region_z: float, pool: int,
        exclude: set[str] | None = None, jitter: float = 0.0,
    ) -> tuple[list[int], np.ndarray]:
        """Search + filter + gate + blended relevance. Returns (meta_idxs, relevance).

        `exclude` drops already-seen uids; `jitter` adds randomness to the relevance
        so repeated calls surface different (but still fitting) works.
        """
        scores, idxs = self.index.search(qvec.reshape(1, -1), pool)
        scores, idxs = scores[0], idxs[0]

        cand: list[tuple[int, float]] = []
        for sim, i in zip(scores, idxs):
            if i == -1:
                continue
            a = self.meta[i]
            if a.get("source") in self.drop_sources:
                continue
            if exclude and a.get("uid") in exclude:
                continue
            if region and a.get("region") != region:
                continue
            if category and a.get("category") != category:
                continue
            if a.get("category") in _DROP_CATEGORIES:
                continue
            if "aesthetic_score" in a and self._region_z(a) < gate_region_z:
                continue
            cand.append((i, float(sim)))
        if not cand:
            return [], np.zeros(0)

        sims = np.array([c[1] for c in cand])
        lo, hi = sims.min(), sims.max()
        clip_norm = (sims - lo) / (hi - lo) if hi > lo else np.ones_like(sims)
        relevance = np.zeros(len(cand))
        for j, (i, _) in enumerate(cand):
            a = self.meta[i]
            rel = w_clip * clip_norm[j] + w_aesthetic * self._fair_aesthetic(a, fair)
            if target_mood and target_mood in (a.get("mood_scores") or {}):
                rel += mood_boost * float(a["mood_scores"][target_mood])
            relevance[j] = rel
        if jitter > 0.0 and len(relevance):
            span = float(relevance.max() - relevance.min()) or 1.0
            relevance = relevance + np.random.uniform(0.0, jitter * span, size=len(relevance))
        return [c[0] for c in cand], relevance

    # --- core curation ------------------------------------------------------

    def _curate(
        self, qvec: np.ndarray, k: int, *,
        target_mood: str | None, region: str | None, category: str | None,
        w_clip: float, w_aesthetic: float, mood_boost: float,
        fair: bool, gate_region_z: float, region_diversity: float,
        mmr_lambda: float, pool: int,
        exclude: set[str] | None = None, jitter: float = 0.0,
    ) -> list[dict]:
        meta_idxs, relevance = self._score_candidates(
            qvec, target_mood=target_mood, region=region, category=category,
            w_clip=w_clip, w_aesthetic=w_aesthetic, mood_boost=mood_boost,
            fair=fair, gate_region_z=gate_region_z, pool=pool,
            exclude=exclude, jitter=jitter)
        if not meta_idxs:
            return []
        order = self._mmr(meta_idxs, relevance, k, mmr_lambda, region_diversity)
        return [{**self.meta[i], "_score": round(float(s), 4), "_rank": r}
                for r, (i, s) in enumerate(order)]

    def _curate_balanced(
        self, qvec: np.ndarray, k: int, *,
        target_mood: str | None, category: str | None,
        w_clip: float, w_aesthetic: float, mood_boost: float,
        fair: bool, gate_region_z: float, min_region_relevance: float, pool: int,
        exclude: set[str] | None = None, jitter: float = 0.0,
    ) -> list[dict]:
        """Region-balanced 'world museum' room: best-per-region, round-robin interleaved."""
        meta_idxs, relevance = self._score_candidates(
            qvec, target_mood=target_mood, region=None, category=category,
            w_clip=w_clip, w_aesthetic=w_aesthetic, mood_boost=mood_boost,
            fair=fair, gate_region_z=gate_region_z, pool=pool,
            exclude=exclude, jitter=jitter)
        if not meta_idxs:
            return []

        # group candidates by region, each sorted by relevance desc
        by_region: dict[str, list[tuple[int, float]]] = {}
        for i, rel in zip(meta_idxs, relevance):
            by_region.setdefault(self.meta[i].get("region", "unknown"), []).append((i, rel))
        for region in by_region:
            by_region[region].sort(key=lambda t: t[1], reverse=True)

        # drop regions whose *best* work is too weak to belong in this mood room
        top_rel = float(relevance.max())
        regions = [r for r, items in by_region.items()
                   if items[0][1] >= min_region_relevance * top_rel]
        # order regions so the most mood-relevant culture leads the walk
        regions.sort(key=lambda r: by_region[r][0][1], reverse=True)

        # round-robin: best of each region, then 2nd of each, … → interleaved cultures
        picked: list[tuple[int, float]] = []
        depth = 0
        while len(picked) < k and regions:
            progressed = False
            for r in regions:
                if depth < len(by_region[r]):
                    picked.append(by_region[r][depth])
                    progressed = True
                    if len(picked) >= k:
                        break
            if not progressed:
                break
            depth += 1
        return [{**self.meta[i], "_score": round(float(s), 4), "_rank": rank}
                for rank, (i, s) in enumerate(picked)]

    def _mmr(self, meta_idxs: list[int], relevance: np.ndarray, k: int,
             lam: float, region_diversity: float) -> list[tuple[int, float]]:
        """MMR with a region-monoculture penalty for cross-cultural variety."""
        if self.embs is None:
            order = np.argsort(-relevance)[:k]
            return [(meta_idxs[j], relevance[j]) for j in order]
        cand_embs = self.embs[meta_idxs]
        regions = [self.meta[i].get("region", "unknown") for i in meta_idxs]
        selected: list[int] = []
        sel_region_count: dict[str, int] = {}
        remaining = list(range(len(meta_idxs)))
        picked: list[tuple[int, float]] = []
        while remaining and len(selected) < k:
            best_j, best_score = None, -1e9
            for j in remaining:
                vis_redundancy = float(np.max(cand_embs[j] @ cand_embs[selected].T)) if selected else 0.0
                region_redundancy = sel_region_count.get(regions[j], 0) / max(k, 1)
                redundancy = vis_redundancy + region_diversity * region_redundancy
                mmr = (1 - lam) * relevance[j] - lam * redundancy
                if mmr > best_score:
                    best_score, best_j = mmr, j
            selected.append(best_j)
            sel_region_count[regions[best_j]] = sel_region_count.get(regions[best_j], 0) + 1
            remaining.remove(best_j)
            picked.append((meta_idxs[best_j], relevance[best_j]))
        return picked

    # --- public API ---------------------------------------------------------

    def by_mood(
        self, mood: str, k: int = 12, *, therapeutic: bool = True,
        balanced: bool = True, intensity: str = "base",
        region: str | None = None, category: str | None = None,
        w_clip: float = 0.6, w_aesthetic: float = 0.4, mood_boost: float = 0.15,
        fair: bool = True, gate_region_z: float = -1.25,
        region_diversity: float = 0.35, mmr_lambda: float = 0.3,
        min_region_relevance: float = 0.55,
        exclude: set[str] | None = None, jitter: float = 0.4,
    ) -> list[dict]:
        target = mood
        if therapeutic and mood in DISTRESS:
            target = THERAPEUTIC_REDIRECT.get(mood, mood)
        prompt = MOOD_PROMPTS.get(target, f"an artwork evoking {target}")
        prompt += _INTENSITY_SUFFIX.get(intensity, "")
        qvec = self._query_vec(target, intensity, prompt)
        # Balanced mode builds a cross-cultural room; a region filter makes it moot.
        if balanced and not region:
            return self._curate_balanced(
                qvec, k, target_mood=target, category=category,
                w_clip=w_clip, w_aesthetic=w_aesthetic, mood_boost=mood_boost,
                fair=fair, gate_region_z=gate_region_z,
                min_region_relevance=min_region_relevance, pool=min(self.index.ntotal, 1000),
                exclude=exclude, jitter=jitter,
            )
        return self._curate(
            qvec, k, target_mood=target, region=region, category=category,
            w_clip=w_clip, w_aesthetic=w_aesthetic, mood_boost=mood_boost,
            fair=fair, gate_region_z=gate_region_z, region_diversity=region_diversity,
            mmr_lambda=mmr_lambda, pool=max(k * 20, 300),
            exclude=exclude, jitter=jitter,
        )

    def by_text(
        self, query: str, k: int = 12, *, region: str | None = None,
        category: str | None = None, w_clip: float = 0.7, w_aesthetic: float = 0.3,
        fair: bool = True, gate_region_z: float = -1.25,
        region_diversity: float = 0.35, mmr_lambda: float = 0.3,
        exclude: set[str] | None = None, jitter: float = 0.0,
    ) -> list[dict]:
        qvec = self.encoder.embed_text([query])[0]
        return self._curate(
            qvec, k, target_mood=None, region=region, category=category,
            w_clip=w_clip, w_aesthetic=w_aesthetic, mood_boost=0.0,
            fair=fair, gate_region_z=gate_region_z, region_diversity=region_diversity,
            mmr_lambda=mmr_lambda, pool=max(k * 12, 120),
            exclude=exclude, jitter=jitter,
        )


def _demo() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Query the curated mood-art index.")
    ap.add_argument("--index", default="data/processed/index")
    ap.add_argument("--mood", help="joy|trust|fear|surprise|sadness|disgust|anger|anticipation")
    ap.add_argument("--text", help="free-text query instead of a mood")
    ap.add_argument("--region", default=None)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--no-therapeutic", action="store_true")
    ap.add_argument("--absolute", action="store_true", help="disable culturally-fair normalization")
    ap.add_argument("--no-balance", action="store_true", help="relevance-first instead of region-balanced")
    args = ap.parse_args()

    r = MoodArtRetriever(args.index)
    fair = not args.absolute
    if args.text:
        results = r.by_text(args.text, k=args.k, region=args.region, fair=fair)
        print(f"text query: {args.text!r} | fair={fair}")
    else:
        mood = args.mood or "joy"
        results = r.by_mood(mood, k=args.k, region=args.region, balanced=not args.no_balance,
                            therapeutic=not args.no_therapeutic, fair=fair)
        print(f"mood: {mood} | therapeutic={not args.no_therapeutic} | fair={fair} | balanced={not args.no_balance}")
    for a in results:
        aes = a.get("aesthetic_score", "—")
        print(f"  {a['_score']:.3f} aes={aes} [{a.get('region',''):15}] "
              f"[{a.get('source',''):9}] {a.get('title','')[:44]!r}")


if __name__ == "__main__":
    _demo()
