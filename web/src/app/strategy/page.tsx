"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import CircuitTrack from "@/components/CircuitTrack";
import { getCircuitData } from "@/data/circuitRegistry";
// EVAL: ModelMetrics type added
import { api, type RaceSummary, type DriverSummary, type StrategyResponse, type WhatIfAction, type WhatIfResponse, type ModelMetrics } from "@/lib/api";

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

const WHAT_IF_ACTION_DOTS: Record<WhatIfAction, string> = {
  pit: "var(--status-amber)",
  push: "var(--status-teal)",
  attack: "var(--status-purple)",
  drs: "#4DD9C4",
  overtake: "var(--accent)",
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
  const [whatIfActions, setWhatIfActions] = useState<WhatIfAction[]>([]);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [whatIfError, setWhatIfError] = useState<string | null>(null);
  // REPLAY: playback state. replaySpeed 1x = one lap every 3 seconds.
  const [replaying, setReplaying] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState(1);
  // EVAL: model evaluation metrics for the bottom strip (strip hides itself if unavailable)
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);

  // Seasons, once
  useEffect(() => {
    api.seasons().then(setSeasons).catch(() => setError("Could not reach the strategy API (is uvicorn running on :8000?)"));
  }, []);

  // EVAL: fetched once — optional content, fails silently when metrics aren't generated yet
  useEffect(() => {
    api.modelMetrics().then(setMetrics).catch(() => setMetrics(null));
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

  // REPLAY: playback is tied to one race+driver run — stop it if the selection changes
  useEffect(() => {
    setReplaying(false);
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

  // REPLAY engine: advance one lap per tick, but only after the current lap's
  // strategy response has settled — every data/arrival change resets this timer,
  // so a slow server delays playback instead of piling up overlapping requests.
  useEffect(() => {
    if (!replaying || !data || error) return;
    if (lap >= maxLap) {
      setReplaying(false);
      return;
    }
    const intervalMs = Math.round(3000 / replaySpeed);
    const handle = setTimeout(() => setLap((prev) => Math.min(prev + 1, maxLap)), intervalMs);
    return () => clearTimeout(handle);
  }, [replaying, data, lap, maxLap, replaySpeed, error]);

  // What-if simulation: refetch when selected actions or race state change.
  // REPLAY: paused during playback (it would double the request rate per lap);
  // it refetches once for the current lap as soon as replay stops.
  useEffect(() => {
    if (raceId == null || driverId == null || whatIfActions.length === 0) {
      setWhatIfResult(null);
      setWhatIfError(null);
      return;
    }
    if (replaying) return;
    setWhatIfLoading(true);
    const handle = setTimeout(() => {
      api.whatIf(raceId, driverId, lap, whatIfActions)
        .then((res) => { setWhatIfResult(res); setWhatIfError(null); })
        .catch((e) => { setWhatIfError(String(e.message ?? e)); setWhatIfResult(null); })
        .finally(() => setWhatIfLoading(false));
    }, 120);
    return () => clearTimeout(handle);
  }, [raceId, driverId, lap, whatIfActions, replaying]);

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

  // REPLAY: lap-to-lap win probability delta (hidden when effectively flat)
  const lapDelta = useMemo(() => {
    if (!data) return null;
    const prev = data.history.find((p) => p.lap === lap - 1);
    if (!prev) return null;
    const delta = data.current.winProbability - prev.winProb;
    return Math.abs(delta) < 0.05 ? null : delta;
  }, [data, lap]);

  const toggleWhatIfAction = (action: WhatIfAction) => {
    setWhatIfActions((prev) =>
      prev.includes(action) ? prev.filter((a) => a !== action) : [...prev, action]
    );
  };

  // Drop actions that are physically impossible in the current race state:
  // OVERTAKE while leading, DRS while leading, DRS when it is already active.
  useEffect(() => {
    const isLeader = data?.meta.position === 1;
    const drsAlreadyOn = data?.current.drsRecommendation.includes("AVAILABLE") ?? false;
    setWhatIfActions((prev) => {
      const next = prev.filter((a) => {
        if (a === "overtake" && isLeader) return false;
        if (a === "drs" && (isLeader || drsAlreadyOn)) return false;
        return true;
      });
      return next.length === prev.length ? prev : next;
    });
  }, [data?.meta.position, data?.current.drsRecommendation]);

  const isLeader = data?.meta.position === 1;
  const drsAlreadyOn = data?.current.drsRecommendation.includes("AVAILABLE") ?? false;
  const isActionDisabled = (action: WhatIfAction) =>
    (action === "overtake" && isLeader) ||
    (action === "drs" && (isLeader || drsAlreadyOn));

  return (
    <>
      <Nav active="/strategy" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-8 pb-6">
        <div className="card p-4 flex flex-col sm:flex-wrap sm:flex-row items-stretch sm:items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="eyebrow shrink-0">SEASON</span>
            <select className="btn !py-2 max-w-full" value={season} onChange={(e) => setSeason(Number(e.target.value))}>
              {seasons.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow shrink-0">RACE</span>
            <select className="btn !py-2 max-w-full truncate" value={raceId ?? ""} onChange={(e) => setRaceId(Number(e.target.value))}>
              {races.map((r) => (
                <option key={r.raceId} value={r.raceId}>{r.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="eyebrow shrink-0">DRIVER</span>
            <select className="btn !py-2 max-w-full truncate" value={driverId ?? ""} onChange={(e) => setDriverId(Number(e.target.value))}>
              {drivers.map((d) => (
                <option key={d.driverId} value={d.driverId}>{d.code} · {d.name}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-0 sm:min-w-[220px] flex items-center gap-4">
            <span className="eyebrow shrink-0">LAP</span>
            <input type="range" min={1} max={maxLap} value={lap} onChange={(e) => setLap(Number(e.target.value))} className="min-w-0 flex-1" />
            <span className="mono text-[14px] shrink-0 w-[64px] text-right">{lap}/{maxLap}</span>
          </div>
          {/* REPLAY: playback controls — auto-advances laps over the historical data */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="btn !py-2"
              title="Auto-advance laps using historical race data"
              onClick={() => {
                if (!replaying && lap >= maxLap) setLap(1); // restart from lap 1 when finished
                setReplaying((p) => !p);
              }}
            >
              {replaying ? "⏸ Pause" : "▶ Replay"}
            </button>
            <select
              className="btn !py-2"
              value={replaySpeed}
              onChange={(e) => setReplaySpeed(Number(e.target.value))}
              title="Replay speed"
            >
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
              <option value={8}>8×</option>
            </select>
          </div>
        </div>
        {error && <div className="mt-3 pill pill--accent">{error}</div>}
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-6 grid lg:grid-cols-[1fr_1fr] gap-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-4 flex-wrap gap-2">
            {/* REPLAY: "RACE POSITION", not "LIVE" — this is historical data, honestly labeled */}
            <div className="eyebrow">
              RACE POSITION · LAP {lap} {data && `· P${data.meta.position}`}
            </div>
            <div className="flex items-center gap-2">
              {replaying && (
                <span className="pill pill--amber"><span className="dot" />Historical replay {replaySpeed}×</span>
              )}
              {driver && (
                <span className="pill" style={{ color: TEAM_COLORS[driver.team], borderColor: TEAM_COLORS[driver.team] }}>
                  <span className="dot" />{driver.team}
                </span>
              )}
            </div>
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
          <div className="flex flex-wrap items-end gap-x-4 gap-y-2 mb-2">
            <div className="display text-[56px] sm:text-[72px] md:text-[84px] leading-none">
              {data ? (data.current.winProbability < 1 ? data.current.winProbability.toFixed(1) : Math.round(data.current.winProbability)) : "—"}
              <span className="text-[28px] sm:text-[32px] md:text-[36px] align-top">%</span>
            </div>
            {/* REPLAY: how much this lap moved the probability */}
            {lapDelta != null && (
              <span className="pill mb-3" style={{ color: lapDelta >= 0 ? "var(--status-teal)" : "var(--accent)" }}>
                <span className="dot" />
                {lapDelta >= 0 ? "+" : ""}{lapDelta.toFixed(1)} pts vs last lap
              </span>
            )}
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
          <div className="flex items-baseline justify-between mb-4 flex-wrap gap-2">
            <div className="eyebrow">WHAT IF SIMULATOR — TEST YOUR OWN CALL</div>
            {data && (
              <span className="pill"><span className="dot" />LAP {lap} · P{data.meta.position}</span>
            )}
          </div>

          {/* Action chips */}
          <div className="flex flex-wrap gap-2 mb-6">
            {(["pit", "push", "attack", "drs", "overtake"] as WhatIfAction[]).map((action) => {
              const active = whatIfActions.includes(action);
              const disabled = isActionDisabled(action);
              return (
                <button
                  key={action}
                  type="button"
                  aria-pressed={active}
                  disabled={disabled}
                  title={
                    action === "drs" && isLeader
                      ? "DRS impossible while leading — no car ahead"
                      : action === "drs" && drsAlreadyOn
                        ? "DRS already active on this lap"
                        : action === "overtake" && isLeader
                          ? "Already leading — nothing to overtake"
                          : undefined
                  }
                  onClick={() => toggleWhatIfAction(action)}
                  className="btn !py-2 uppercase tracking-wide inline-flex items-center gap-2"
                  style={{
                    ...(active ? { background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" } : {}),
                    ...(disabled ? { opacity: 0.35, cursor: "not-allowed" } : {}),
                  }}
                >
                  <i className="w-2 h-2 rounded-full inline-block" style={{ background: active ? "#fff" : WHAT_IF_ACTION_DOTS[action] }} />
                  {action}
                </button>
              );
            })}
          </div>

          {whatIfLoading && <div className="text-[12px] text-[color:var(--ink-muted)] mt-2">simulating…</div>}
          {whatIfError && <div className="text-[13px] mt-2" style={{ color: "var(--accent)" }}>{whatIfError}</div>}

          {whatIfResult && !whatIfLoading && (
            <>
              {/* Big NOW -> IF YOU DO comparison */}
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 sm:gap-8 max-w-[560px]">
                <div>
                  <div className="eyebrow mb-1">NOW</div>
                  <div className="display text-[40px] sm:text-[48px] leading-none">
                    {(whatIfResult.currentWinProbability * 100).toFixed(1)}
                    <span className="text-[20px] align-top">%</span>
                  </div>
                </div>
                <div className="mono text-[24px] text-[color:var(--ink-muted)]">→</div>
                <div>
                  <div className="eyebrow mb-1">IF YOU DO: {whatIfResult.actionsApplied.join("+").toUpperCase()}</div>
                  <div
                    className="display text-[40px] sm:text-[48px] leading-none"
                    style={{ color: whatIfResult.changePoints >= 0 ? "var(--status-teal)" : "var(--accent)" }}
                  >
                    {(whatIfResult.simulatedWinProbability * 100).toFixed(1)}
                    <span className="text-[20px] align-top">%</span>
                  </div>
                </div>
              </div>

              {/* Delta badge */}
              <div className="mt-4">
                <span
                  className="pill mono"
                  style={{
                    color: whatIfResult.changePoints >= 0 ? "var(--status-teal)" : "var(--accent)",
                    borderColor: whatIfResult.changePoints >= 0 ? "var(--status-teal)" : "var(--accent)",
                  }}
                >
                  {whatIfResult.changePoints >= 0 ? "+" : ""}{whatIfResult.changePoints.toFixed(1)} pts win probability
                </span>
              </div>

              {/* Honesty footnotes */}
              <div className="hairline-top mt-5 pt-3 flex flex-col gap-1">
                {Object.entries(whatIfResult.perActionNotes).map(([action, note]) => (
                  <div key={action} className="text-[11px] text-[color:var(--ink-muted)]">
                    {action.toUpperCase()} — {note}
                  </div>
                ))}
              </div>
            </>
          )}

          {!whatIfResult && !whatIfLoading && !whatIfError && (
            <div className="text-[13px] text-[color:var(--ink-secondary)] mt-2">
              Pick one or more actions — e.g. <span className="mono">DRS + OVERTAKE</span> — to test your own hypothesis for this exact race state. Impossible calls (DRS while leading) are disabled, not faked.
            </div>
          )}
        </div>
      </section>

      {/* EVAL: field table now ends with pb-6; the model evaluation strip is the closer */}
      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-6">
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

      {/* EVAL: model evaluation strip — evaluation metrics, never plain "accuracy" */}
      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-16">
        <div className="card p-6">
          <div className="flex items-baseline justify-between flex-wrap gap-2 mb-4">
            <div className="eyebrow">MODEL EVALUATION — TIME-BASED SPLITS, NEVER RANDOM</div>
            {metrics && (
              <span className="pill"><span className="dot" />TEST YEAR {metrics.test_year}</span>
            )}
          </div>
          {metrics ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="eyebrow mb-1">ROC-AUC</div>
                  <div className="display text-[32px] leading-none">{metrics.test_metrics.roc_auc.toFixed(4)}</div>
                </div>
                <div>
                  <div className="eyebrow mb-1">BRIER SCORE</div>
                  <div className="display text-[32px] leading-none">{metrics.test_metrics.brier_score.toFixed(4)}</div>
                </div>
                <div>
                  <div className="eyebrow mb-1">PRECISION</div>
                  <div className="display text-[32px] leading-none">
                    {(metrics.test_metrics.precision * 100).toFixed(1)}<span className="text-[16px] align-top">%</span>
                  </div>
                </div>
                <div>
                  <div className="eyebrow mb-1">RECALL</div>
                  <div className="display text-[32px] leading-none">
                    {(metrics.test_metrics.recall * 100).toFixed(1)}<span className="text-[16px] align-top">%</span>
                  </div>
                </div>
              </div>
              {metrics.walk_forward_cv && (
                <div className="mt-4 text-[12px] text-[color:var(--ink-secondary)]">
                  Walk-forward cross-validation across {metrics.walk_forward_cv.folds} seasons:
                  ROC-AUC {metrics.walk_forward_cv.roc_auc_mean.toFixed(4)} ± {metrics.walk_forward_cv.roc_auc_std.toFixed(4)}
                  {" "}· calibrated probabilities (mean Brier {metrics.walk_forward_cv.brier_mean.toFixed(4)})
                </div>
              )}
              <div className="mt-3 text-[11px] text-[color:var(--ink-muted)]">
                Trained on years &lt; {metrics.calibration_year}, calibrated on {metrics.calibration_year}, evaluated on {metrics.test_year} ({metrics.splits.test_rows.toLocaleString()} laps). Plain accuracy is not shown — only 5.4% of laps end in a win, so precision/recall and AUC are the honest measures. Full write-up: docs/09_model_results.md
              </div>
            </>
          ) : (
            <div className="text-[12px] text-[color:var(--ink-muted)]">
              Evaluation metrics not available — run <span className="mono">python src/features/train_model.py</span> to generate them.
            </div>
          )}
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
