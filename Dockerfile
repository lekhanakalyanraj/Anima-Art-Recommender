# Anima API — lightweight serve image (FastAPI + FAISS + NumPy, no torch/CLIP).
# The mood-query vectors are precomputed (mood_vectors.npz), so this stays small
# enough for a free 512MB host and cold-starts in seconds.
# Works on Render / Koyeb / Cloud Run (they inject $PORT).
FROM python:3.11-slim

# FAISS needs the OpenMP runtime at import time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ART_INDEX_DIR=data/processed/index_world \
    ART_MEDIA_DIR=data/raw/images

COPY requirements-serve.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-serve.txt

# App code + the built index (FAISS + meta + embeddings + mood vectors) + images
COPY ml ./ml
COPY apps ./apps
COPY data/processed/index_world ./data/processed/index_world
COPY data/raw/images ./data/raw/images

EXPOSE 8000
# Shell form so ${PORT} (set by the host) is expanded; falls back to 8000 locally.
CMD uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
