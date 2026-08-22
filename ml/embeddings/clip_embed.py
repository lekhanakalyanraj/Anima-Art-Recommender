"""CLIP encoder — one shared image/text embedding space (open_clip).

The recommender needs images and text in the *same* space so a mood/style query
(text) can rank artworks (images), matching the spec's CLIP-based approach. Also
lets a Pinterest board (images) later query the corpus directly.

Model: ViT-B-32 / laion2b — small enough for CPU or Apple MPS, 512-d vectors.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np

# ViT-L/14 by default (768-d) for higher-fidelity retrieval and to match the
# aesthetic predictor's CLIP backbone. Override via env for a faster B/32 run.
_MODEL_NAME = os.environ.get("ART_CLIP_MODEL", "ViT-L-14")
_PRETRAINED = os.environ.get("ART_CLIP_PRETRAINED", "laion2b_s32b_b82k")


def _pick_device():
    """Pick a compute device.

    CUDA when present, else CPU. Apple MPS is *not* auto-selected: this torch
    build segfaults on MPS during batched CLIP image inference. Opt in with
    ART_USE_MPS=1 if a future torch fixes it.
    """
    import os

    import torch
    if torch.cuda.is_available():
        return "cuda"
    if os.environ.get("ART_USE_MPS") == "1" and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class ClipEncoder:
    """Lazily-loaded CLIP encoder producing L2-normalized float32 vectors."""

    def __init__(self, device: str | None = None):
        import open_clip
        import torch

        self.torch = torch
        self.device = device or _pick_device()
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            _MODEL_NAME, pretrained=_PRETRAINED
        )
        self.model = self.model.to(self.device).eval()
        self.tokenizer = open_clip.get_tokenizer(_MODEL_NAME)
        self.dim = self.model.visual.output_dim

    # --- loading -----------------------------------------------------------

    # A browser-like UA plus an origin Referer clears WAFs on some museum image
    # hosts (e.g. AIC's IIIF server 403s otherwise).
    _BROWSER_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    @classmethod
    def _load_image(cls, path_or_url: str):
        from urllib.parse import urlparse

        from PIL import Image

        from ..data.sources.base import _SESSION

        if path_or_url.startswith(("http://", "https://")):
            parts = urlparse(path_or_url)
            headers = {
                "User-Agent": cls._BROWSER_UA,
                "Referer": f"{parts.scheme}://{parts.netloc}/",
            }
            resp = _SESSION.get(path_or_url, timeout=15, headers=headers)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
        else:
            img = Image.open(Path(path_or_url))
        return img.convert("RGB")

    # --- embedding ---------------------------------------------------------

    def embed_pil_batch(self, pil_images: list) -> np.ndarray:
        """Embed already-loaded PIL images → (n, dim) L2-normalized array."""
        if not pil_images:
            return np.zeros((0, self.dim), dtype="float32")
        tensor = self.torch.stack([self.preprocess(im) for im in pil_images]).to(self.device)
        with self.torch.no_grad():
            feats = self.model.encode_image(tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().astype("float32")

    def embed_images(self, sources: list[str], batch_size: int = 32,
                     verbose: bool = False) -> np.ndarray:
        """Embed a list of image paths/URLs. Failed loads become zero vectors."""
        vecs = np.zeros((len(sources), self.dim), dtype="float32")
        batch_imgs, batch_idx = [], []

        def flush():
            if not batch_imgs:
                return
            rows = self.embed_pil_batch(batch_imgs)
            for j, row in zip(batch_idx, rows):
                vecs[j] = row
            batch_imgs.clear()
            batch_idx.clear()

        for i, src in enumerate(sources):
            try:
                batch_imgs.append(self._load_image(src))
                batch_idx.append(i)
            except Exception:
                continue  # leave zero vector; caller can filter
            if len(batch_imgs) >= batch_size:
                flush()
                if verbose:
                    print(f"  embedded {i + 1}/{len(sources)} …", flush=True)
        flush()
        if verbose:
            print(f"  embedded {len(sources)}/{len(sources)} (done)", flush=True)
        return vecs

    def embed_text(self, texts: list[str]) -> np.ndarray:
        tokens = self.tokenizer(texts).to(self.device)
        with self.torch.no_grad():
            feats = self.model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().astype("float32")
