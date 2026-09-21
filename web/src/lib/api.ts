const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface RaceSummary {
  raceId: number;
  round: number;
  name: string;
  circuitName: string;
}

export interface DriverSummary {
  driverId: number;
  code: string;
  name: string;
  team: string;
}

export interface LapBounds {
  maxLap: number;
  totalLaps: number;
}

export interface StrategySnapshot {
  winProbability: number;
  pitUrgencyScore: number;
  tireAgeRatio: number;
  lapsOnCurrentTires: number;
  pitRecommendation: string;
  drsRecommendation: string;
  ersRecommendation: string;
  raceCraftRecommendation: string;
  gapToAheadMs: number | null;
  gapToBehindMs: number | null;
  simulatedPitNow: {
    winProbability: number;
    probabilityChange: number;
    note: string;
  };
}

export interface StrategyResponse {
  meta: {
    circuitName: string;
    year: number;
    round: number;
    totalLaps: number;
    maxLap: number;
    position: number;
    team: string;
    code: string;
  };
  current: StrategySnapshot;
  history: { lap: number; winProb: number }[];
  field: {
    position: number;
    driverId: number;
    code: string;
    team: string;
    winProbability: number;
    pitRecommendation: string;
    drsAvailable: boolean;
    raceCraftRecommendation: string;
  }[];
  featureImportance: { feature: string; importance: number }[];
}

export interface CompareDriverResult {
  driverId: number;
  code: string;
  name: string;
  team: string;
  position: number;
  lapsOnCurrentTires: number;
  current: StrategySnapshot;
  history: { lap: number; winProb: number }[];
}

export interface CompareResponse {
  driverA: CompareDriverResult;
  driverB: CompareDriverResult;
}

async function getJSON<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])));
  const res = await fetch(`${API_URL}${path}?${qs}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} failed: ${res.status} ${body}`);
  }
  return res.json();
}

export interface RaceInfo {
  raceId: number;
  year: number;
  round: number;
  name: string;
  circuitName: string;
  totalLaps: number;
}

export const api = {
  seasons: (): Promise<number[]> => fetch(`${API_URL}/api/seasons`).then((r) => r.json()),
  races: (year: number): Promise<RaceSummary[]> => getJSON("/api/races", { year }),
  raceInfo: (raceId: number): Promise<RaceInfo> => getJSON("/api/race-info", { raceId }),
  drivers: (raceId: number): Promise<DriverSummary[]> => getJSON("/api/drivers", { raceId }),
  laps: (raceId: number, driverId: number): Promise<LapBounds> => getJSON("/api/laps", { raceId, driverId }),
  strategy: (raceId: number, driverId: number, lap: number): Promise<StrategyResponse> =>
    getJSON("/api/strategy", { raceId, driverId, lap }),
  compare: (raceId: number, driverAId: number, driverBId: number, lap: number): Promise<CompareResponse> =>
    getJSON("/api/compare", { raceId, driverAId, driverBId, lap }),
};