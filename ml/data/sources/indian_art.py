"""Indian art styles (Divya0001/indian-art-styles) — 34 traditional styles.

Covers exactly what WikiArt lacks: madhubani, warli, gond, pattachitra, tanjore,
mughal miniature, pahari, kangra, kalamkari, thangka, pichwai and more. Every
work is South Asian; we additionally carry the originating Indian state and
distinguish folk traditions from court/miniature painting.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..schema import Artwork
from .base import BaseIngestor
from .hf_common import save_image

_REPO = "Divya0001/indian-art-styles"

# style -> (originating state/region within India, category)
_STYLE_META: dict[str, tuple[str, str]] = {
    "aipan": ("Uttarakhand", "folk_art"),
    "bengal_school": ("West Bengal", "painting"),
    "bhil": ("Madhya Pradesh", "folk_art"),
    "bikaner": ("Rajasthan", "painting"),
    "bundi": ("Rajasthan", "painting"),
    "cheriyal": ("Telangana", "folk_art"),
    "gond": ("Madhya Pradesh", "folk_art"),
    "jaipur": ("Rajasthan", "painting"),
    "kalamkari": ("Andhra Pradesh", "textile"),
    "kalighat": ("West Bengal", "folk_art"),
    "kangra": ("Himachal Pradesh", "painting"),
    "kerala_mural": ("Kerala", "painting"),
    "kishangarh": ("Rajasthan", "painting"),
    "kota": ("Rajasthan", "painting"),
    "madhubani": ("Bihar", "folk_art"),
    "mandana": ("Rajasthan", "folk_art"),
    "manjusha": ("Bihar", "folk_art"),
    "mewar": ("Rajasthan", "painting"),
    "mughal_miniature": ("Mughal India", "painting"),
    "mysore": ("Karnataka", "painting"),
    "nirmal": ("Telangana", "painting"),
    "pahari": ("Himalayan foothills", "painting"),
    "patna_kalam": ("Bihar", "painting"),
    "pattachitra": ("Odisha", "folk_art"),
    "phad": ("Rajasthan", "folk_art"),
    "pichwai": ("Rajasthan", "painting"),
    "pithora": ("Gujarat", "folk_art"),
    "rajput": ("Rajasthan", "painting"),
    "rogan": ("Gujarat", "folk_art"),
    "saura": ("Odisha", "folk_art"),
    "sohrai": ("Jharkhand", "folk_art"),
    "tanjore": ("Tamil Nadu", "painting"),
    "thangka": ("Himalayan / Tibetan", "painting"),
    "warli": ("Maharashtra", "folk_art"),
}


class IndianArtIngestor(BaseIngestor):
    source = "indian_art"

    def __init__(self, save_images: bool = True):
        self.save_images = save_images

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        from datasets import load_dataset  # lazy import; heavy dependency

        ds = load_dataset(_REPO, split="train", streaming=True)
        label_names = ds.features["label"].names

        count = 0
        for idx, row in enumerate(ds):
            if limit is not None and count >= limit:
                return
            style = label_names[row["label"]]
            state, category = _STYLE_META.get(style, ("India", "folk_art"))

            image_url = ""
            if self.save_images:
                saved = save_image(row.get("image"), self.source, str(idx))
                if not saved:
                    continue
                image_url = saved

            pretty_style = style.replace("_", " ").title()
            art = Artwork(
                uid=self.make_uid(idx),
                source=self.source,
                source_id=str(idx),
                title=f"{pretty_style} painting",
                style=pretty_style,
                category=category,
                region="south_asian",
                culture_raw=f"Indian — {pretty_style} ({state})",
                image_url=image_url,
                license="CC-BY-4.0",
            )
            count += 1
            yield art
