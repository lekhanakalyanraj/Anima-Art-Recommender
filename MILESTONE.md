# Anima — Project Milestone / Resume Notes

_Last updated: 2026-08-24_

A quick map of where the project stands, so you can pick it back up without
re-deriving anything. For the how-to steps see [DEPLOY.md](DEPLOY.md); for the
project overview see [README.md](README.md).

---

## TL;DR — where things fall

| Piece | Status |
|---|---|
| ML pipeline + index (1,647 works) | ✅ Done |
| Backend (FastAPI, lightweight, no torch) | ✅ **Live on Render** |
| Frontend (Vite/React) build | ✅ Built, points at live backend |
| **Frontend hosting on Hostinger** | ⏳ **NOT DONE — the one thing left** |
| Custom domain `anima.lekhanakraj.com` | ⏳ Not set up yet |

**Live backend:** https://anima-art-recommender.onrender.com/api/v1/health
**Frontend:** not deployed yet (runs locally; `dist/` is ready to upload).

---

## ▶️ The one remaining task: put the frontend on Hostinger

Everything else is done and verified. To finish:

1. hPanel → **Domains → Subdomains** → create `anima` under `lekhanakraj.com`
   (note its document root, e.g. `public_html/anima`).
2. **File Manager / FTP** → upload the **contents of** `apps/web/dist/`
   (`index.html`, `assets/`, `fonts/`) so `index.html` sits at the subdomain root.
3. Visit **https://anima.lekhanakraj.com**.

> If you rebuild the frontend first (`cd apps/web && npm run build`), upload the
> fresh `dist/`. The live Render URL is already baked into
> `apps/web/.env.production`, so no edits needed.

---

## Architecture (as deployed)

- **Frontend** → static Vite build → Hostinger (subdomain, shared hosting).
- **Backend** → FastAPI + FAISS + NumPy (no torch/CLIP) → Render free tier.
  The 24 mood-query vectors are precomputed (`mood_vectors.npz`), so the server
  never loads CLIP. Fits the 512MB free instance; cold-starts in seconds.
- Frontend calls Render cross-origin; `apps/web/src/api.ts` prefixes image URLs
  with `VITE_API_BASE`; backend CORS allows the lekhanakraj.com domains.

_Why not HuggingFace: HF made Docker/compute Spaces PRO-only ($9/mo) in July 2026,
so we went lightweight-on-Render for $0. Fly.io no longer has a free tier; Koyeb
is the backup host._

---

## Run it locally

Backend (from project root):
```bash
source .venv/bin/activate
ART_EXCLUDE_SOURCES=aic uvicorn apps.api.main:app --port 8000
```
Frontend dev (talks to local backend via Vite proxy):
```bash
cd apps/web && npm run dev
```
Preview the production build (talks to the LIVE Render backend; use port 5173 so
CORS allows it):
```bash
cd apps/web && npm run build && npx vite preview --port 5173
```

---

## Known decisions & gotchas

- **AIC (Art Institute of Chicago) is excluded.** Their image server went behind a
  Cloudflare bot-challenge, so its images 403. Hidden via `ART_EXCLUDE_SOURCES=aic`
  (set in the `Dockerfile` for Render; pass it locally too). Corpus is effectively
  **1,350 works** (AIC was 297). Remove that env var if their access is ever
  restored, or re-host those images via Wikimedia + `/media` (not done).
- **Render free tier sleeps** after ~15 min idle → first request ~30–50s, then
  fast. Optional keep-warm: cron-job.org ping to `/api/v1/health` (DEPLOY.md §3).
- **Font:** Oceanic Mono is used under its personal-use license (fine for a
  portfolio). Swap it in `apps/web/src/styles.css` if this ever goes commercial.
- **Data files vs .gitignore:** the index + images are force-added past
  `.gitignore` (`git add -f data/processed/index_world data/raw/images`).

---

## Git state

- Repo: **`lekhanakalyanraj/Anima-Art-Recommender`** (private), pushed via SSH
  alias `github-personal` (key `~/.ssh/id_ed25519_personal`).
- Commits are authored as **Lekhana Kalyan Raj <krajlekhana@gmail.com>** (set
  `--local` for this repo only; your other repos keep the UNSW identity).
  - To get your avatar/contribution graph, add `krajlekhana@gmail.com` to your
    personal GitHub → Settings → Emails (verify it).
- ⚠️ **1 commit not yet pushed:** `Point frontend at live Render URL`. Run:
  ```bash
  git push
  ```

---

## If you want to go further later

- Re-host AIC images via Wikimedia Commons → `/media` (recover ~300 works).
- Saved-pieces view (the ♥ already tracks likes client-side).
- Real ArtEmis emotion labels; Wikimedia temple-architecture ingestor.
- Keep-warm cron so the first visit is never slow.
