// Derives corner positions and DRS-zone extents directly from a real circuit
// SVG path's geometry (curvature peaks + longest straight gaps), instead of
// hand-picking coordinates. Ported from the original vanilla-JS prototype
// (track-analysis.js) built for the Claude Design mockups.

export interface TrackPoint {
  l: number;
  x: number;
  y: number;
}

export interface TrackAnalysis {
  total: number;
  corners: TrackPoint[];
  drs1: { fromL: number; len: number };
  drs2: { fromL: number; len: number };
}

export function analyzeTrack(
  pathEl: SVGPathElement,
  { numCorners = 19, sampleCount = 720, window = 7 }: { numCorners?: number; sampleCount?: number; window?: number } = {}
): TrackAnalysis {
  const total = pathEl.getTotalLength();
  const pts: TrackPoint[] = [];
  for (let i = 0; i < sampleCount; i++) {
    const l = (i / sampleCount) * total;
    const p = pathEl.getPointAtLength(l);
    pts.push({ l, x: p.x, y: p.y });
  }

  function turnAngle(i: number) {
    const a = pts[(i - window + sampleCount) % sampleCount];
    const b = pts[i];
    const c = pts[(i + window) % sampleCount];
    const v1x = b.x - a.x, v1y = b.y - a.y;
    const v2x = c.x - b.x, v2y = c.y - b.y;
    let d = Math.atan2(v2y, v2x) - Math.atan2(v1y, v1x);
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    return Math.abs(d);
  }

  const curvature = pts.map((_, i) => turnAngle(i));
  const ranked = curvature.map((v, i) => [v, i] as const).sort((a, b) => b[0] - a[0]);
  const minSep = Math.floor(sampleCount / (numCorners * 1.5));
  const chosen: number[] = [];
  for (const [, i] of ranked) {
    if (chosen.length >= numCorners) break;
    if (chosen.every((j) => Math.min(Math.abs(j - i), sampleCount - Math.abs(j - i)) > minSep)) {
      chosen.push(i);
    }
  }
  chosen.sort((a, b) => a - b);
  const corners = chosen.map((i) => pts[i]);

  const gaps = corners.map((c, k) => {
    const next = corners[(k + 1) % corners.length];
    let len = next.l - c.l;
    if (len <= 0) len += total;
    return { fromL: c.l, len, wraps: k === corners.length - 1 };
  });
  const drs2 = gaps[gaps.length - 1]; // wraparound: last corner -> start/finish -> first corner = pit straight
  const drs1 = gaps.slice(0, -1).reduce((a, b) => (b.len > a.len ? b : a)); // longest interior straight

  return { total, corners, drs1, drs2 };
}

export function sampleRange(pathEl: SVGPathElement, total: number, fromL: number, len: number, n = 40) {
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const l = (((fromL + (len * i) / n) % total) + total) % total;
    const p = pathEl.getPointAtLength(l);
    pts.push([p.x, p.y]);
  }
  return pts;
}
