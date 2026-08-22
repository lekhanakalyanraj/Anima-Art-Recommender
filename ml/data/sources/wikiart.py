"""WikiArt (huggan/wikiart) — the Western-canon base layer.

81,444 works with artist / genre / style class labels. No per-work culture field,
so region is inferred from the style name (e.g. Ukiyo-e -> east_asian) and
otherwise left 'unknown' rather than falsely stamped 'european'. This is the
layer ArtEmis emotion labels attach to.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..normalize import normalize_region
from ..schema import Artwork
from .base import BaseIngestor
from .hf_common import save_image

_REPO = "huggan/wikiart"


class WikiArtIngestor(BaseIngestor):
    source = "wikiart"

    def __init__(self, save_images: bool = True):
        self.save_images = save_images

    def iter_artworks(self, limit: int | None = None) -> Iterator[Artwork]:
        from datasets import load_dataset  # lazy import; heavy dependency

        ds = load_dataset(_REPO, split="train", streaming=True)
        feats = ds.features
        artist_names = feats["artist"].names if "artist" in feats else None
        genre_names = feats["genre"].names if "genre" in feats else None
        style_names = feats["style"].names if "style" in feats else None

        count = 0
        for idx, row in enumerate(ds):
            if limit is not None and count >= limit:
                return
            style = style_names[row["style"]] if style_names and "style" in row else ""
            genre = genre_names[row["genre"]] if genre_names and "genre" in row else ""
            artist = artist_names[row["artist"]] if artist_names and "artist" in row else ""
            style = style.replace("_", " ")

            image_url = ""
            if self.save_images:
                saved = save_image(row.get("image"), self.source, str(idx))
                if not saved:
                    continue
                image_url = saved

            # Region: only trust a signal we can defend (e.g. Ukiyo-e); else unknown.
            region = normalize_region(style)

            art = Artwork(
                uid=self.make_uid(idx),
                source=self.source,
                source_id=str(idx),
                title=genre.replace("_", " ").title() if genre else "Untitled",
                artist=artist.replace("_", " ").title(),
                category="painting",
                style=style,
                region=region,
                culture_raw=style,
                image_url=image_url,
                license="see WikiArt terms",
            )
            count += 1
            yield art
