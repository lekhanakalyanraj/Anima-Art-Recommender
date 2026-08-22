import type { Mood, Room } from "./types";

// Same-origin in dev via Vite proxy; override with VITE_API_BASE for a hosted API.
// Trailing slash trimmed so `${BASE}${path}` never doubles up.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

// The API returns image paths relative to itself (`/api/v1/img...`, `/media/...`).
// When the frontend is served from a different origin (prod), prefix them with
// the API base so the browser fetches images from the API, not the static host.
function withBase(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path)) return path;
  return path.startsWith("/") ? `${BASE}${path}` : path;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function fetchMoods(): Promise<Mood[]> {
  return getJSON<Mood[]>("/api/v1/moods");
}

export interface Health {
  status: string;
  index_dir: string;
  artworks: number;
}

export function fetchHealth(): Promise<Health> {
  return getJSON<Health>("/api/v1/health");
}

// A stable per-device id so the backend can avoid repeating artworks this
// device has already seen (persists across visits via localStorage).
function sessionId(): string {
  const KEY = "anima_session";
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = (crypto.randomUUID?.() ?? String(Math.random()).slice(2)) as string;
    localStorage.setItem(KEY, id);
  }
  return id;
}

export async function fetchRoom(mood: string, k = 12, intensity = "base"): Promise<Room> {
  const s = encodeURIComponent(sessionId());
  const room = await getJSON<Room>(
    `/api/v1/room?mood=${encodeURIComponent(mood)}&k=${k}&intensity=${intensity}&session=${s}`
  );
  return { ...room, items: room.items.map((it) => ({ ...it, image_url: withBase(it.image_url) })) };
}
