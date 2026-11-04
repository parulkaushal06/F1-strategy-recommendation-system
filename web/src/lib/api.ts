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

// The backend sleeps on a free hosting tier. While it wakes up, requests fail with a
// network error or a 502/503/504. Retry those a few times instead of showing an error
// straight away. Normal 4xx/5xx answers (e.g. a 404 for a retired driver) are NOT retried.
const RETRY_STATUSES = new Set([502, 503, 504]);

async function fetchWithRetry(url: string, attempts = 5, delayMs = 4000): Promise<Response> {
  let lastError: unknown = new Error("request failed");
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url);
      if (!RETRY_STATUSES.has(res.status)) return res;
      lastError = new Error(`server unavailable (${res.status})`);
    } catch (e) {
      lastError = e;
    }
    if (i < attempts - 1) await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  throw lastError;
}

async function getJSON<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])));
  const res = await fetchWithRetry(`${API_URL}${path}?${qs}`);
  if (!res.ok) {
    // Prefer the API's human-readable `detail` (e.g. "Cannot overtake: ...")
    // over a raw path+status+JSON blob.
    let detail = "";
    try {
      const parsed: { detail?: unknown } = JSON.parse(await res.text());
      detail = typeof parsed.detail === "string" ? parsed.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface RaceInfo {
  raceId: number;
  year: number;
  round: number;
  name: string;
  circuitName: string;
  totalLaps: number;
}

export interface PitTimingOption {
  label: string;
  lapsFromNow: number;
  winProbability: number;
  changePoints: number;
}

export interface SimulateResponse {
  currentWinProbability: number;
  options: PitTimingOption[];
  bestOptionLabel: string;
  normalizationNote?: string;
}

export type WhatIfAction = "pit" | "push" | "attack" | "drs" | "overtake";

export interface WhatIfResponse {
  verdict: string;                        // e.g. "PIT+PUSH: 68% -> 75% (+7%)"
  actionsApplied: WhatIfAction[];
  currentWinProbability: number;          // 0-1 fraction
  simulatedWinProbability: number;        // 0-1 fraction
  changePoints: number;                   // percentage points, e.g. +7.0
  perActionNotes: Record<string, string>; // honesty labels per action
  normalizationNote?: string;
}

export interface ExplanationResponse {
  calibrated_win_probability: number;
  raw_calibrated_win_probability?: number;
  normalization_note?: string;
  top_factors: { feature: string; actual_value: number | null; shap_impact_points: number; direction: string }[];
}

// NEW: evaluation metrics served by GET /api/model-metrics (written by train_model.py)
export interface ModelMetrics {
  test_year: number;
  calibration_year: number;
  calibration_years?: number[];
  splits: { train_rows: number; calib_rows: number; test_rows: number };
  test_metrics: { roc_auc: number; precision: number; recall: number; brier_score: number };
  feature_importance_top10: { feature: string; importance: number }[];
  library_versions?: { scikit_learn: string; pandas: string };
  race_level_evaluation?: {
    test_year: number;
    races: number;
    winner_top1_accuracy: number;
    winner_top1_accuracy_ci95: [number, number];
    row_roc_auc_race_bootstrap_ci95: [number, number];
    row_brier_race_bootstrap_ci95: [number, number];
  };
  walk_forward_cv?: {
    folds: number;
    test_years: number[];
    roc_auc_mean: number;
    roc_auc_std: number;
    brier_mean: number;
  };
}

// FIX: raw wire-format shapes for endpoints whose JSON keys are snake_case.
// Typed explicitly instead of `any` — same runtime behavior, zero lint errors.
interface RawPitTimingOption {
  label: string;
  laps_from_now: number;
  win_probability: number;
  change_points: number;
}

interface RawSimulateResponse {
  current_win_probability: number;
  best_option_label: string;
  options: RawPitTimingOption[];
  normalization_note?: string;
}

interface RawWhatIfResponse {
  verdict: string;
  actions_applied: WhatIfAction[];
  current_win_probability: number;
  simulated_win_probability: number;
  change_points: number;
  per_action_notes?: Record<string, string>;
  normalization_note?: string;
}

export const api = {
  seasons: (): Promise<number[]> => fetchWithRetry(`${API_URL}/api/seasons`).then((r) => r.json() as Promise<number[]>),
  // Single quick check used by the "waking up" banner; never throws.
  health: async (timeoutMs = 15000): Promise<boolean> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${API_URL}/health`, { signal: controller.signal });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  },
  races: (year: number): Promise<RaceSummary[]> => getJSON("/api/races", { year }),
  raceInfo: (raceId: number): Promise<RaceInfo> => getJSON("/api/race-info", { raceId }),
  drivers: (raceId: number): Promise<DriverSummary[]> => getJSON("/api/drivers", { raceId }),
  laps: (raceId: number, driverId: number): Promise<LapBounds> => getJSON("/api/laps", { raceId, driverId }),
  strategy: (raceId: number, driverId: number, lap: number): Promise<StrategyResponse> =>
    getJSON("/api/strategy", { raceId, driverId, lap }),
  explain: (raceId: number, driverId: number, lap: number): Promise<ExplanationResponse> =>
    getJSON("/api/explain", { raceId, driverId, lap }),
  compare: (raceId: number, driverAId: number, driverBId: number, lap: number): Promise<CompareResponse> =>
    getJSON("/api/compare", { raceId, driverAId, driverBId, lap }),
  // NEW: evaluation metrics — fetched once by the model evaluation strip
  modelMetrics: (): Promise<ModelMetrics> =>
    fetch(`${API_URL}/api/model-metrics`).then((r) => {
      if (!r.ok) throw new Error("model metrics unavailable");
      return r.json() as Promise<ModelMetrics>;
    }),
  simulate: (raceId: number, driverId: number, lap: number): Promise<SimulateResponse> =>
    getJSON<RawSimulateResponse>("/api/simulate/pit-timings", { raceId, driverId, lap }).then((raw) => ({
      currentWinProbability: raw.current_win_probability,
      bestOptionLabel: raw.best_option_label,
      normalizationNote: raw.normalization_note,
      options: raw.options.map((o) => ({
        label: o.label,
        lapsFromNow: o.laps_from_now,
        winProbability: o.win_probability,
        changePoints: o.change_points,
      })),
    })),
  whatIf: (raceId: number, driverId: number, lap: number, actions: WhatIfAction[]): Promise<WhatIfResponse> =>
    getJSON<RawWhatIfResponse>("/api/simulate/what-if", { raceId, driverId, lap, actions: actions.join(",") }).then((raw) => ({
      verdict: raw.verdict,
      actionsApplied: raw.actions_applied,
      currentWinProbability: raw.current_win_probability,
      simulatedWinProbability: raw.simulated_win_probability,
      changePoints: raw.change_points,
      perActionNotes: raw.per_action_notes ?? {},
      normalizationNote: raw.normalization_note,
    })),
};
