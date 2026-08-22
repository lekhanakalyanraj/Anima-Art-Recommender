"""Aesthetic quality scoring — the LAION improved-aesthetic predictor.

A museum curates; it doesn't show every object. This scores each artwork 0–10 on
visual appeal (the model behind LAION-Aesthetics), so we can gate out study
fragments / coins / damaged pieces and make beauty a first-class ranking term.

Model: `shunk031/aesthetics-predictor-v2-sac-logos-ava1-l14-linearMSE` — the
canonical predictor as a maintained `transformers` model, built on CLIP ViT-L/14
(the same backbone family as our L/14 retrieval embeddings).
"""

from __future__ import annotations

import numpy as np

_MODEL_ID = "shunk031/aesthetics-predictor-v2-sac-logos-ava1-l14-linearMSE"


def _pick_device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class AestheticScorer:
    """Scores PIL images for aesthetic quality on the LAION 0–10 scale."""

    def __init__(self, device: str | None = None):
        import torch
        from aesthetics_predictor import AestheticsPredictorV2Linear
        from transformers import CLIPProcessor

        self.torch = torch
        self.device = device or _pick_device()
        self.model = AestheticsPredictorV2Linear.from_pretrained(_MODEL_ID).to(self.device).eval()
        self.processor = CLIPProcessor.from_pretrained(_MODEL_ID)

    def score_pil_batch(self, pil_images: list) -> list[float]:
        """Return an aesthetic score per PIL image (empty -> [])."""
        if not pil_images:
            return []
        inputs = self.processor(images=pil_images, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            logits = self.model(**inputs).logits.squeeze(-1)
        return [float(x) for x in logits.cpu().numpy().reshape(-1)]


def normalize_aesthetic(score: float, lo: float = 4.0, hi: float = 9.0) -> float:
    """Map a raw 0–10 aesthetic score to ~[0,1] over the useful band (4–9)."""
    return float(np.clip((score - lo) / (hi - lo), 0.0, 1.0))
