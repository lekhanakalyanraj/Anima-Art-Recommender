import { useState } from "react";
import type { Intensity, MoodSelection } from "../types";

interface Props {
  onSelect: (sel: MoodSelection) => void;
}

// Eight primaries, clockwise from top, with opposites across the wheel.
// labels: [intense (inner), base (middle), mild (outer)].
interface Wedge {
  primary: string;
  color: string;
  labels: [string, string, string];
}

const WEDGES: Wedge[] = [
  { primary: "joy", color: "#F4D03F", labels: ["ecstasy", "joy", "serenity"] },
  { primary: "trust", color: "#82C46C", labels: ["admiration", "trust", "acceptance"] },
  { primary: "fear", color: "#1E8449", labels: ["terror", "fear", "apprehension"] },
  { primary: "surprise", color: "#5DADE2", labels: ["amazement", "surprise", "distraction"] },
  { primary: "sadness", color: "#2E86C1", labels: ["grief", "sadness", "pensiveness"] },
  { primary: "disgust", color: "#8E44AD", labels: ["loathing", "disgust", "boredom"] },
  { primary: "anger", color: "#E74C3C", labels: ["rage", "anger", "annoyance"] },
  { primary: "anticipation", color: "#E67E22", labels: ["vigilance", "anticipation", "interest"] },
];

const INTENSITIES: Intensity[] = ["intense", "base", "mild"];
// Ring radii [inner, outer]. Rings get WIDER outward: inner narrow, outer widest.
// index 0 = intense (inner), 2 = mild (outer).
const RINGS = [
  [58, 114],
  [114, 176],
  [176, 248],
];
const HUB = 58;
const RIM = 274; // radius of the primary labels
const VIEWBOX = "-322 -322 644 644";

function pt(r: number, deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [r * Math.sin(a), -r * Math.cos(a)]; // 0° = top, clockwise
}

// Rounded annular-sector path for angles [a0,a1] (deg from top, cw) and radii
// [ri,ro]. A small gap + rounded corners make each petal read as a soft tile.
function sector(a0: number, a1: number, ri: number, ro: number): string {
  const gapDeg = 0.7; // angular gap between neighbouring petals
  const gapR = 1.2; // radial gap between rings
  const cr = 9; // corner radius (world units)

  const A0 = a0 + gapDeg;
  const A1 = a1 - gapDeg;
  const RI = ri + gapR;
  const RO = ro - gapR;

  const dr = Math.min(cr, (RO - RI) / 2 - 1); // radial inset for corner
  const half = (A1 - A0) / 2 - 0.5;
  const dIn = Math.min((cr / RI) * (180 / Math.PI), half); // arc inset (inner)
  const dOut = Math.min((cr / RO) * (180 / Math.PI), half); // arc inset (outer)

  const f = (r: number, a: number) => {
    const [x, y] = pt(r, a);
    return `${x.toFixed(2)} ${y.toFixed(2)}`;
  };

  return [
    `M ${f(RI, A0 + dIn)}`,
    `A ${RI} ${RI} 0 0 1 ${f(RI, A1 - dIn)}`, // inner arc
    `Q ${f(RI, A1)} ${f(RI + dr, A1)}`, // inner-A1 corner
    `L ${f(RO - dr, A1)}`, // radial edge at A1
    `Q ${f(RO, A1)} ${f(RO, A1 - dOut)}`, // outer-A1 corner
    `A ${RO} ${RO} 0 0 0 ${f(RO, A0 + dOut)}`, // outer arc
    `Q ${f(RO, A0)} ${f(RO - dr, A0)}`, // outer-A0 corner
    `L ${f(RI + dr, A0)}`, // radial edge at A0
    `Q ${f(RI, A0)} ${f(RI, A0 + dIn)}`, // inner-A0 corner
    "Z",
  ].join(" ");
}

function hexToHsl(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  const r = ((n >> 16) & 255) / 255;
  const g = ((n >> 8) & 255) / 255;
  const b = (n & 255) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  let s = 0;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, l];
}

function hslToRgb(h: number, s: number, l: number): string {
  s = Math.min(1, Math.max(0, s));
  l = Math.min(1, Math.max(0, l));
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const hh = ((h % 360) + 360) % 360;
  let r = 0;
  let g = 0;
  let b = 0;
  if (hh < 60) [r, g, b] = [c, x, 0];
  else if (hh < 120) [r, g, b] = [x, c, 0];
  else if (hh < 180) [r, g, b] = [0, c, x];
  else if (hh < 240) [r, g, b] = [0, x, c];
  else if (hh < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const to = (v: number) => Math.round((v + m) * 255);
  return `rgb(${to(r)}, ${to(g)}, ${to(b)})`;
}

// Intensity rings from one hue. Darkening happens in HSL (lightness down, keep
// saturation) so the inner ring is a rich, vivid deep color — not a muddy black tint.
function ringColor(hex: string, ring: number): string {
  const [h, s, l] = hexToHsl(hex);
  if (ring === 0) return hslToRgb(h, Math.min(1, s * 1.2), l * 0.78);
  if (ring === 1) return hslToRgb(h, s, l);
  return hslToRgb(h, s * 0.72, l + (1 - l) * 0.55);
}

const SWEEP = 45; // degrees per wedge

export function randomMood(): MoodSelection {
  const w = WEDGES[Math.floor(Math.random() * WEDGES.length)];
  const ring = Math.floor(Math.random() * 3);
  return { primary: w.primary, intensity: INTENSITIES[ring], label: w.labels[ring], color: w.color };
}

export default function PlutchikWheel({ onSelect }: Props) {
  const [hover, setHover] = useState<MoodSelection | null>(null);

  return (
    <div className="plutchik">
      <div className="wheel3d" role="group" aria-label="Plutchik emotion wheel">
        {/* One SVG layer per ring, each pushed to a different depth (Z). */}
        {RINGS.map(([ri, ro], ring) => (
          <svg key={ring} className={`ring-layer ring-z-${ring}`} viewBox={VIEWBOX} aria-hidden={ring !== 1}>
            {ring === 0 && (
              <defs>
                {/* Metallic bevel: soft specular highlight so each petal reads as a raised button. */}
                <filter id="anima-bevel" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur in="SourceAlpha" stdDeviation="7" result="blur" />
                  <feSpecularLighting
                    in="blur"
                    surfaceScale="6"
                    specularConstant="0.7"
                    specularExponent="16"
                    lightingColor="#ffffff"
                    result="spec"
                  >
                    <feDistantLight azimuth="235" elevation="52" />
                  </feSpecularLighting>
                  <feComposite in="spec" in2="SourceAlpha" operator="in" result="specClip" />
                  <feBlend in="SourceGraphic" in2="specClip" mode="screen" />
                </filter>
              </defs>
            )}
            {WEDGES.map((w, wi) => {
              const center = wi * SWEEP;
              const a0 = center - SWEEP / 2;
              const a1 = center + SWEEP / 2;
              const intensity = INTENSITIES[ring];
              const label = w.labels[ring];
              const fill = ringColor(w.color, ring);
              const active = hover?.label === label;
              return (
                <path
                  key={label}
                  d={sector(a0, a1, ri, ro)}
                  fill={fill}
                  className={`wedge ${active ? "active" : ""} ${hover && !active ? "muted" : ""}`}
                  onMouseEnter={() => setHover({ primary: w.primary, intensity, label, color: w.color })}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => onSelect({ primary: w.primary, intensity, label, color: w.color })}
                  role="button"
                  aria-label={`${label}${intensity !== "base" ? ` — ${intensity} ${w.primary}` : ""}`}
                />
              );
            })}
          </svg>
        ))}

        {/* Front overlay: primary labels + the center hub readout. */}
        <svg className="wheel-overlay" viewBox={VIEWBOX} aria-hidden="true">
          {WEDGES.map((w, wi) => {
            const center = wi * SWEEP;
            const [lx, ly] = pt(RIM, center);
            const mod = ((center % 360) + 360) % 360;
            return (
              <text
                key={w.primary}
                x={lx}
                y={ly}
                className="rim-label"
                textAnchor={mod < 1 || Math.abs(mod - 180) < 1 ? "middle" : mod < 180 ? "start" : "end"}
                dominantBaseline="middle"
              >
                {w.primary}
              </text>
            );
          })}
          <circle r={HUB} className="hub" />
          {hover ? (
            <>
              <text className="hub-label" y={-4}>{hover.label}</text>
              <text className="hub-sub" y={14}>
                {hover.intensity === "base" ? hover.primary : `${hover.intensity} · ${hover.primary}`}
              </text>
            </>
          ) : (
            <text className="hub-idle" y={4}>anima</text>
          )}
        </svg>
      </div>
    </div>
  );
}
