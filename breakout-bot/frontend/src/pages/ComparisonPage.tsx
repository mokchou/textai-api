import { useEffect, useState } from "react";
import { GitCompareArrows } from "lucide-react";
import { api } from "../api/client";
import type { BacktestDetail, BacktestSummary } from "../api/types";
import { EquityCompare } from "../components/charts/EquityCurve";
import Badge from "../components/ui/Badge";
import { fmtDateTime, shortHash } from "../utils/format";
import { METRIC_DEFS } from "../utils/metrics";

export default function ComparisonPage() {
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [details, setDetails] = useState<BacktestDetail[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .backtests()
      .then((bts) => setBacktests(bts.filter((b) => b.status === "termine")))
      .catch((e) => setError(e instanceof Error ? e.message : "Erreur de chargement."));
  }, []);

  const toggle = (id: number) => {
    setSelected((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : cur.length >= 4 ? cur : [...cur, id],
    );
  };

  const onCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      setDetails(await api.backtestsCompare(selected));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de la comparaison.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-100">Comparaison de backtests</h1>

      {error && (
        <div className="card border-red-500/40 text-sm text-red-400" role="alert">
          {error}
        </div>
      )}

      <section className="card space-y-3">
        <p className="text-sm text-slate-400">
          Sélectionnez 2 à 4 backtests terminés ({selected.length} sélectionné
          {selected.length > 1 ? "s" : ""}).
        </p>
        <div className="grid max-h-72 grid-cols-1 gap-1 overflow-auto md:grid-cols-2">
          {backtests.map((b) => (
            <label
              key={b.id}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                selected.includes(b.id)
                  ? "border-sky-500/60 bg-sky-500/10"
                  : "border-slate-800 hover:bg-slate-800/50"
              }`}
            >
              <input
                type="checkbox"
                className="accent-sky-500"
                checked={selected.includes(b.id)}
                onChange={() => toggle(b.id)}
              />
              <span className="font-medium text-slate-200">
                n°{b.id} — {b.symbol ?? "?"} {b.timeframe ?? ""}
              </span>
              <span className="text-xs text-slate-500">{fmtDateTime(b.started_at)}</span>
              <Badge tone="blue" mono>
                {shortHash(b.dataset_hash, 8)}
              </Badge>
            </label>
          ))}
          {backtests.length === 0 && (
            <p className="text-sm text-slate-500">Aucun backtest terminé disponible.</p>
          )}
        </div>
        <button
          className="btn-primary"
          disabled={selected.length < 2 || loading}
          onClick={onCompare}
        >
          <GitCompareArrows size={15} aria-hidden="true" />
          {loading ? "Comparaison…" : "Comparer"}
        </button>
      </section>

      {details.length >= 2 && (
        <>
          <section className="card">
            <h2 className="mb-2 text-sm font-semibold text-slate-300">
              Courbes d'équité superposées
            </h2>
            <EquityCompare
              series={details.map((d) => ({
                name: `Backtest n°${d.id}`,
                data: d.equity ?? [],
              }))}
            />
          </section>

          <section className="card overflow-auto">
            <h2 className="mb-2 text-sm font-semibold text-slate-300">Métriques côte à côte</h2>
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-2 text-left font-medium">Métrique</th>
                  {details.map((d) => (
                    <th key={d.id} className="px-3 py-2 text-right font-medium">
                      n°{d.id}
                      <span className="ml-1 font-mono normal-case text-sky-400">
                        {shortHash(d.report?.run_id, 8)}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {METRIC_DEFS.map((def) => {
                  const values = details.map(
                    (d) => (d.report?.metriques[def.key] as number | null) ?? null,
                  );
                  const finite = values.filter((v): v is number => v != null && isFinite(v));
                  const best = def.higherIsBetter && finite.length ? Math.max(...finite) : null;
                  return (
                    <tr key={def.key}>
                      <td className="px-3 py-1.5 text-slate-400">{def.label}</td>
                      {values.map((v, i) => (
                        <td
                          key={i}
                          className={`px-3 py-1.5 text-right tabular-nums ${
                            best != null && v === best
                              ? "font-semibold text-emerald-400"
                              : "text-slate-200"
                          }`}
                        >
                          {def.fmt(v)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
