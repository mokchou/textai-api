// Types alignés sur le backend FastAPI (source de vérité : backend/app/api/*.py)

// ----------------------------- configuration ------------------------------ //

export type FieldType = "number" | "integer" | "boolean" | "choice" | "json";

export interface SchemaField {
  name: string;
  type: FieldType;
  label_fr: string;
  tooltip_fr: string | null;
  unit: string | null;
  default: unknown;
  min: number | null;
  max: number | null;
  options: string[] | null;
}

export interface SchemaGroup {
  key: string;
  label_fr: string;
  fields: SchemaField[];
}

export interface ConfigSchema {
  groups: SchemaGroup[];
}

export type BotConfig = Record<string, Record<string, unknown>>;

export interface ActiveConfig {
  config: BotConfig;
  config_hash: string;
}

export interface ValidationResult {
  valide: boolean;
  erreurs_fr: string[];
  config_hash?: string;
}

export interface PresetSummary {
  id: number;
  name: string;
  config_hash: string;
  created_at: number;
}

export interface Preset extends PresetSummary {
  config: BotConfig;
}

// -------------------------------- jobs ------------------------------------ //

export type JobStatus = "en_cours" | "termine" | "erreur";

export interface Job {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  started_at: number;
  result: unknown;
  error: string | null;
}

// ------------------------------- datasets --------------------------------- //

export interface Dataset {
  id: number;
  symbol: string;
  timeframe: string;
  hash: string;
  start_ts?: number;
  end_ts?: number;
  created_at?: number;
  manifest: Record<string, unknown>;
}

// ------------------------------- métriques -------------------------------- //

export interface Metriques {
  pnl_net: number;
  pnl_net_pct: number;
  pnl_brut: number;
  total_frais: number;
  total_slippage: number;
  total_funding: number;
  nb_trades: number;
  nb_avortes: number;
  win_rate_pct: number;
  expectancy_r: number;
  profit_factor: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number;
  max_drawdown_pct: number;
  max_drawdown_duree_jours: number;
  exposition_pct: number;
  mae_moyen_r: number;
  mfe_moyen_r: number;
  [k: string]: number | null | undefined;
}

export interface AttributionCouts {
  pnl_brut: number;
  frais: number;
  slippage: number;
  funding: number;
  pnl_net: number;
  couts_totaux: number;
  ratio_couts_pct: number | null;
  edge_fragile: boolean;
  avertissement_fr?: string;
  note_funding_fr?: string;
  funding_taux_de_repli_utilise?: boolean;
  pour_100_brut?: {
    frais: number;
    slippage: number;
    funding: number;
    net: number;
  };
}

// ------------------------------- backtests -------------------------------- //

export interface Trade {
  symbol: string;
  direction: string;
  mode: string;
  entry_ts: number;
  exit_ts: number;
  entry_price: number;
  exit_price: number;
  qty: number;
  exit_reason: string;
  aborted: boolean;
  pnl_gross: number;
  entry_fee: number;
  exit_fee: number;
  slippage_cost: number;
  funding_cost: number;
  pnl_net: number;
  r_multiple: number;
  mae: number;
  mfe: number;
  entry_signals?: Record<string, unknown>;
}

export interface EquityPoint {
  ts: number;
  equite: number;
  drawdown: number;
}

export interface BacktestReport {
  run_id: string;
  metriques: Metriques;
  ventilations: Record<string, unknown>;
  attribution_couts: AttributionCouts;
  trades: Trade[];
}

export interface BacktestSummary {
  id: number;
  run_id: string;
  status: string;
  started_at: number;
  finished_at: number | null;
  engine_version: string;
  symbol: string | null;
  timeframe: string | null;
  dataset_hash: string | null;
}

export interface BacktestDetail {
  id: number;
  run_id: string;
  dataset_id: number;
  status: string;
  started_at: number;
  finished_at: number | null;
  engine_version: string;
  report: BacktestReport | null;
  equity: EquityPoint[] | null;
}

// ------------------------------ optimisation ------------------------------ //

export interface GridResult {
  params: Record<string, number>;
  [metric: string]: unknown;
}

export interface StabilityReport {
  metrique: string;
  parametres: string[];
  axes: number[][];
  heatmap: (number | null)[][];
  optimum: { params: Record<string, number>; valeur: number };
  score_plateau: number | null;
  optimum_isole: boolean;
  avertissement_fr?: string;
}

export interface WalkForwardWindow {
  fenetre: { train: [number, number]; test: [number, number] };
  params_retenus: Record<string, number>;
  score_plateau: number | null;
  optimum_isole: boolean;
  metriques_test: Metriques;
}

export interface WalkForwardReport {
  fenetres: WalkForwardWindow[];
  metriques_agregees_test: Metriques;
  nb_fenetres: number;
  params_balayes: string[];
  derniers_params: Record<string, number> | null;
  stabilite_derniere_fenetre: number | null;
}

export interface OptimizeJobSummary {
  id: number;
  kind: "grid" | "walkforward";
  dataset_id: number;
  status: string;
  created_at: number;
  finished_at: number | null;
}

export interface OptimizeJobDetail extends OptimizeJobSummary {
  results?: GridResult[] | WalkForwardReport;
  stability?: StabilityReport;
  params?: { path: string; values: number[] }[];
  base_config?: BotConfig;
}

// ------------------------------ paper trading ----------------------------- //

export interface PaperPosition {
  direction: string;
  mode: string;
  qty: number;
  prix_entree: number;
  stop_courant: number;
  pnl_latent: number;
  funding_cumule: number;
  trailing_actif: boolean;
  confirme: boolean;
}

export interface PendingOrder {
  mode: string;
  direction: string;
  prix: number;
  suspendu: boolean;
}

export interface PaperSnapshot {
  session_id: number;
  symbol: string;
  ts: number;
  etat: string;
  equite: number;
  kill_switch: boolean;
  kill_raison: string | null;
  pertes_consecutives: number;
  position: PaperPosition | null;
  ordres_en_attente: PendingOrder[];
  nb_trades: number;
}

export interface JournalEvaluation {
  signals: Record<string, unknown>;
  filters?: Record<string, unknown>;
  reasons_fr: string[];
  decisions: { action: string; payload?: Record<string, unknown> }[];
}

export interface JournalEntry {
  id?: number;
  session_id: number;
  ts: number;
  symbol: string;
  state: string;
  evaluation: JournalEvaluation;
  has_decision: number | boolean;
}

export interface CoherenceMatch {
  entry_ts: number;
  direction: string;
  mode: string;
  identique: boolean;
  ecart_prix_entree_pct: number;
  pnl_paper: number;
  pnl_backtest: number;
  motif_sortie_paper: string;
  motif_sortie_backtest: string;
}

export interface CoherenceReport {
  nb_trades_paper: number;
  nb_trades_backtest: number;
  nb_apparies: number;
  nb_identiques: number;
  pct_identiques: number;
  objectif_atteint: boolean;
  seuil_pct: number;
  causes_ecarts_fr: string[];
  appariements: CoherenceMatch[];
  paper_sans_equivalent: Trade[];
  backtest_sans_equivalent: Trade[];
}

// ------------------------------- adaptation ------------------------------- //

export interface AdaptiveSettings {
  enabled: boolean;
  mode: "approbation_manuelle" | "auto";
  cron_day_of_week: string;
  cron_hour_utc: number;
  lookback_days: number;
  train_days: number;
  test_days: number;
  adaptive_params: string[];
  grid_points: number;
  min_plateau_score: number;
  min_profit_factor_test: number;
  max_drawdown_test_pct: number;
  max_param_delta_pct: number;
  metric: string;
}

export interface GuardrailReport {
  passed: boolean;
  checks?: Record<string, unknown> | unknown[];
  reasons_fr: string[];
}

export interface AdaptiveChange {
  id: number;
  ts: number;
  trigger_kind: string;
  status: string;
  applied_at?: number | null;
  stability_score: number | null;
  diff: Record<string, { avant: unknown; apres: unknown }>;
  guardrail_report: GuardrailReport | null;
  old_config?: BotConfig;
  new_config?: BotConfig;
}

// ------------------------------ tableau de bord --------------------------- //

export interface DashboardKpis {
  scope: string;
  metriques: Metriques;
  attribution_couts: AttributionCouts;
  ventilations?: Record<string, unknown>;
  equite?: { ts: number; equite: number }[];
}

// -------------------------------- websocket ------------------------------- //

export interface WsMessage {
  channel: string;
  payload: Record<string, unknown>;
}
