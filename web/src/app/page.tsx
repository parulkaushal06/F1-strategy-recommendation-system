"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import CircuitTrack from "@/components/CircuitTrack";
import season from "@/data/season_2023.json";
import standings from "@/data/standings_2023_r11.json";
import { getCircuitData } from "@/data/circuitRegistry";
import { SPA_QUICK_FACTS } from "@/data/spaCircuit";
import { api, type RaceInfo } from "@/lib/api";

const TEAM_COLORS: Record<string, string> = {
  "Red Bull": "#2246A8",
  Ferrari: "#C1121C",
  Mercedes: "#4DD9C4",
  "Aston Martin": "#1F7A5C",
  McLaren: "#E8792E",
};

// "Bahrain Grand Prix" -> ["Bahrain", "Grand Prix"], so the hero heading can
// keep its two-line display style for whichever race is actually next,
// instead of the name being hardcoded to Belgium/Spa.
function splitRaceName(name: string): [string, string | null] {
  const suffix = " Grand Prix";
  if (name.endsWith(suffix)) {
    return [name.slice(0, -suffix.length), "Grand Prix"];
  }
  return [name, null];
}

function statusPill(status: string) {
  if (status === "done") {
    return (
      <span className="pill pill--teal">
        <span className="dot" />
        DONE
      </span>
    );
  }
  if (status === "next") {
    return (
      <span className="pill pill--accent">
        <span className="live-dot" />
        NEXT
      </span>
    );
  }
  return (
    <span className="pill">
      <span className="dot" />
      UPCOMING
    </span>
  );
}

export default function SeasonHub() {
  const next = useMemo(() => season.find((r) => r.status === "next") ?? season[0], []);
  const [info, setInfo] = useState<RaceInfo | null>(null);
  const [infoError, setInfoError] = useState(false);

  useEffect(() => {
    if (!next) return;
    api.raceInfo(next.raceId).then(setInfo).catch(() => setInfoError(true));
  }, [next]);

  const circuit = useMemo(() => (info ? getCircuitData(info.circuitName) : null), [info]);
  const [headingMain, headingSuffix] = splitRaceName(next?.name ?? "Season");

  // Rich quick facts (lap record, DRS zone count) only exist as real, sourced
  // data for Spa right now (see docs/06_known_limitations.md). For any other
  // "next" race, show only what's genuinely available rather than fabricate
  // numbers for it — total laps from the API, corner count and map precision
  // from the circuit registry (both real, per-circuit data).
  const isSpa = info?.circuitName === "Circuit de Spa-Francorchamps";

  return (
    <>
      <Nav active="/" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-14 pb-10 grid md:grid-cols-[1.1fr_0.9fr] gap-10 items-center">
        <div>
          <div className="eyebrow mb-4">
            2023 SEASON · ROUND {next?.round} OF {season.length} ·{" "}
            {next && new Date(next.date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }).toUpperCase()}
          </div>
          <h1 className="text-[40px] sm:text-[56px] md:text-[76px] leading-[0.92]">
            {headingMain}
            {headingSuffix && (
              <>
                <br />
                {headingSuffix}
              </>
            )}
          </h1>
          <p className="mt-5 text-[15px] text-[color:var(--ink-secondary)] max-w-[46ch]">
            {next?.location}, {next?.country}
            {isSpa &&
              " — the fastest lap on the calendar, decided by two DRS zones and a weather system that rarely agrees with itself."}
          </p>
          <div className="mt-7 flex flex-wrap gap-x-8 gap-y-4 mono text-[13px] text-[color:var(--ink-secondary)]">
            {isSpa ? (
              <>
                <div>
                  <div className="text-[11px] mb-1">CIRCUIT LENGTH</div>
                  <div className="text-[color:var(--ink-primary)] text-[16px]">{SPA_QUICK_FACTS.circuitLengthKm} km</div>
                </div>
                <div>
                  <div className="text-[11px] mb-1">RACE LAPS</div>
                  <div className="text-[color:var(--ink-primary)] text-[16px]">{info?.totalLaps ?? SPA_QUICK_FACTS.laps}</div>
                </div>
                <div>
                  <div className="text-[11px] mb-1">LAP RECORD</div>
                  <div className="text-[color:var(--ink-primary)] text-[16px]">
                    {SPA_QUICK_FACTS.lapRecord} · {SPA_QUICK_FACTS.lapRecordDriver}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] mb-1">DRS ZONES</div>
                  <div className="text-[color:var(--ink-primary)] text-[16px]">{SPA_QUICK_FACTS.drsZones.length}</div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <div className="text-[11px] mb-1">RACE LAPS</div>
                  <div className="text-[color:var(--ink-primary)] text-[16px]">{info?.totalLaps ?? "—"}</div>
                </div>
                {circuit && (
                  <div>
                    <div className="text-[11px] mb-1">CORNERS</div>
                    <div className="text-[color:var(--ink-primary)] text-[16px]">{circuit.numCorners}</div>
                  </div>
                )}
                {infoError && (
                  <div className="text-[13px] text-[color:var(--ink-muted)]">
                    Couldn&apos;t reach the strategy API for live race details (is uvicorn running on :8000?)
                  </div>
                )}
              </>
            )}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href={`/race-hub?raceId=${next?.raceId}`} className="btn">
              View Circuit &amp; Sessions
            </Link>
            <Link href={`/strategy?raceId=${next?.raceId}`} className="btn btn--accent">
              Run Win Probability →
            </Link>
          </div>
        </div>

        <div className="card p-6 relative overflow-hidden">
          <div className="eyebrow mb-3">TRACK MAP</div>
          {circuit ? (
            <CircuitTrack pathD={circuit.pathD} />
          ) : (
            <div className="aspect-square w-full flex items-center justify-center text-[13px] text-[color:var(--ink-muted)]">
              No traced map for this circuit yet
            </div>
          )}
          {circuit && <div className="absolute top-6 right-6 pill pill--teal">{circuit.numCorners} CORNERS</div>}
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 py-8">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-[22px]">Race Calendar</h2>
          <span className="eyebrow">SCROLL FOR ALL {season.length} ROUNDS →</span>
        </div>
        <div className="flex gap-3 overflow-x-auto pb-3 scrollbar-thin">
          {season.map((race) => (
            <Link
              key={race.round}
              href={`/race-hub?raceId=${race.raceId}`}
              className="card p-4 min-w-[176px] shrink-0"
              style={race.status === "next" ? { borderColor: "var(--accent)" } : undefined}
            >
              <div className="eyebrow mb-3">ROUND {String(race.round).padStart(2, "0")}</div>
              <div className="text-[16px] font-semibold mb-1">{race.name.replace(" Grand Prix", " GP")}</div>
              <div className="text-[13px] text-[color:var(--ink-secondary)] mb-4">
                {race.location} ·{" "}
                {new Date(race.date).toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit" })}
              </div>
              {statusPill(race.status)}
            </Link>
          ))}
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 py-10 grid md:grid-cols-2 gap-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-5">
            <h3 className="text-[20px]">Drivers&apos; Championship</h3>
            <span className="eyebrow">AFTER ROUND {standings.after_round}</span>
          </div>
          <div className="space-y-1">
            {standings.drivers.map((d, i) => (
              <div
                key={d.name}
                className={`grid grid-cols-[24px_1fr_auto] gap-3 items-center py-2.5 ${
                  i < standings.drivers.length - 1 ? "hairline-bottom" : ""
                }`}
              >
                <span className="mono text-[13px] text-[color:var(--ink-muted)]">{d.position}</span>
                <span>{d.name}</span>
                <span className="mono text-[15px]">{d.points}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-5">
            <h3 className="text-[20px]">Constructors&apos; Championship</h3>
            <span className="eyebrow">AFTER ROUND {standings.after_round}</span>
          </div>
          <div className="space-y-1">
            {standings.constructors.map((c, i) => (
              <div
                key={c.name}
                className={`grid grid-cols-[24px_1fr_auto] gap-3 items-center py-2.5 ${
                  i < standings.constructors.length - 1 ? "hairline-bottom" : ""
                }`}
              >
                <span className="mono text-[13px] text-[color:var(--ink-muted)]">{c.position}</span>
                <span className="flex items-center gap-2">
                  <i className="w-2 h-2 rounded-full inline-block" style={{ background: TEAM_COLORS[c.name] ?? "var(--ink-muted)" }} />
                  {c.name}
                </span>
                <span className="mono text-[15px]">{c.points}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}