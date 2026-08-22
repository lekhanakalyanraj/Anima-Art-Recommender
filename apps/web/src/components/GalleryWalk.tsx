import { useCallback, useEffect, useRef, useState } from "react";
import type { Artwork } from "../types";
import { regionLabel } from "../types";

interface Props {
  moodLabel: string;
  moodColor: string;
  items: Artwork[];
  liked: Artwork[];
  onToggleLike: (a: Artwork) => void;
  onExit: () => void;
}

export default function GalleryWalk({
  moodLabel,
  moodColor,
  items,
  liked,
  onToggleLike,
  onExit,
}: Props) {
  const [i, setI] = useState(0);
  const atEnd = i >= items.length;
  const art = items[i];

  const next = useCallback(() => setI((n) => Math.min(n + 1, items.length)), [items.length]);
  const prev = useCallback(() => setI((n) => Math.max(n - 1, 0)), []);

  // swipe (tablet / phone): left → next, right → previous
  const touchX = useRef<number | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    touchX.current = e.changedTouches[0].clientX;
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (touchX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    touchX.current = null;
    if (Math.abs(dx) > 45) (dx < 0 ? next : prev)();
  };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Escape") onExit();
      else if ((e.key === "h" || e.key === "H") && art) onToggleLike(art);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, onExit, onToggleLike, art]);

  if (atEnd) {
    return (
      <div className="screen center" style={{ background: wash(moodColor) }}>
        <div className="end">
          <h2>You’ve walked the {moodLabel.toLowerCase()} gallery.</h2>
          <p className="dim">
            {liked.length > 0
              ? `${liked.length} piece${liked.length > 1 ? "s" : ""} stayed with you.`
              : "Take what you felt with you."}
          </p>
          <div className="end-actions">
            <button className="ghost" onClick={() => setI(0)}>Walk it again</button>
            <button className="primary" onClick={onExit}>Choose another feeling</button>
          </div>
        </div>
      </div>
    );
  }

  const isLiked = !!liked.find((x) => x.uid === art.uid);
  const credit = SOURCE_CREDIT[art.source] ?? art.source;
  // NASA's culture string duplicates the credit; prefer the region label there.
  const origin = art.source === "nasa" ? regionLabel(art.region) : art.culture_raw || regionLabel(art.region);
  const meta = [art.date_text, origin].filter(Boolean).join("  ·  ");

  return (
    <div
      className="screen walk"
      style={{ background: wash(moodColor) }}
      role="region"
      aria-roledescription="artwork gallery"
      aria-label={`${moodLabel} gallery, artwork ${i + 1} of ${items.length}`}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <p className="sr-only" aria-live="polite" role="status">
        {`Artwork ${i + 1} of ${items.length}: ${art.title || "Untitled"}${
          art.artist ? ", " + art.artist : ""
        }`}
      </p>

      <div className="walk-top">
        <button className="round exit" onClick={onExit} aria-label="Back to feelings" title="Back to feelings">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
               strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <span className="walk-mood" style={{ color: moodColor }}>{moodLabel}</span>
        <span className="walk-count" aria-hidden="true">{i + 1} / {items.length}</span>
      </div>

      <div className="stage">
        <img
          key={art.uid}
          className="artwork"
          src={art.image_url}
          alt={`${art.title || "Untitled"}${art.artist ? " — " + art.artist : ""}`}
          onClick={next}
          draggable={false}
        />
      </div>

      <figcaption className="label">
        <h2 className="title">{art.title || "Untitled"}</h2>
        {art.artist && <p className="artist">{art.artist}</p>}
        {meta && <p className="meta">{meta}</p>}
        <p className="credit">
          Courtesy of{" "}
          {art.source_url ? (
            <a href={art.source_url} target="_blank" rel="noreferrer">{credit}</a>
          ) : (
            credit
          )}
        </p>
      </figcaption>

      <div className="controls">
        <button className="round" onClick={prev} disabled={i === 0} aria-label="Previous">‹</button>
        <button
          className={`round heart ${isLiked ? "on" : ""}`}
          onClick={() => onToggleLike(art)}
          aria-label={isLiked ? "Unsave" : "Save"}
        >
          {isLiked ? "♥" : "♡"}
        </button>
        <button className="round" onClick={next} aria-label="Next">›</button>
      </div>

      <div className="progress" aria-hidden="true">
        {items.map((_, idx) => (
          <span key={idx} className={`tick ${idx === i ? "on" : ""}`} />
        ))}
      </div>

      {i === 0 && <p className="walk-hint" aria-hidden="true">tap or swipe to move</p>}
    </div>
  );
}

// Attribution shown as the credit line, keyed by source.
const SOURCE_CREDIT: Record<string, string> = {
  nasa: "NASA",
  met: "The Metropolitan Museum of Art",
  cleveland: "The Cleveland Museum of Art",
  aic: "Art Institute of Chicago",
  indian_art: "Indian art traditions",
  wikiart: "WikiArt",
};

// A faint wash of the mood's color, fading to transparent so the drifting
// particles behind show through in the margins.
function wash(hex: string): string {
  return `radial-gradient(1400px 900px at 50% 28%, ${hex}14, transparent 60%)`;
}
