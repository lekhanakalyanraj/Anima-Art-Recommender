# Deploying Anima

Two pieces, both **free**:

- **Backend** (FastAPI + FAISS, lightweight — no torch/CLIP) → **Render** free tier
- **Frontend** (static Vite build) → **Hostinger**, on a subdomain of `lekhanakraj.com`

The 24 mood-room query vectors are precomputed into the index
(`mood_vectors.npz`), so the server just searches FAISS + reranks in NumPy — it
fits Render's free 512 MB instance and cold-starts in seconds.

> **Why not HuggingFace?** As of July 2026 HF made Docker/compute Spaces require a
> paid PRO plan. Render's free tier needs no card and no PRO.

---

## 1. Backend → Render (free)

### 1a. Put the repo on GitHub

> ⚠️ **Gotcha:** the project's `.gitignore` excludes `*.faiss`, `data/raw/`, and
> `data/processed/*.jsonl` — which are the index + image files the server needs.
> The commands below **force-add** them with `-f`.

From the project root (`art-therapy-recommender/`):

```bash
git init
# App + deploy files
git add Dockerfile README.md DEPLOY.md requirements-serve.txt .dockerignore .gitignore
git add ml apps/api apps/web
# Index + images + precomputed mood vectors (force past .gitignore)
git add -f data/processed/index_world data/raw/images
git commit -m "Anima: lightweight API + web"
git branch -M main
```

Create an empty repo on GitHub (e.g. `anima`), then:

```bash
git remote add origin https://github.com/<your-username>/anima.git
git push -u origin main
```

### 1b. Create the Render service
1. Go to https://render.com → sign up (GitHub login is easiest) → **New → Web Service**.
2. Connect the `anima` repo.
3. Render auto-detects the **Dockerfile** and uses it. Settings:
   - **Name:** `anima-api` (this becomes `https://anima-api.onrender.com` — must
     match the frontend's `VITE_API_BASE`, see step 2a).
   - **Instance type:** **Free**.
   - No env vars needed in Render's dashboard — CORS already allows your domain,
     paths default correctly, and `ART_EXCLUDE_SOURCES=aic` is set in the
     Dockerfile (AIC's images sit behind a Cloudflare bot-challenge and can't be
     served; remove that line if their access is ever restored).
4. **Create Web Service.** First build takes ~3–5 min.
5. When live, check `https://anima-api.onrender.com/api/v1/health` →
   `{"status":"ok", ..., "artworks":1647}`.

> **Free-tier note:** the service spins down after ~15 min idle; the next request
> wakes it in ~30–50 s. See step 3 for an optional keep-warm.

---

## 2. Frontend → Hostinger

### 2a. Confirm the API URL
The build reads `apps/web/.env.production`, currently
`VITE_API_BASE=https://anima-api.onrender.com`. **Only if your Render service name
differs**, edit that file to the real URL.

### 2b. Build
```bash
cd apps/web
npm install        # first time only
npm run build      # outputs apps/web/dist/
```

### 2c. Create the subdomain in Hostinger
1. hPanel → **Domains → Subdomains** → create **`anima`** under `lekhanakraj.com`.
   Note its document root (e.g. `public_html/anima`).

### 2d. Upload the build
- hPanel → **File Manager** (or FTP) → open the subdomain's document root.
- Upload the **contents of `apps/web/dist/`** (the `index.html`, `assets/`, and
  `fonts/` folders) so `index.html` sits at the subdomain root.
- Visit **https://anima.lekhanakraj.com** — done.

> Assets use absolute paths (`/assets/…`, `/fonts/…`), so the build must live at a
> subdomain **root**. For a subfolder like `lekhanakraj.com/anima/`, set
> `base: "/anima/"` in `apps/web/vite.config.ts` and rebuild.

---

## 3. Optional: keep the API warm (still free)
Render's free tier gives ~750 instance-hours/month — enough to stay up 24/7. A
free pinger avoids the cold-start:
- Sign up at https://cron-job.org (free), add a job hitting
  `https://anima-api.onrender.com/api/v1/health` every **10 minutes**.

---

## 4. Updating later
- **Backend / index change:** commit and `git push`; Render auto-redeploys.
  (Re-add data with `-f` if you regenerated it.)
- **Frontend change:** `npm run build`, re-upload `dist/` contents.
- **Changed mood prompts:** re-run
  `python -m ml.embeddings.precompute_moods --index data/processed/index_world`,
  commit the new `mood_vectors.npz`, push.

## Font licensing
Oceanic Mono is used under its personal-use license (confirmed). If Anima ever
becomes commercial, swap it for a licensed/free monospace in
`apps/web/src/styles.css`.
