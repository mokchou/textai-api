import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "../api/client";
import type { BacktestSummary, DashboardKpis, PaperSnapshot } from "../api/types";
import CostWaterfall from "../components/charts/CostWaterfall";
import { EquitySparkline } from "../components/charts/EquityCurve";
import Badge from "../components/ui/Badge";
import KpiTile from "../components/ui/KpiTile";
import { fmtInt, fmtMoney, fmtPct, fmtR, fmtRatio } from "../utils/format";

interface ScopeOption {
  value: string;
  label: string;
}

export default function Dashboard() {
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [sessions, setSessions] = useState<PaperSnapshot[]>([]);
  const [scope, setScope] = useState<string>("");
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [equity, setEquity] = useState<{ ts: number; equite: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [bts, state] = await Promise.all([
          api.backtests(),
          api.paperState().catch(() => ({ sessions: [] as PaperSnapshot[] })),
        ]);
        const done = bts.filter((b) => b.status === "termine");
        setBacktests(done);
        setSessions(state.sessions);
        if (done.length > 0) setScope(`backtest:${done[0].id}`);
        else if (state.sessions.length > 0) setScope(`paper:${state.sessions[0].session_id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erreur de chargement.");
      }
    })();
  }, []);

  useEffect(() => {
    if (!scope) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const data = await api.dashboardKpis(scope);
        if (cancelled) return;
        setKpis(data);
        if (data.equite) {
          setEquity(data.equite);
        } else if (scope.startsWith("backtest:")) {
          const bt = await api.backtest(Number(scope.split(":")[1]));
          if (!cancelled) setEquity(bt.equity ?? []);
        } else {
          setEquity([]);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erreur de chargement des KPI.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scope]);

  const options: ScopeOption[] = useMemo(
    () => [
      ...backtests.map((b) => ({
        value: `backtest:${b.id}`,
        label: `Backtest n°${b.id} — ${b.symbol ?? "?"} ${b.timeframe ?? ""}`,
      })),
      ...sessions.map((s) => ({
        value: `paper:${s.session_id}`,
        label: `Paper n°${s.session_id} — ${s.symbol}`,
      })),
    ],
    [backtests, sessions],
  );

  const m = kpis?.metriques;
  const couts = kpis?.attribution_couts;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-100">Tableau de bord</h1>
        <div className="flex items-center gap-2">
          <label htmlFor="scope" className="text-sm text-slate-400">
            Périmètre
          </label>
          <select
            id="scope"
            className="input w-72"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            {options.length === 0 && <option value="">Aucune source disponible</option>}
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error && (
        <div className="card border-red-500/40 text-sm text-red-400" role="alert">
          {error}
        </div>
      )}

      {!scope && !error && (
        <p className="card text-sm text-slate-400">
          Aucun backtest terminé ni session paper : lancez un backtest pour alimenter le tableau de
          bord.
        </p>
      )}

      {m && couts && (
        <>
          <section
            className={`grid grid-cols-2 gap-3 md:grid-cols-4 ${loading ? "opacity-60" : ""}`}
            aria-label="Indicateurs clés"
          >
            <KpiTile
              label="PnL net"
              value={fmtMoney(m.pnl_net)}
              sub={fmtPct(m.pnl_net_pct, 2)}
              tone={m.pnl_net >= 0 ? "positive" : "negative"}
            />
            <KpiTile label="Taux de réussite" value={fmtPct(m.win_rate_pct, 1)} sub={`${fmtInt(m.nb_trades)} trades`} />
            <KpiTile
              label="Espérance"
              value={fmtR(m.expectancy_r)}
              tone={m.expectancy_r >= 0 ? "positive" : "negative"}
            />
            <KpiTile label="Profit factor" value={fmtRatio(m.profit_factor)} />
            <KpiTile label="Sharpe" value={fmtRatio(m.sharpe)} sub={`Sortino ${fmtRatio(m.sortino)}`} />
            <KpiTile
              label="Drawdown max"
              value={fmtPct(m.max_drawdown_pct, 2)}
              sub={`${fmtMoney(m.max_drawdown)} — ${fmtRatio(m.max_drawdown_duree_jours)} j`}
              tone="negative"
            />
            <KpiTile label="Exposition" value={fmtPct(m.exposition_pct, 1)} />
            <KpiTile
              label="Ratio de coûts"
              value={fmtPct(couts.ratio_couts_pct, 1)}
              badge={
                couts.edge_fragile ? (
                  <Badge tone="red">
                    <AlertTriangle size={12} aria-hidden="true" /> Edge fragile
                  </Badge>
                ) : undefined
              }
              tone={couts.edge_fragile ? "negative" : "neutral"}
            />
          </section>

          {couts.avertissement_fr && (
            <div className="card border-red-500/40 text-sm text-red-300" role="alert">
              <AlertTriangle size={14} className="mr-1 inline" aria-hidden="true" />
              {couts.avertissement_fr}
            </div>
          )}

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="card">
              <h2 className="mb-2 text-sm font-semibold text-slate-300">Courbe d'équité</h2>
              <EquitySparkline data={equity} height={180} />
            </div>
            <div className="card">
              <h2 className="mb-2 text-sm font-semibold text-slate-300">Attribution des coûts</h2>
              <CostWaterfall couts={couts} height={180} />
              {couts.note_funding_fr && (
                <p className="mt-2 text-xs text-amber-400">{couts.note_funding_fr}</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
