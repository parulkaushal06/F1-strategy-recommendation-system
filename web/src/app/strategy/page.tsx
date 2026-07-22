"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import CircuitTrack from "@/components/CircuitTrack";
import { getCircuitData } from "@/data/circuitRegistry";
import { api, type RaceSummary, type DriverSummary, type StrategyResponse } from "@/lib/api";

const TEAM_COLORS: Record<string, string> = {
  "Red Bull": "#2246A8",
  Ferrari: "#C1121C",
  Mercedes: "#4DD9C4",
  "Aston Martin": "#1F7A5C",
  McLaren: "#E8792E",
  Alpine: "#2D6FE0",
  AlphaTauri: "#3A4A5C",
  "Alfa Romeo": "#A32029",
  Williams: "#4FA8E0",
  Haas: "#B7B7B7",
};

function statusColor(kind: "pit" | "drs" | "ers" | "craft", text: string) {
  if (kind === "pit") return text.startsWith("PIT NOW") ? "var(--accent)" : text.startsWith("CONSIDER") ? "var(--status-amber)" : "var(--status-teal)";
  if (kind === "drs") return text.includes("AVAILABLE") ? "var(--status-teal)" : "var(--ink-muted)";
  if (kind === "ers") return text.includes("OVERTAKE") ? "var(--status-purple)" : "var(--ink-muted)";
  return text.includes("URGENTLY") ? "var(--accent)" : text.includes("DEFEND") ? "var(--status-amber)" : text.includes("ATTACK") ? "var(--status-purple)" : "var(--status-teal)";
}

function StrategyDashboardInner() {
  const searchParams = useSearchParams();
  const [seasons, setSeasons] = useState<number[]>([]);
  const [season, setSeason] = useState<number>(2023);
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [raceId, setRaceId] = useState<number | null>(null);
  const [drivers, setDrivers] = useState<DriverSummary[]>([]);
  const [driverId, setDriverId] = useState<number | null>(null);
  const [maxLap, setMaxLap] = useState(44);
  const [lap, setLap] = useState(32);
  const [data, setData] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initializedFromQuery, setInitializedFromQuery] = useState(false);

  // Seasons, once
  useEffect(() => {
    api.seasons().then(setSeasons).catch(() => setError("Could not reach the strategy API (is uvicorn running on :8000?)"));
  }, []);

  // Races for the selected season -> honor ?raceId= from a deep link once, then
  // default to Belgian GP if present, else first
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

  // Drivers for the selected race -> default to VER if present, else first
  useEffect(() => {
    if (raceId == null) return;
    api.drivers(raceId).then((list) => {
      setDrivers(list);
      const ver = list.find((d) => d.code === "VER");
      setDriverId((ver ?? list[0])?.driverId ?? null);
    }).catch(() => setError("Failed to load drivers"));
  }, [raceId]);

  // Lap bounds for the selected race+driver
  useEffect(() => {
    if (raceId == null || driverId == null) return;
    api.laps(raceId, driverId).then((bounds) => {
      setMaxLap(bounds.maxLap);
      setLap((prev) => Math.min(prev, bounds.maxLap));
    }).catch(() => setError("Failed to load lap range"));
  }, [raceId, driverId]);

  // Debounced fetch of the actual strategy snapshot as the lap slider moves
  useEffect(() => {
    if (raceId == null || driverId == null) return;
    setLoading(true);
    const handle = setTimeout(() => {
      api.strategy(raceId, driverId, lap)
        .then((res) => { setData(res); setError(null); })
        .catch((e) => setError(String(e.message ?? e)))
        .finally(() => setLoading(false));
    }, 120);
    return () => clearTimeout(handle);
  }, [raceId, driverId, lap]);

  const driver = useMemo(() => drivers.find((d) => d.driverId === driverId), [drivers, driverId]);
  const circuit = useMemo(() => (data ? getCircuitData(data.meta.circuitName) : null), [data]);

  const sparkline = useMemo(() => {
    if (!data || data.history.length === 0) return "";
    const pts = data.history;
    const w = 400, h = 80, pad = 4;
    const minLap = pts[0].lap, maxLapVal = pts[pts.length - 1].lap;
    const lapSpan = Math.max(1, maxLapVal - minLap);
    return pts
      .map((p) => {
        const x = pad + ((p.lap - minLap) / lapSpan) * (w - pad * 2);
        const y = h - pad - (p.winProb / 100) * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data]);

  return (
    <>
      <Nav active="/strategy" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-8 pb-6">
        <div className="card p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="eyebrow">SEASON</span>
            <select className="btn !py-2" value={season} onChange={(e) => setSeason(Number(e.target.value))}>
              {seasons.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow">RACE</span>
            <select className="btn !py-2" value={raceId ?? ""} onChange={(e) => setRaceId(Number(e.target.value))}>
              {races.map((r) => (
                <option key={r.raceId} value={r.raceId}>{r.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow">DRIVER</span>
            <select className="btn !py-2" value={driverId ?? ""} onChange={(e) => setDriverId(Number(e.target.value))}>
              {drivers.map((d) => (
                <option key={d.driverId} value={d.driverId}>{d.code} · {d.name}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[220px] flex items-center gap-4">
            <span className="eyebrow shrink-0">LAP</span>
            <input type="range" min={1} max={maxLap} value={lap} onChange={(e) => setLap(Number(e.target.value))} />
            <span className="mono text-[14px] shrink-0 w-[64px] text-right">{lap}/{maxLap}</span>
          </div>
        </div>
        {error && <div className="mt-3 pill pill--accent">{error}</div>}
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-6 grid lg:grid-cols-[1fr_1fr] gap-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-4">
            <div className="eyebrow">
              LIVE POSITION · LAP {lap} {data && `· P${data.meta.position}`}
            </div>
            {driver && (
              <span className="pill" style={{ color: TEAM_COLORS[driver.team], borderColor: TEAM_COLORS[driver.team] }}>
                <span className="dot" />{driver.team}
              </span>
            )}
          </div>
          {circuit ? (
            <CircuitTrack
              pathD={circuit.pathD}
              sectorPoints={circuit.sectorPoints}
              numCorners={circuit.numCorners}
              lap={lap}
              totalLaps={maxLap}
              className="w-full h-auto"
            />
          ) : (
            <div className="aspect-square flex items-center justify-center text-center px-8">
              <p className="text-[13px] text-[color:var(--ink-muted)]">
                No real circuit outline available for {data?.meta.circuitName ?? "this venue"} yet —
                FastF1 doesn&apos;t reliably cover pre-2018 sessions.
              </p>
            </div>
          )}
          <div className="mt-2 flex justify-between mono text-[11px] text-[color:var(--ink-muted)]">
            <span>GAP AHEAD: {data?.current.gapToAheadMs != null ? `${(data.current.gapToAheadMs / 1000).toFixed(3)}s` : "—"}</span>
            <span>GAP BEHIND: {data?.current.gapToBehindMs != null ? `${(data.current.gapToBehindMs / 1000).toFixed(3)}s` : "—"}</span>
          </div>
        </div>

        <div className="card p-6 flex flex-col">
          <div className="eyebrow mb-2">WIN PROBABILITY · LAP {lap}/{maxLap}</div>
          <div className="flex items-end gap-4 mb-2">
            <div className="display text-[84px] leading-none">
              {data ? Math.round(data.current.winProbability) : "—"}
              <span className="text-[36px] align-top">%</span>
            </div>
            <div className="pill mb-3">
              <span className="dot" />
              PIT URGENCY {data?.current.pitUrgencyScore ?? "—"}/100
            </div>
          </div>
          <svg viewBox="0 0 400 80" className="w-full h-[80px] mt-2">
            {sparkline && (
              <>
                <polyline points={sparkline} fill="none" stroke="var(--prob-70)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                {(() => {
                  const [x, y] = sparkline.split(" ").pop()!.split(",");
                  return <circle cx={x} cy={y} r="4" fill="var(--prob-70)" />;
                })()}
              </>
            )}
          </svg>
          <div className="flex justify-between mono text-[11px] text-[color:var(--ink-muted)] mt-1 mb-6">
            <span>LAP 1</span>
            <span>LAP {lap} (NOW)</span>
          </div>

          <div className="eyebrow mb-3 mt-auto">FEATURE IMPORTANCE (real, from the trained model)</div>
          <div className="space-y-2.5">
            {data?.featureImportance.slice(0, 3).map((row) => (
              <div key={row.feature}>
                <div className="flex justify-between mono text-[11px] mb-1">
                  <span className="text-[color:var(--ink-secondary)]">{row.feature}</span>
                  <span>{row.importance}</span>
                </div>
                <div className="h-1.5 rounded-full bg-[color:var(--surface-2)]">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.min(100, (row.importance / (data.featureImportance[0]?.importance || 1)) * 100)}%`, background: "var(--prob-70)" }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-6">
        <div className="eyebrow mb-4">RECOMMENDATIONS</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card p-5" style={{ borderLeft: `3px solid ${data ? statusColor("pit", data.current.pitRecommendation) : "var(--hairline)"}` }}>
            <div className="eyebrow mb-3">PIT STOP</div>
            <div className="text-[15px] font-semibold mb-2">{data?.current.pitRecommendation.split(" (")[0] ?? "—"}</div>
            <div className="text-[12px] text-[color:var(--ink-secondary)]">
              {data ? `Tire age ratio ${(data.current.tireAgeRatio * 100).toFixed(0)}% · ${data.current.lapsOnCurrentTires} laps on current tires.` : ""}
            </div>
          </div>
          <div className="card p-5" style={{ borderLeft: `3px solid ${data ? statusColor("drs", data.current.drsRecommendation) : "var(--hairline)"}` }}>
            <div className="eyebrow mb-3">DRS</div>
            <div className="text-[15px] font-semibold mb-2">{data?.current.drsRecommendation ?? "—"}</div>
            <div className="text-[12px] text-[color:var(--ink-secondary)]">Rule-based proxy beyond the 3 validated telemetry races.</div>
          </div>
          <div className="card p-5" style={{ borderLeft: `3px solid ${data ? statusColor("ers", data.current.ersRecommendation) : "var(--hairline)"}` }}>
            <div className="eyebrow mb-3">ERS</div>
            <div className="text-[15px] font-semibold mb-2">{data?.current.ersRecommendation.split(" (")[0] ?? "—"}</div>
            <div className="text-[12px] text-[color:var(--ink-secondary)]">Proxy signal — no public ERS deployment data exists.</div>
          </div>
          <div className="card p-5" style={{ borderLeft: `3px solid ${data ? statusColor("craft", data.current.raceCraftRecommendation) : "var(--hairline)"}` }}>
            <div className="eyebrow mb-3">RACE CRAFT</div>
            <div className="text-[15px] font-semibold mb-2">{data?.current.raceCraftRecommendation.split(" (")[0] ?? "—"}</div>
            <div className="text-[12px] text-[color:var(--ink-secondary)]">
              {data?.current.raceCraftRecommendation.match(/\(([^)]+)\)/)?.[1] ?? ""}
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-6">
        <div className="card p-6">
          <div className="eyebrow mb-2">MODEL CONTEXT — WHAT IF THIS DRIVER PITTED THIS LAP?</div>
          {data && (
            <div className="text-[14px] text-[color:var(--ink-secondary)] mt-2">
              Simulated win probability if pitting now: <span className="text-[color:var(--ink-primary)] mono">{data.current.simulatedPitNow.winProbability}%</span>{" "}
              (change: <span className="mono" style={{ color: data.current.simulatedPitNow.probabilityChange >= 0 ? "var(--status-teal)" : "var(--accent)" }}>
                {data.current.simulatedPitNow.probabilityChange >= 0 ? "+" : ""}{data.current.simulatedPitNow.probabilityChange} pts
              </span>)
              <div className="text-[11px] text-[color:var(--ink-muted)] mt-2">{data.current.simulatedPitNow.note}</div>
            </div>
          )}
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-16">
        <div className="card p-6">
          <div className="eyebrow mb-4">FIELD CONTEXT — LAP {lap} {loading && "(updating…)"}</div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="eyebrow text-left hairline-bottom">
                  <th className="py-2 pr-4 font-normal">POS</th>
                  <th className="py-2 pr-4 font-normal">DRIVER</th>
                  <th className="py-2 pr-4 font-normal">TEAM</th>
                  <th className="py-2 pr-4 font-normal text-right">WIN %</th>
                  <th className="py-2 pr-4 font-normal text-right">PIT</th>
                  <th className="py-2 pr-4 font-normal text-right">DRS</th>
                  <th className="py-2 pr-4 font-normal text-right">RACE CRAFT</th>
                </tr>
              </thead>
              <tbody className="mono">
                {data?.field.map((row, i, arr) => (
                  <tr
                    key={row.driverId}
                    className={i < arr.length - 1 ? "hairline-bottom" : ""}
                    style={row.driverId === driverId ? { background: "color-mix(in oklab, var(--accent) 8%, transparent)" } : undefined}
                  >
                    <td className="py-2.5 pr-4">{row.position}</td>
                    <td className="py-2.5 pr-4">
                      <span className="inline-flex items-center gap-2">
                        <i className="w-2 h-2 rounded-full inline-block" style={{ background: TEAM_COLORS[row.team] ?? "var(--ink-muted)" }} />
                        {row.code}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-[color:var(--ink-secondary)]">{row.team}</td>
                    <td className="py-2.5 pr-4 text-right">{row.winProbability.toFixed(1)}</td>
                    <td className="py-2.5 pr-4 text-right">{row.pitRecommendation}</td>
                    <td className="py-2.5 pr-4 text-right">{row.drsAvailable ? "Yes" : "No"}</td>
                    <td className="py-2.5 pr-4 text-right">{row.raceCraftRecommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}

export default function StrategyDashboard() {
  return (
    <Suspense fallback={null}>
      <StrategyDashboardInner />
    </Suspense>
  );
}
