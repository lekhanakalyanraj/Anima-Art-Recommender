# Data layer — world-art corpus

Builds one normalized, mood-tagged art corpus spanning **world** traditions —
not just the Western canon — to power the mood-wheel recommender.

## Sources

| key | source | coverage | access | images |
|---|---|---|---|---|
| `wikiart` | huggan/wikiart | Western canon (base, 81k) | HF `datasets` | embedded → saved local |
| `met` | The Met Open Access API | Asian, Islamic, African/Oceania/Americas, Egyptian, Ancient Near East | public, no key | URL (CC0) |
| `cleveland` | Cleveland Museum of Art API | Indian, Himalayan, East Asian | public, no key | URL (CC0) |
| `aic` | Art Institute of Chicago API | Indian/Himalayan/SE Asian (Alsdorf), African, Amerindian | public, no key | IIIF URL (CC0) |
| `indian_art` | Divya0001/indian-art-styles | 34 Indian styles (madhubani, warli, gond, pattachitra, tanjore, mughal…) | HF `datasets` | embedded → saved local |
| `commons` *(fast follow)* | Wikimedia Commons | temple architecture | API | URL |

## Unified schema

Every source emits [`Artwork`](schema.py): identity (`uid = <source>:<id>`),
descriptive fields, `category` (painting/sculpture/architecture/folk_art/…),
`region` (controlled world regions), `image_url` (http or local path), rights,
and `mood_scores` (Plutchik primaries). See [`normalize.py`](normalize.py) for
region/category mapping and [`mood.py`](mood.py) for the Plutchik + ArtEmis
vocabulary.

## Run it

```bash
pip install -r ../../requirements.txt      # or: pip install requests pydantic (museums only)

# museum APIs (no key, no heavy deps)
python -m ml.data.ingest --sources met,cleveland,aic --limit 200

# everything (WikiArt + Indian art need `datasets`; download images)
python -m ml.data.ingest --sources all --limit 500
```

The orchestrator de-dups by `uid`, writes `data/processed/corpus.jsonl`, and
prints a **coverage report** by source / region / category with a non-Western %.

## Mood layer (ArtEmis)

[`artemis.py`](artemis.py) turns ArtEmis's 9 emotion categories into per-painting
Plutchik mood distributions and attaches them to WikiArt works.

- Get the CSV (terms) from https://www.artemisdataset.org/
- **Join caveat:** ArtEmis keys paintings by filename, which `huggan/wikiart`
  doesn't expose. Exact per-painting join needs a filename-preserving WikiArt
  source; until then `style_mood_prior()` gives a per-style fallback.
- Logic is covered by a synthetic self-test: `python -m ml.data.artemis`.

## Retrieval (CLIP + FAISS)

`ml/embeddings/` turns the corpus into a searchable mood-art index.

```bash
python -m ml.embeddings.build_index --corpus data/processed/corpus.jsonl --out data/processed/index
python -m ml.embeddings.retrieval --mood joy --k 8            # mood-wheel query
python -m ml.embeddings.retrieval --mood sadness             # therapeutic redirect → calm
python -m ml.embeddings.retrieval --text "serene temple at dawn"
```

- [clip_embed.py](../embeddings/clip_embed.py) — open_clip ViT-B-32/laion2b, one
  shared image+text space (512-d), loads images from URL or local path.
- [build_index.py](../embeddings/build_index.py) — embeds every image, drops
  failed loads, writes `corpus.faiss` + row-aligned `corpus_meta.jsonl`.
- [retrieval.py](../embeddings/retrieval.py) — `MoodArtRetriever`: maps a Plutchik
  selection to a visual CLIP prompt, over-fetches, applies region/category
  filters + an ArtEmis mood boost. **Therapeutic mode** answers a distress
  selection (sadness/fear/anger/disgust) with regulating imagery.

**Two macOS gotchas handled** (documented in code):
- torch + faiss each bundle OpenMP → duplicate-libomp **segfault**. Fixed by a
  guard in `ml/embeddings/__init__.py` and by loading torch before faiss.
- AIC's IIIF image host 403s without a browser UA **and** an origin `Referer`;
  the image fetcher now sends both.

## Status

Done & verified live: schema, region/category normalization, Met/Cleveland/AIC
ingestors, orchestrator + coverage report, ArtEmis mapping logic, **CLIP
embeddings + FAISS index + mood/text retrieval** (proof corpus of 180 works).
Written, needs heavy deps to run: WikiArt + Indian art ingestors (`datasets`).
In progress: balanced world corpus (Met global depts + Indian art) → `index_world`.
Next: Commons temple ingestor; ArtEmis real CSV + WikiArt-filename join; FastAPI backend.
