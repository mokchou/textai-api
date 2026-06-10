import { fmtInt, fmtMoney, fmtPct, fmtR, fmtRatio } from "./format";

export interface MetricDef {
  key: string;
  label: string;
  fmt: (v: number | null | undefined) => string;
  /** true si une valeur élevée est favorable (coloration). */
  higherIsBetter?: boolean;
}

/** Définitions FR + formatage des métriques renvoyées par le backend. */
export const METRIC_DEFS: MetricDef[] = [
  { key: "pnl_net", label: "PnL net", fmt: (v) => fmtMoney(v), higherIsBetter: true },
  { key: "pnl_net_pct", label: "PnL net (%)", fmt: (v) => fmtPct(v, 2), higherIsBetter: true },
  { key: "pnl_brut", label: "PnL brut", fmt: (v) => fmtMoney(v), higherIsBetter: true },
  { key: "total_frais", label: "Frais totaux", fmt: (v) => fmtMoney(v) },
  { key: "total_slippage", label: "Slippage total", fmt: (v) => fmtMoney(v) },
  { key: "total_funding", label: "Funding total", fmt: (v) => fmtMoney(v) },
  { key: "nb_trades", label: "Nombre de trades", fmt: fmtInt },
  { key: "nb_avortes", label: "Trades avortés", fmt: fmtInt },
  { key: "win_rate_pct", label: "Taux de réussite", fmt: (v) => fmtPct(v, 1), higherIsBetter: true },
  { key: "expectancy_r", label: "Espérance", fmt: fmtR, higherIsBetter: true },
  { key: "profit_factor", label: "Profit factor", fmt: fmtRatio, higherIsBetter: true },
  { key: "sharpe", label: "Sharpe", fmt: fmtRatio, higherIsBetter: true },
  { key: "sortino", label: "Sortino", fmt: fmtRatio, higherIsBetter: true },
  { key: "max_drawdown", label: "Drawdown max", fmt: (v) => fmtMoney(v) },
  { key: "max_drawdown_pct", label: "Drawdown max (%)", fmt: (v) => fmtPct(v, 2) },
  { key: "max_drawdown_duree_jours", label: "Durée du drawdown max (jours)", fmt: fmtRatio },
  { key: "exposition_pct", label: "Exposition", fmt: (v) => fmtPct(v, 1) },
  { key: "mae_moyen_r", label: "MAE moyen", fmt: fmtR },
  { key: "mfe_moyen_r", label: "MFE moyen", fmt: fmtR },
];

/** Métriques proposées comme objectif d'optimisation. */
export const OPTIMIZE_METRICS = [
  { value: "expectancy_r", label: "Espérance (R)" },
  { value: "pnl_net", label: "PnL net" },
  { value: "pnl_net_pct", label: "PnL net (%)" },
  { value: "profit_factor", label: "Profit factor" },
  { value: "sharpe", label: "Sharpe" },
  { value: "sortino", label: "Sortino" },
  { value: "win_rate_pct", label: "Taux de réussite (%)" },
];

export const EXIT_REASONS_FR: Record<string, string> = {
  stop: "Stop",
  trailing: "Stop suiveur",
  invalidation: "Invalidation",
  time_exit: "Sortie en temps",
  avorte: "Avorté",
  kill_switch: "Kill switch",
  manuel: "Manuel",
};

export function exitReasonFr(reason: string): string {
  return EXIT_REASONS_FR[reason] ?? reason;
}

export const ETATS_FR: Record<string, string> = {
  inactif: "Inactif",
  range_arme: "Range armé",
  en_position_non_confirmee: "En position (non confirmée)",
  en_position: "En position",
};

export function etatFr(etat: string): string {
  return ETATS_FR[etat] ?? etat;
}

export const MODES_FR: Record<string, string> = {
  mode_1: "Mode 1 (cassure)",
  mode_2: "Mode 2 (retest)",
};

export function modeFr(mode: string): string {
  return MODES_FR[mode] ?? mode;
}
