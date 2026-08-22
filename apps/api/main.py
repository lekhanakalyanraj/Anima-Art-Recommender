"""FastAPI backend for the Art Therapy Recommender.

Wraps the curated retriever behind a small, versioned HTTP API so the React
gallery-walk frontend (and, later, a mobile app) can consume it. The heavy
CLIP+FAISS retriever loads once at startup; each request only embeds a short
mood prompt and searches the index.

Run:
    uvicorn apps.api.main:app --reload --port 8000
Index dir via env:
    ART_INDEX_DIR=data/processed/index_world  (default)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml.data.mood import PLUTCHIK_PRIMARIES

from .moods import list_moods

INDEX_DIR = os.environ.get("ART_INDEX_DIR", "data/processed/index_world")

# Directory of locally-saved images (Indian art) served at /media. Kept as a
# plain env/path so serving never pulls in the heavy ingestion packages
# (datasets/pandas) — the API only needs to read files, not ingest them.
MEDIA_ROOT = Path(os.environ.get("ART_MEDIA_DIR", "data/raw/images")).resolve()

# Allowed browser origins. Defaults cover local dev + the production frontend on
# the user's own domain; override/extend with ART_CORS_ORIGINS (comma-separated).
_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://lekhanakraj.com",
    "https://www.lekhanakraj.com",
    "https://anima.lekhanakraj.com",
]
_env_origins = os.environ.get("ART_CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] or _DEFAULT_ORIGINS

app = FastAPI(title="Art Therapy Recommender API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Serve locally-saved images (Indian art, WikiArt) that aren't hosted URLs.
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


# Museum image hosts we proxy (some 403 hotlinked <img> requests without a
# browser UA + Referer). Proxying also sidesteps CORS/hotlink protection.
_IMG_HOSTS = ("artic.edu", "metmuseum.org", "clevelandart.org", "nasa.gov")
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _client_image_url(image_url: str) -> str:
    """URL the browser should load: /media for local files, /api/v1/img proxy for remote."""
    if not image_url:
        return ""
    if image_url.startswith(("http://", "https://")):
        return f"/api/v1/img?u={quote(image_url, safe='')}"
    norm = image_url.replace("\\", "/")
    marker = "images/"
    idx = norm.rfind(marker)
    return f"/media/{norm[idx + len(marker):]}" if idx != -1 else image_url


@app.get("/api/v1/img")
def image_proxy(u: str = Query(..., description="museum image URL to proxy")) -> Response:
    host = urlparse(u).netloc.lower()
    if not any(host == h or host.endswith("." + h) for h in _IMG_HOSTS):
        raise HTTPException(400, "image host not allowed")
    parts = urlparse(u)
    headers = {"User-Agent": _BROWSER_UA, "Referer": f"{parts.scheme}://{parts.netloc}/"}
    try:
        r = requests.get(u, headers=headers, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        raise HTTPException(502, "image fetch failed")
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --- response models --------------------------------------------------------

class ArtworkOut(BaseModel):
    uid: str
    title: str = ""
    artist: str = ""
    date_text: str = ""
    region: str = ""
    culture_raw: str = ""
    category: str = ""
    image_url: str = ""
    source: str = ""
    source_url: str = ""
    aesthetic_score: float | None = None
    score: float | None = None


class Room(BaseModel):
    mood: str
    therapeutic: bool
    balanced: bool
    count: int
    items: list[ArtworkOut]


# --- retriever (lazy singleton) ---------------------------------------------

@lru_cache(maxsize=1)
def get_retriever():
    from ml.embeddings.retrieval import MoodArtRetriever
    return MoodArtRetriever(INDEX_DIR)


def _to_out(a: dict) -> ArtworkOut:
    return ArtworkOut(
        uid=a.get("uid", ""),
        title=a.get("title", ""),
        artist=a.get("artist", ""),
        date_text=a.get("date_text", ""),
        region=a.get("region", ""),
        culture_raw=a.get("culture_raw", ""),
        category=a.get("category", ""),
        image_url=_client_image_url(a.get("image_url", "")),
        source=a.get("source", ""),
        source_url=a.get("source_url", ""),
        aesthetic_score=a.get("aesthetic_score"),
        score=a.get("_score"),
    )


# Per-device "seen" memory so a device never gets repeat artworks. In-memory,
# keyed by a client-supplied session id (resets when the server restarts).
_SEEN: dict[str, set[str]] = {}


# --- routes -----------------------------------------------------------------

@app.get("/api/v1/health")
def health() -> dict:
    r = get_retriever()
    return {"status": "ok", "index_dir": INDEX_DIR, "artworks": len(r.meta)}


@app.get("/api/v1/moods")
def moods() -> list[dict]:
    return list_moods()


@app.get("/api/v1/room", response_model=Room)
def room(
    mood: str = Query(..., description="Plutchik primary"),
    k: int = Query(12, ge=1, le=40),
    therapeutic: bool = True,
    balanced: bool = True,
    intensity: str = Query("base", pattern="^(mild|base|intense)$"),
    region: str | None = None,
    session: str | None = Query(None, description="device id — unseen artworks per device"),
) -> Room:
    if mood not in PLUTCHIK_PRIMARIES:
        raise HTTPException(400, f"unknown mood '{mood}'. Valid: {', '.join(PLUTCHIK_PRIMARIES)}")
    seen = _SEEN.setdefault(session, set()) if session else None
    retr = get_retriever()

    def fetch(exclude: set[str] | None) -> list[dict]:
        rows = retr.by_mood(mood, k=k, therapeutic=therapeutic, balanced=balanced,
                            intensity=intensity, region=region, exclude=exclude)
        return [it for it in rows if it.get("image_url")]

    items = fetch(seen)
    # this device has walked the whole pool for this query → forget & start fresh
    if not items and seen:
        seen.clear()
        items = fetch(seen)
    if seen is not None:
        seen.update(it["uid"] for it in items)

    return Room(mood=mood, therapeutic=therapeutic, balanced=balanced,
                count=len(items), items=[_to_out(a) for a in items])


@app.get("/api/v1/reset")
def reset(session: str = Query(..., description="device id to clear seen-history for")) -> dict:
    _SEEN.pop(session, None)
    return {"status": "reset", "session": session}


@app.get("/api/v1/search", response_model=Room)
def search(
    q: str = Query(..., min_length=2),
    k: int = Query(12, ge=1, le=40),
    region: str | None = None,
) -> Room:
    items = get_retriever().by_text(q, k=k, region=region)
    items = [it for it in items if it.get("image_url")]
    return Room(mood=q, therapeutic=False, balanced=False,
                count=len(items), items=[_to_out(a) for a in items])
