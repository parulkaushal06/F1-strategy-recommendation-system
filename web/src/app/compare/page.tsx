"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { api, type RaceSummary, type DriverSummary, type CompareResponse } from "@/lib/api";

function buildPolyline(history: { lap: number; winProb: number }[], w = 900, h = 300, pad = 20) {
  if (history.length === 0) return { points: "", last: null as null | { x: number; y: number; value: number } };
  const minLap = history[0].lap, maxLap = history[history.length - 1].lap;
  const span = Math.max(1, maxLap - minLap);
  const pts = history.map((p) => {
    const x = pad + ((p.lap - minLap) / span) * (w - pad * 2);
    const y = h - pad - (p.winProb / 100) * (h - pad * 2);
    return { x, y, value: p.winProb };
  });
  return { points: pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" "), last: pts[pts.length - 1] };
}

export default function DriverComparison() {
  const [season] = useState(2023);
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [raceId, setRaceId] = useState<number | null>(null);
  const [drivers, setDrivers] = useState<DriverSummary[]>([]);
  const [driverAId, setDriverAId] = useState<number | null>(null);
  const [driverBId, setDriverBId] = useState<number | null>(null);
  const [maxLap, setMaxLap] = useState(44);
  const [lap, setLap] = useState(32);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.races(season).then((list) => {
      setRaces(list);
      const belgian = list.find((r) => r.name.includes("Belgian"));
      setRaceId((belgian ?? list[0])?.raceId ?? null);
    }).catch(() => setError("Could not reach the strategy API (is uvicorn running on :8000?)"));
  }, [season]);

  useEffect(() => {
    if (raceId == null) return;
    api.drivers(raceId).then((list) => {
      setDrivers(list);
      const ver = list.find((d) => d.code === "VER");
      const ham = list.find((d) => d.code === "HAM");
      setDriverAId((ver ?? list[0])?.driverId ?? null);
      setDriverBId((ham ?? list[1])?.driverId ?? null);
    }).catch(() => setError("Failed to load drivers"));
  }, [raceId]);

  useEffect(() => {
    if (raceId == null || driverAId == null) return;
    api.laps(raceId, driverAId).then((b) => {
      setMaxLap(b.maxLap);
      setLap((prev) => Math.min(prev, b.maxLap));
    }).catch(() => {});
  }, [raceId, driverAId]);

  useEffect(() => {
    if (raceId == null || driverAId == null || driverBId == null || driverAId === driverBId) return;
    const handle = setTimeout(() => {
      api.compare(raceId, driverAId, driverBId, lap)
        .then((res) => { setData(res); setError(null); })
        .catch((e) => setError(String(e.message ?? e)));
    }, 120);
    return () => clearTimeout(handle);
  }, [raceId, driverAId, driverBId, lap]);

  const lineA = useMemo(() => (data ? buildPolyline(data.driverA.history) : { points: "", last: null }), [data]);
  const lineB = useMemo(() => (data ? buildPolyline(data.driverB.history) : { points: "", last: null }), [data]);

  return (
    <>
      <Nav active="/compare" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-10 pb-6">
        <div className="eyebrow mb-3">HEAD TO HEAD</div>
        <h1 className="text-[40px] md:text-[52px] leading-[0.95] mb-8">Driver Comparison</h1>

        <div className="card p-4 flex flex-wrap items-center gap-4 mb-8">
          <div className="flex items-center gap-2">
            <span className="eyebrow">RACE</span>
            <select className="btn !py-2" value={raceId ?? ""} onChange={(e) => setRaceId(Number(e.target.value))}>
              {races.map((r) => <option key={r.raceId} value={r.raceId}>{r.name}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-[220px] flex items-center gap-4">
            <span className="eyebrow shrink-0">LAP</span>
            <input type="range" min={1} max={maxLap} value={lap} onChange={(e) => setLap(Number(e.target.value))} />
            <span className="mono text-[14px] shrink-0 w-[64px] text-right">{lap}/{maxLap}</span>
          </div>
        </div>
        {error && <div className="mb-6 pill pill--accent">{error}</div>}

        <div className="grid sm:grid-cols-2 gap-4 mb-8">
          <div className="card p-5 flex items-center gap-4" style={{ borderLeft: "3px solid var(--driver-a)" }}>
            <div className="w-3 h-3 rounded-full shrink-0" style={{ background: "var(--driver-a)" }} />
            <div className="flex-1">
              <div className="eyebrow mb-1">DRIVER A</div>
              <select className="text-[18px] font-semibold bg-transparent w-full" value={driverAId ?? ""} onChange={(e) => setDriverAId(Number(e.target.value))}>
                {drivers.map((d) => <option key={d.driverId} value={d.driverId}>{d.code} · {d.name}</option>)}
              </select>
              <div className="text-[12px] text-[color:var(--ink-secondary)]">{data?.driverA.team}</div>
            </div>
          </div>
          <div className="card p-5 flex items-center gap-4" style={{ borderLeft: "3px solid var(--driver-b)" }}>
            <div className="w-3 h-3 rounded-full shrink-0" style={{ background: "var(--driver-b)" }} />
            <div className="flex-1">
              <div className="eyebrow mb-1">DRIVER B</div>
              <select className="text-[18px] font-semibold bg-transparent w-full" value={driverBId ?? ""} onChange={(e) => setDriverBId(Number(e.target.value))}>
                {drivers.map((d) => <option key={d.driverId} value={d.driverId}>{d.code} · {d.name}</option>)}
              </select>
              <div className="text-[12px] text-[color:var(--ink-secondary)]">{data?.driverB.team}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-8">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-5">
            <div className="eyebrow">WIN PROBABILITY OVER RACE DISTANCE (real, from the trained model)</div>
            <div className="flex gap-4 eyebrow">
              <span className="flex items-center gap-2"><i className="w-2 h-2 rounded-full inline-block" style={{ background: "var(--driver-a)" }} />{data?.driverA.code}</span>
              <span className="flex items-center gap-2"><i className="w-2 h-2 rounded-full inline-block" style={{ background: "var(--driver-b)" }} />{data?.driverB.code}</span>
            </div>
          </div>
          <svg viewBox="0 0 900 300" className="w-full h-auto">
            <g stroke="var(--hairline)" strokeWidth="1">
              <line x1="0" y1="40" x2="900" y2="40" /><line x1="0" y1="110" x2="900" y2="110" />
              <line x1="0" y1="180" x2="900" y2="180" /><line x1="0" y1="250" x2="900" y2="250" />
            </g>
            <g fontFamily="var(--font-mono-family)" fontSize="11" fill="var(--ink-muted)">
              <text x="0" y="36">100%</text><text x="0" y="106">66%</text>
              <text x="0" y="176">33%</text><text x="0" y="246">0%</text>
            </g>
            {lineA.points && <polyline points={lineA.points} fill="none" stroke="var(--driver-a)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
            {lineA.last && <>
              <circle cx={lineA.last.x} cy={lineA.last.y} r="4" fill="var(--driver-a)" />
              <text x={lineA.last.x + 8} y={lineA.last.y + 4} fontFamily="var(--font-mono-family)" fontSize="12" fill="var(--driver-a)">{lineA.last.value.toFixed(0)}%</text>
            </>}
            {lineB.points && <polyline points={lineB.points} fill="none" stroke="var(--driver-b)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
            {lineB.last && <>
              <circle cx={lineB.last.x} cy={lineB.last.y} r="4" fill="var(--driver-b)" />
              <text x={lineB.last.x + 8} y={lineB.last.y + 4} fontFamily="var(--font-mono-family)" fontSize="12" fill="var(--driver-b)">{lineB.last.value.toFixed(0)}%</text>
            </>}
          </svg>
          <div className="flex justify-between mono text-[11px] text-[color:var(--ink-muted)] mt-2">
            <span>LAP 1</span><span>LAP {maxLap}</span>
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-16">
        <div className="card p-6">
          <div className="eyebrow mb-5">STAT DELTA · LAP {lap}</div>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="eyebrow text-left hairline-bottom">
                <th className="py-2 pr-4 font-normal w-1/3">METRIC</th>
                <th className="py-2 pr-4 font-normal text-right">{data?.driverA.code ?? "A"}</th>
                <th className="py-2 pr-4 font-normal text-right">{data?.driverB.code ?? "B"}</th>
              </tr>
            </thead>
            <tbody className="mono">
              {data && [
                { metric: "Position", a: `P${data.driverA.position}`, b: `P${data.driverB.position}`, lead: data.driverA.position < data.driverB.position ? "a" : "b" },
                { metric: "Win probability", a: `${data.driverA.current.winProbability.toFixed(1)}%`, b: `${data.driverB.current.winProbability.toFixed(1)}%`, lead: data.driverA.current.winProbability > data.driverB.current.winProbability ? "a" : "b" },
                { metric: "Tyre age", a: `${data.driverA.lapsOnCurrentTires} laps`, b: `${data.driverB.lapsOnCurrentTires} laps`, lead: data.driverA.lapsOnCurrentTires < data.driverB.lapsOnCurrentTires ? "a" : "b" },
                { metric: "Pit urgency", a: `${data.driverA.current.pitUrgencyScore}/100`, b: `${data.driverB.current.pitUrgencyScore}/100`, lead: null },
                { metric: "Race craft", a: data.driverA.current.raceCraftRecommendation.split(" (")[0], b: data.driverB.current.raceCraftRecommendation.split(" (")[0], lead: null },
              ].map((row, i, arr) => (
                <tr key={row.metric} className={i < arr.length - 1 ? "hairline-bottom" : ""}>
                  <td className="py-3 pr-4 text-[color:var(--ink-secondary)]">{row.metric}</td>
                  <td className="py-3 pr-4 text-right">
                    <span className="inline-flex items-center gap-1.5 justify-end">
                      {row.lead === "a" && <i className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: "var(--driver-a)" }} />}
                      {row.a}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span className="inline-flex items-center gap-1.5 justify-end">
                      {row.lead === "b" && <i className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: "var(--driver-b)" }} />}
                      {row.b}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Footer />
    </>
  );
}
