"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import CircuitTrack from "@/components/CircuitTrack";
import { getCircuitData } from "@/data/circuitRegistry";
import seasonCalendar from "@/data/season_2023.json";
import { api, type RaceSummary } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface RaceInfo {
  raceId: number;
  year: number;
  round: number;
  name: string;
  circuitName: string;
  totalLaps: number;
}

function RaceHubInner() {
  const searchParams = useSearchParams();
  const [seasons, setSeasons] = useState<number[]>([]);
  const [season, setSeason] = useState<number>(2023);
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [raceId, setRaceId] = useState<number | null>(null);
  const [info, setInfo] = useState<RaceInfo | null>(null);
  const [infoLoading, setInfoLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // FIX: one-shot flag → ref, not state (doesn't need to trigger a re-render)
  const initializedFromQuery = useRef(false);

  useEffect(() => {
    api.seasons().then(setSeasons).catch(() => setError("Could not reach the strategy API (is uvicorn running on :8000?)"));
  }, []);

  // FIX: useRef + searchParams in deps; eslint-disable removed.
  useEffect(() => {
    api.races(season).then((list) => {
      setRaces(list);
      const queryRaceId = searchParams.get("raceId");
      if (!initializedFromQuery.current && queryRaceId && list.some((r) => r.raceId === Number(queryRaceId))) {
        setRaceId(Number(queryRaceId));
      } else {
        const nextRaceId = seasonCalendar.find((r) => r.status === "next")?.raceId;
        const fallback = list.find((r) => r.raceId === nextRaceId);
        setRaceId((fallback ?? list[0])?.raceId ?? null);
      }
      initializedFromQuery.current = true;
    }).catch(() => setError("Failed to load races"));
  }, [season, searchParams]);

  // FIX: setInfoLoading(true) was synchronous in the effect body.
  // Moved inside an async IIFE so the only synchronous work is the fetch call itself.
  useEffect(() => {
    if (raceId == null) return;
    let cancelled = false;
    (async () => {
      setInfoLoading(true);
      try {
        const r = await fetch(`${API_URL}/api/race-info?raceId=${raceId}`);
        const json: RaceInfo = await r.json();
        if (!cancelled) setInfo(json);
      } catch {
        if (!cancelled) setError("Failed to load race info");
      } finally {
        if (!cancelled) setInfoLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [raceId]);

  const circuit = useMemo(() => (info ? getCircuitData(info.circuitName) : null), [info]);

  return (
    <>
      <Nav active="/race-hub" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-10 pb-6">
        <div className="card p-4 flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center gap-4 mb-6">
          {/* FIX: the old "SEASON" block was bound to raceId — that was a bug. Real season selector now. */}
          <div className="flex items-center gap-2">
            <span className="eyebrow shrink-0">SEASON</span>
            <select
              className="btn !py-2 max-w-full truncate"
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
            >
              {seasons.length === 0
                ? <option value={season}>{season}</option>
                : seasons.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow shrink-0">RACE</span>
            <select
              className="btn !py-2 max-w-full truncate"
              value={raceId ?? ""}
              onChange={(e) => setRaceId(Number(e.target.value))}
            >
              {races.length === 0
                ? <option value="">Loading races…</option>
                : races.map((r) => <option key={r.raceId} value={r.raceId}>{r.name}</option>)}
            </select>
          </div>
        </div>
        {error && <div className="mb-6 pill pill--accent">{error}</div>}

        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow mb-3">
              {info && `ROUND ${info.round} · ${info.year}`}
            </div>
            <h1 className="text-[32px] sm:text-[44px] md:text-[58px] leading-[0.95]">
            {infoLoading ? <span className="text-[color:var(--ink-muted)]">Loading race…</span> : (info?.name ?? "—")}
          </h1>
            <div className="mt-3 text-[14px] text-[color:var(--ink-secondary)]">{info?.circuitName}</div>
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 py-6 grid lg:grid-cols-[1.4fr_0.6fr] gap-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-4">
            <div className="eyebrow">CIRCUIT MAP</div>
            {circuit && (
              <div className="flex gap-2">
                <span className="pill pill--teal"><span className="dot" />DRS ZONE 1 &amp; 2 (geometry-detected)</span>
                <span className="pill pill--purple"><span className="dot" />SECTOR SPLITS (real)</span>
              </div>
            )}
          </div>
          {circuit ? (
            <CircuitTrack pathD={circuit.pathD} sectorPoints={circuit.sectorPoints} numCorners={circuit.numCorners} className="w-full h-auto" />
          ) : (
            <div className="aspect-square flex items-center justify-center text-center px-8">
              <p className="text-[13px] text-[color:var(--ink-muted)]">
                No real circuit outline available for {info?.circuitName ?? "this venue"} yet —
                FastF1 doesn&apos;t reliably cover pre-2018 sessions.
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div className="card p-5">
            <div className="eyebrow mb-4">QUICK FACTS</div>
            <div className="space-y-3 mono text-[13px]">
              <div className="flex justify-between hairline-bottom pb-3">
                <span className="text-[color:var(--ink-secondary)]">Race laps</span>
                <span>{info?.totalLaps ?? "—"}</span>
              </div>
              <div className="flex justify-between hairline-bottom pb-3">
                <span className="text-[color:var(--ink-secondary)]">Corners</span>
                <span>{circuit?.numCorners ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[color:var(--ink-secondary)]">Alignment quality</span>
                <span>{circuit ? `±${circuit.residualPx.toFixed(0)}px` : "—"}</span>
              </div>
            </div>
            <p className="text-[11px] text-[color:var(--ink-muted)] mt-4">
              Circuit length, lap record, and first-GP-year aren&apos;t in this project&apos;s dataset —
              shown only for facts we can actually derive.
            </p>
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-16">
        <Link
          href={raceId ? `/strategy?raceId=${raceId}` : "/strategy"}
          className="card p-6 flex flex-wrap items-center justify-between gap-4 hover:border-[color:var(--accent)]"
        >
          <div>
            <div className="eyebrow mb-2">STRATEGY ENGINE</div>
            <div className="text-[20px]">Run the win-probability model for this race</div>
          </div>
          <div className="btn btn--accent">Open →</div>
        </Link>
      </section>

      <Footer />
    </>
  );
}

export default function RaceHub() {
  return (
    <Suspense fallback={null}>
      <RaceHubInner />
    </Suspense>
  );
}