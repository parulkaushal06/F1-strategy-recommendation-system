"use client";

import { useMemo, useState } from "react";
import { analyzeTrack, sampleRange } from "@/lib/trackAnalysis";

interface CircuitTrackProps {
  pathD: string;
  viewBox?: string;
  numCorners?: number;
  /** Real, telemetry-aligned sector boundary coordinates for this circuit, if available. */
  sectorPoints?: [number, number][];
  sectorLabels?: string[];
  showDrsZones?: boolean;
  showStartFinishMark?: boolean;
  /** When set, draws a live position dot at this lap out of totalLaps. */
  lap?: number;
  totalLaps?: number;
  className?: string;
}

export default function CircuitTrack({
  pathD,
  viewBox = "0 0 500 500",
  numCorners = 19,
  sectorPoints,
  sectorLabels = ["S1/S2", "S2/S3"],
  showDrsZones = true,
  showStartFinishMark = true,
  lap,
  totalLaps,
  className,
}: CircuitTrackProps) {
  const [pathEl, setPathEl] = useState<SVGPathElement | null>(null);
  const analysis = useMemo(
    () => (pathEl ? analyzeTrack(pathEl, { numCorners }) : null),
    [pathEl, numCorners]
  );
  const drsPolylines = useMemo(() => {
    if (!pathEl || !analysis || !showDrsZones) return [];
    return [analysis.drs1, analysis.drs2].map((zone) =>
      sampleRange(pathEl, analysis.total, zone.fromL, zone.len)
        .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
        .join(" ")
    );
  }, [pathEl, analysis, showDrsZones]);

  const startFinishLine = useMemo(() => {
    if (!pathEl || !analysis || !showStartFinishMark) return null;
    // These circuit SVGs conventionally start their path at (or right next to) the
    // real start/finish line, so a perpendicular tick at length 0 lines up correctly
    // for any circuit's own outline — unlike a hardcoded decoration copied from one
    // specific track's file, which wouldn't generalize to the others.
    const p0 = pathEl.getPointAtLength(0);
    const p1 = pathEl.getPointAtLength(Math.min(3, analysis.total * 0.01));
    const dx = p1.x - p0.x, dy = p1.y - p0.y;
    const len = Math.hypot(dx, dy) || 1;
    const px = -dy / len, py = dx / len; // perpendicular to travel direction
    const halfWidth = 12;
    return {
      x1: p0.x - px * halfWidth, y1: p0.y - py * halfWidth,
      x2: p0.x + px * halfWidth, y2: p0.y + py * halfWidth,
    };
  }, [pathEl, analysis, showStartFinishMark]);

  const carPoint =
    analysis && lap != null && totalLaps && pathEl
      ? pathEl.getPointAtLength(((lap - 1) / (totalLaps - 1)) * analysis.total)
      : null;

  return (
    <svg viewBox={viewBox} className={className}>
      {/* key remounts the outline when its path changes, so the ref and analysis follow the new geometry */}
      <path
        key={pathD}
        ref={setPathEl}
        d={pathD}
        fill="none"
        stroke="var(--surface-3)"
        strokeWidth="16"
        strokeLinejoin="round"
      />
      {drsPolylines.map((points, i) => (
        <polyline
          key={i}
          points={points}
          fill="none"
          stroke="var(--status-teal)"
          strokeWidth="16"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.5}
        />
      ))}
      <path
        d={pathD}
        fill="none"
        stroke="var(--ink-secondary)"
        strokeWidth="1.25"
        strokeDasharray="1 7"
        strokeLinecap="round"
      />
      {startFinishLine && (
        <line
          x1={startFinishLine.x1}
          y1={startFinishLine.y1}
          x2={startFinishLine.x2}
          y2={startFinishLine.y2}
          stroke="var(--accent)"
          strokeWidth="3"
        />
      )}
      {analysis?.corners.map((c, i) => (
        <g key={i} fontFamily="var(--font-mono-family)" fontSize="10" fill="var(--ink-secondary)">
          <circle cx={c.x} cy={c.y} r="8" fill="var(--surface-2)" stroke="var(--hairline-strong)" />
          <text x={c.x} y={c.y + 3.2} textAnchor="middle">
            {i + 1}
          </text>
        </g>
      ))}
      {sectorPoints?.map(([x, y], i) => (
        <g key={i} fontFamily="var(--font-mono-family)" fontSize="10" fill="var(--status-purple)">
          <circle cx={x} cy={y} r="4" fill="var(--status-purple)" />
          <text x={x + 9} y={y - 6}>
            {sectorLabels[i] ?? ""}
          </text>
        </g>
      ))}
      {carPoint && (
        <circle cx={carPoint.x} cy={carPoint.y} r="8" fill="var(--accent)" stroke="var(--surface-0)" strokeWidth="2" />
      )}
    </svg>
  );
}
