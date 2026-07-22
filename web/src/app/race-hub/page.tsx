"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import CircuitTrack from "@/components/CircuitTrack";
import { getCircuitData } from "@/data/circuitRegistry";
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
  const [error, setError] = useState<string | null>(null);
  const [initializedFromQuery, setInitializedFromQuery] = useState(false);

  useEffect(() => {
    api.seasons().then(setSeasons).catch(() => setError("Could not reach the strategy API (is uvicorn running on :8000?)"));
  }, []);

  useEffect(() => {
    api.races(season).then((list) => {
      setRaces(list);
      const queryRaceId = searchParams.get("raceId");
      if (!initializedFromQuery && queryRaceId && list.some((r) => r.raceId === Number(queryRaceId))) {
        setRaceId(Number(queryRaceId));
      } else {
        const belgian = list.find((r) => r.name.includes("Belgian"));
        setRaceId((belgian ?? list[0])?.raceId ?? null);
      }
      setInitializedFromQuery(true);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }).catch(() => setError("Failed to load races"));
  }, [season]);

  useEffect(() => {
    if (raceId == null) return;
    fetch(`${API_URL}/api/race-info?raceId=${raceId}`)
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => setError("Failed to load race info"));
  }, [raceId]);

  const circuit = useMemo(() => (info ? getCircuitData(info.circuitName) : null), [info]);

  return (
    <>
      <Nav active="/race-hub" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-10 pb-6">
        <div className="card p-4 flex flex-wrap items-center gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="eyebrow">SEASON</span>
            <select className="btn !py-2" value={season} onChange={(e) => setSeason(Number(e.target.value))}>
              {seasons.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow">RACE</span>
            <select className="btn !py-2" value={raceId ?? ""} onChange={(e) => setRaceId(Number(e.target.value))}>
              {races.map((r) => <option key={r.raceId} value={r.raceId}>{r.name}</option>)}
            </select>
          </div>
        </div>
        {error && <div className="mb-6 pill pill--accent">{error}</div>}

        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow mb-3">
              {info && `ROUND ${info.round} · ${info.year}`}
            </div>
            <h1 className="text-[44px] md:text-[58px] leading-[0.95]">{info?.name ?? "—"}</h1>
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
          className="card p-6 flex items-center justify-between hover:border-[color:var(--accent)]"
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
