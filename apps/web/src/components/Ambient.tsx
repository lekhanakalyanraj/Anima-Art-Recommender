import { useEffect, useRef } from "react";

const CREAM: [number, number, number] = [239, 233, 224];

// Parse "#rrggbb" → [r,g,b], lightened toward white so darker moods stay visible.
function moodRgb(hex?: string): [number, number, number] {
  if (!hex) return CREAM;
  const n = parseInt(hex.slice(1), 16);
  if (Number.isNaN(n)) return CREAM;
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  const lift = (c: number) => Math.round(c + (255 - c) * 0.32);
  return [lift(r), lift(g), lift(b)];
}

/**
 * A faint field of slowly drifting particles behind everything — tinted with the
 * current mood's colour (cream on the wheel screen), easing between colours when
 * the mood changes. Fixed, non-interactive, and subtle so it never competes.
 */
export default function Ambient({ color }: { color?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const target = useRef<[number, number, number]>(moodRgb(color));

  useEffect(() => {
    target.current = moodRgb(color);
  }, [color]);

  useEffect(() => {
    const canvasEl = ref.current;
    if (!canvasEl) return;
    const context = canvasEl.getContext("2d");
    if (!context) return;
    // Fresh non-null bindings: the animation closures below capture these, and
    // TS won't carry the null-guard narrowing into a nested function otherwise.
    const canvas = canvasEl;
    const ctx = context;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0;
    let H = 0;
    let raf = 0;
    type P = { x: number; y: number; vx: number; vy: number; r: number; a: number; tw: number };
    let particles: P[] = [];
    const cur: [number, number, number] = [...target.current];

    function resize() {
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(160, Math.max(45, Math.round((W * H) / 15000)));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12 - 0.035, // gentle upward drift
        r: Math.random() * 1.7 + 0.5,
        a: Math.random() * 0.45 + 0.16,
        tw: Math.random() * Math.PI * 2,
      }));
    }

    function frame() {
      // ease the drawing colour toward the current mood
      const t = target.current;
      cur[0] += (t[0] - cur[0]) * 0.04;
      cur[1] += (t[1] - cur[1]) * 0.04;
      cur[2] += (t[2] - cur[2]) * 0.04;
      const rgb = `${Math.round(cur[0])}, ${Math.round(cur[1])}, ${Math.round(cur[2])}`;

      ctx.clearRect(0, 0, W, H);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        p.tw += 0.008;
        if (p.x < -6) p.x = W + 6;
        else if (p.x > W + 6) p.x = -6;
        if (p.y < -6) p.y = H + 6;
        else if (p.y > H + 6) p.y = -6;
        const alpha = p.a * (0.55 + 0.45 * Math.sin(p.tw));
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb}, ${alpha})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="ambient" aria-hidden="true" />;
}
