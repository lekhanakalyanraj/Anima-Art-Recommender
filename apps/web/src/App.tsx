import { useEffect, useState, type ReactNode } from "react";
import { fetchMoods, fetchRoom } from "./api";
import type { Artwork, MoodSelection } from "./types";
import MoodSelect from "./components/MoodSelect";
import GalleryWalk from "./components/GalleryWalk";
import Ambient from "./components/Ambient";

type View =
  | { name: "select" }
  | { name: "loading"; sel: MoodSelection }
  | { name: "walk"; sel: MoodSelection; items: Artwork[] }
  | { name: "error"; message: string };

export default function App() {
  const [view, setView] = useState<View>({ name: "select" });
  const [liked, setLiked] = useState<Artwork[]>([]);

  // Connectivity probe so a down backend shows a clear message early.
  useEffect(() => {
    fetchMoods().catch((e) => setView({ name: "error", message: String(e) }));
  }, []);

  async function enterMood(sel: MoodSelection) {
    setView({ name: "loading", sel });
    try {
      const room = await fetchRoom(sel.primary, 14, sel.intensity);
      if (!room.items.length) throw new Error("No artworks came back for this mood.");
      setView({ name: "walk", sel, items: room.items });
    } catch (e) {
      setView({ name: "error", message: String(e) });
    }
  }

  function toggleLike(a: Artwork) {
    setLiked((cur) =>
      cur.find((x) => x.uid === a.uid) ? cur.filter((x) => x.uid !== a.uid) : [...cur, a]
    );
  }

  let content: ReactNode;
  if (view.name === "error") {
    content = (
      <div className="screen center">
        <div className="notice">
          <p>Couldn’t reach the gallery.</p>
          <p className="dim small">{view.message}</p>
          <p className="dim small">Is the API running on port 8000?</p>
          <button className="ghost" onClick={() => setView({ name: "select" })}>Back</button>
        </div>
      </div>
    );
  } else if (view.name === "loading") {
    content = (
      <div className="screen center" style={{ background: tint(view.sel.color) }}>
        <div className="loading">
          <span className="dot" style={{ background: view.sel.color }} />
          <p className="dim">Gathering a room for {view.sel.label}…</p>
        </div>
      </div>
    );
  } else if (view.name === "walk") {
    content = (
      <GalleryWalk
        moodLabel={view.sel.label}
        moodColor={view.sel.color}
        items={view.items}
        liked={liked}
        onToggleLike={toggleLike}
        onExit={() => setView({ name: "select" })}
      />
    );
  } else {
    content = <MoodSelect onPick={enterMood} />;
  }

  const ambientColor =
    view.name === "walk" || view.name === "loading" ? view.sel.color : undefined;

  return (
    <>
      <Ambient color={ambientColor} />
      {content}
    </>
  );
}

function tint(hex: string): string {
  return `radial-gradient(1200px 800px at 50% 40%, ${hex}20, transparent 65%)`;
}
