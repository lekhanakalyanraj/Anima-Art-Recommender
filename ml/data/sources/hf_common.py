"""Helpers shared by HuggingFace-dataset ingestors (WikiArt, Indian art styles).

Unlike the museum APIs, these datasets embed image *bytes* rather than URLs, so we
persist each image to a local media directory and point ``image_url`` at that
path. Downstream (CLIP embedding, the API) treats a local path and an http(s)
URL the same way. Streaming avoids downloading the whole (tens-of-GB) dataset.
"""

from __future__ import annotations

from pathlib import Path

# Media root for locally-persisted images from embedded-image datasets.
MEDIA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "images"


# Project root, so saved image paths can be stored relative (portable across
# machines) rather than as an absolute path baked into the corpus.
_PROJECT_ROOT = MEDIA_ROOT.parents[2]


def save_image(image, source: str, source_id: str) -> str | None:
    """Persist a PIL image under MEDIA_ROOT/<source>/<source_id>.jpg.

    Returns a project-relative path (e.g. 'data/raw/images/<source>/<id>.jpg'),
    or None if the image could not be saved. Relative so the corpus is portable.
    """
    if image is None:
        return None
    out_dir = MEDIA_ROOT / source
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{source_id}.jpg"
    try:
        rgb = image.convert("RGB") if image.mode != "RGB" else image
        rgb.save(out_path, format="JPEG", quality=90)
    except Exception:
        return None
    return str(out_path.relative_to(_PROJECT_ROOT)).replace("\\", "/")
