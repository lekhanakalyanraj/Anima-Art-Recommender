# Anima — a quiet gallery for how you feel

Anima maps how you feel (Plutchik's wheel of emotions) to curated world art. Pick
a feeling and an intensity, and it opens a contemplative, one-at-a-time gallery
walk drawn from a 1,647-work corpus spanning museums (the Met, Cleveland, Art
Institute of Chicago), Indian art, and NASA's cosmos — ranked with CLIP ViT-L/14
+ FAISS, region-balanced and aesthetically curated so each room feels like a
museum, not a search.
## System
<img width="600" height="600" alt="Screenshot 2026-08-24 at 10 32 07 AM" src="https://github.com/user-attachments/assets/2fe3afda-b468-455b-82d8-eb865eea1b06" />
<img width="600" height="600" alt="Screenshot 2026-08-24 at 10 32 26 AM" src="https://github.com/user-attachments/assets/9355a8d2-1528-4515-91bb-c491d0f99df9" />
<img width="600" height="600" alt="Screenshot 2026-08-24 at 10 32 40 AM" src="https://github.com/user-attachments/assets/79fde2fc-1036-4056-935c-f4a86f371176" />

## Architecture

- **`apps/web`** — Vite + React frontend (static). Deploys to Hostinger.
- **`apps/api`** — FastAPI backend serving the curated retriever. Deploys to a
  free host (Render).
- **`ml`** — data ingestion + CLIP/FAISS embedding + retrieval pipeline.

The 24 mood-room query vectors are **precomputed** into the index
(`mood_vectors.npz`), so the running API needs no torch/CLIP — just FAISS +
NumPy. That keeps it small enough to run free.

## Backend API

- `GET /api/v1/health` — index status
- `GET /api/v1/moods` — the mood taxonomy
- `GET /api/v1/room?mood=joy&intensity=base&k=14&session=<id>` — a curated room
- `GET /api/v1/img?u=...` — proxy for WAF-protected museum images
- `/media/...` — locally hosted images (Indian art)

Config via env: `ART_CORS_ORIGINS`, `ART_INDEX_DIR`, `ART_MEDIA_DIR`.

See [DEPLOY.md](DEPLOY.md) for deployment steps.

## Regenerating the mood vectors

If you change the mood prompts in `ml/embeddings/retrieval.py`, re-run (needs the
CLIP model, e.g. on the machine that built the index):

```bash
python -m ml.embeddings.precompute_moods --index data/processed/index_world
```
