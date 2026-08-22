export interface Mood {
  key: string;
  label: string;
  color: string;
  blurb: string;
}

export type Intensity = "mild" | "base" | "intense";

// A specific pick from the Plutchik wheel: a primary emotion at one intensity.
export interface MoodSelection {
  primary: string; // Plutchik primary the backend expects
  intensity: Intensity;
  label: string; // the specific emotion, e.g. "serenity"
  color: string; // the primary's color
}

export interface Artwork {
  uid: string;
  title: string;
  artist: string;
  date_text: string;
  region: string;
  culture_raw: string;
  category: string;
  image_url: string;
  source: string;
  source_url: string;
  aesthetic_score: number | null;
  score: number | null;
}

export interface Room {
  mood: string;
  therapeutic: boolean;
  balanced: boolean;
  count: number;
  items: Artwork[];
}

const REGION_LABELS: Record<string, string> = {
  african: "African",
  east_asian: "East Asian",
  south_asian: "South Asian",
  southeast_asian: "Southeast Asian",
  central_asian: "Central Asian",
  west_asian: "West Asian",
  european: "European",
  north_american: "North American",
  latin_american: "Latin American",
  oceanian: "Oceanian",
  ancient_mediterranean: "Ancient Mediterranean",
  space: "Cosmos",
  unknown: "",
};

export function regionLabel(region: string): string {
  return REGION_LABELS[region] ?? region;
}
