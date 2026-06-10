import type {
  ActiveConfig,
  AdaptiveChange,
  AdaptiveSettings,
  BacktestDetail,
  BacktestSummary,
  BotConfig,
  CoherenceReport,
  ConfigSchema,
  DashboardKpis,
  Dataset,
  Job,
  JournalEntry,
  OptimizeJobDetail,
  OptimizeJobSummary,
  PaperSnapshot,
  Preset,
  PresetSummary,
  ValidationResult,
} from "./types";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    let message = `Erreur HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        message = Array.isArray(body.detail) ? body.detail.join(" ; ") : String(body.detail);
      }
    } catch {
      /* corps non JSON */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

const get = <T>(url: string) => http<T>(url);
const post = <T>(url: string, body?: unknown) =>
  http<T>(url, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
const put = <T>(url: string, body: unknown) =>
  http<T>(url, { method: "PUT", body: JSON.stringify(body) });

export const api = {
  // configuration
  configSchema: () => get<ConfigSchema>("/api/config/schema"),
  configActive: () => get<ActiveConfig>("/api/config/active"),
  configSave: (config: BotConfig) =>
    put<{ ok: boolean; config_hash: string }>("/api/config/active", config),
  configValidate: (config: BotConfig) => post<ValidationResult>("/api/config/validate", config),
  configDefaults: () => get<BotConfig>("/api/config/defaults"),
  presets: () => get<PresetSummary[]>("/api/configs"),
  presetSave: (name: string, config: BotConfig) =>
    post<{ id: number; config_hash: string }>("/api/configs", { name, config }),
  preset: (id: number) => get<Preset>(`/api/configs/${id}`),

  // datasets
  datasets: () => get<Dataset[]>("/api/datasets"),
  datasetBuild: (body: { symbol: string; timeframe: string; start_ts: number; end_ts: number }) =>
    post<{ job_id: string }>("/api/datasets/build", body),

  // jobs
  job: (jobId: string) => get<Job>(`/api/jobs/${jobId}`),

  // backtests
  backtests: () => get<BacktestSummary[]>("/api/backtests"),
  backtest: (id: number) => get<BacktestDetail>(`/api/backtests/${id}`),
  backtestLaunch: (body: { dataset_id: number; config?: BotConfig }) =>
    post<{ job_id: string; backtest_id: number }>("/api/backtests", body),
  backtestsCompare: (ids: number[]) =>
    get<BacktestDetail[]>(`/api/backtests/compare?ids=${ids.join(",")}`),

  // optimisation
  optimizeGrid: (body: {
    dataset_id: number;
    params: { path: string; values: number[] }[];
    metric: string;
  }) => post<{ job_id: string; optimize_id: number }>("/api/optimize/grid", body),
  optimizeWalkforward: (body: {
    dataset_id: number;
    params: { path: string; values: number[] }[];
    metric: string;
    train_days: number;
    test_days: number;
  }) => post<{ job_id: string; optimize_id: number }>("/api/optimize/walkforward", body),
  optimizeJobs: () => get<OptimizeJobSummary[]>("/api/optimize/jobs"),
  optimizeJob: (id: number) => get<OptimizeJobDetail>(`/api/optimize/jobs/${id}`),

  // paper trading
  paperStart: (symbol?: string) =>
    post<{ session_id: number }>("/api/paper/start", symbol ? { symbol } : {}),
  paperStop: (sessionId: number) => post<{ ok: boolean }>(`/api/paper/stop/${sessionId}`),
  paperState: () => get<{ sessions: PaperSnapshot[] }>("/api/paper/state"),
  paperJournal: (sessionId?: number, limit = 200) =>
    get<JournalEntry[]>(
      `/api/paper/journal?limit=${limit}${sessionId != null ? `&session_id=${sessionId}` : ""}`,
    ),
  paperKillSwitchReset: (sessionId: number) =>
    post<{ ok: boolean }>(`/api/paper/kill-switch/reset/${sessionId}`),
  paperCoherence: (sessionId: number) =>
    get<CoherenceReport>(`/api/paper/coherence/${sessionId}`),

  // adaptation
  adaptiveSettings: () => get<AdaptiveSettings>("/api/adaptive/settings"),
  adaptiveSettingsSave: (settings: AdaptiveSettings) =>
    put<{ ok: boolean }>("/api/adaptive/settings", settings),
  adaptiveHistory: (limit = 100) => get<AdaptiveChange[]>(`/api/adaptive/history?limit=${limit}`),
  adaptiveRunNow: () => post<{ job_id: string }>("/api/adaptive/run-now"),
  adaptiveApprove: (changeId: number) =>
    post<{ ok: boolean }>(`/api/adaptive/proposals/${changeId}/approve`),
  adaptiveReject: (changeId: number) =>
    post<{ ok: boolean }>(`/api/adaptive/proposals/${changeId}/reject`),

  // tableau de bord
  dashboardKpis: (scope: string) =>
    get<DashboardKpis>(`/api/dashboard/kpis?scope=${encodeURIComponent(scope)}`),
};
