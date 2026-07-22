// Generalized version of the one-off Spa script: given an SVG path's 'd'
// string, samples it and picks curvature-peak corners, same algorithm as
// web/src/lib/trackAnalysis.ts. Used to register real FastF1 corner
// coordinates onto a specific circuit SVG from assets/circuits-svg/.
//
// Usage: node extract_svg_corners.js --svg <path-to-svg-file> [--corners 19]
const fs = require("fs");
const { svgPathProperties } = require("svg-path-properties");

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { corners: 19 };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--svg") out.svg = args[++i];
    if (args[i] === "--corners") out.corners = Number(args[++i]);
  }
  if (!out.svg) {
    console.error("Usage: node extract_svg_corners.js --svg <file.svg> [--corners 19]");
    process.exit(1);
  }
  return out;
}

function extractPathD(svgText) {
  const match = svgText.match(/<path[^>]*\sd="([^"]+)"/);
  if (!match) throw new Error("No <path d=\"...\"> found in SVG");
  return match[1];
}

const { svg, corners: numCorners } = parseArgs();
const svgText = fs.readFileSync(svg, "utf8");
const d = extractPathD(svgText);

const props = new svgPathProperties(d);
const total = props.getTotalLength();

const sampleCount = 720, window = 7;
const pts = [];
for (let i = 0; i < sampleCount; i++) {
  const l = (i / sampleCount) * total;
  const p = props.getPointAtLength(l);
  pts.push({ l, x: p.x, y: p.y });
}

function turnAngle(i) {
  const a = pts[(i - window + sampleCount) % sampleCount];
  const b = pts[i];
  const c = pts[(i + window) % sampleCount];
  const v1x = b.x - a.x, v1y = b.y - a.y;
  const v2x = c.x - b.x, v2y = c.y - b.y;
  let d2 = Math.atan2(v2y, v2x) - Math.atan2(v1y, v1x);
  while (d2 > Math.PI) d2 -= 2 * Math.PI;
  while (d2 < -Math.PI) d2 += 2 * Math.PI;
  return Math.abs(d2);
}

const curvature = pts.map((_, i) => turnAngle(i));
const ranked = curvature.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]);
const minSep = Math.floor(sampleCount / (numCorners * 1.5));
const chosen = [];
for (const [, i] of ranked) {
  if (chosen.length >= numCorners) break;
  if (chosen.every((j) => Math.min(Math.abs(j - i), sampleCount - Math.abs(j - i)) > minSep)) {
    chosen.push(i);
  }
}
chosen.sort((a, b) => a - b);
const cornerPts = chosen.map((i) => ({ x: pts[i].x, y: pts[i].y, l: pts[i].l }));

console.log(JSON.stringify({ pathD: d, total, corners: cornerPts }));
