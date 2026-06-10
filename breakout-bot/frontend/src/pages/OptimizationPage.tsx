import { useCallback, useEffect, useState } from "react";
import { Play, Plus, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type {
  Dataset,
  GridResult,
  OptimizeJobDetail,
  OptimizeJobSummary,
  StabilityReport,
  WalkForwardReport,
} from "../api/types";
import { useJob } from "../api/ws";
import StabilityHeatmap from "../components/charts/StabilityHeatmap";
import Badge, { StatusBadge } from "../components/ui/Badge";
import DataTable, { type Column } from "../components/ui/DataTable";
import ProgressBar from "../components/ui/ProgressBar";
import { fmtDate, fmtDateTime, fmtInt, fmtMoney, fmtNum, fmtPct, fmtR, fmtRatio, shortHash } from "../utils/format";
import { OPTIMIZE_METRICS } from "../utils/metrics";

interface ParamRow {
  path: string;
  values: string;
}

export default function OptimizationPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState<number | "">("");
  const [params, setParams] = useState<ParamRow[]>([
    { path: "range_detection.compression_percentile", values: "20, 30, 40" },
  ]);
  const [metric, setMetric] = useState("expectancy_r");
  const [trainDays, setTrainDays] = useState(180);
  const [testDays, setTestDays] = useState(60);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pendingOptId, setPendingOptId] = useState<number | null>(null);
  const [jobs, setJobs] = useState<OptimizeJobSummary[]>([]);
  const [detail, setDetail] = useState<OptimizeJobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await api.optimizeJobs());
    } catch {
      /* non bloquant */
    }
  }, []);

  useEffect(() => {
    api
      .datasets()
      .then((ds) => {
        setDatasets(ds);
        if (ds.length > 0) setDatasetId(ds[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Erreur de chargement."));
    void refreshJobs();
  }, [refreshJobs]);

  const job = useJob(jobId, () => {
    void refreshJobs();
    if (pendingOptId != null) void openJob(pendingOptId);
    setJobId(null);
    setPendingOptId(null);
  });

  const openJob = async (id: number) => {
    try {
      setDetail(await api.optimizeJob(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement du job.");
    }
  };

  const parseParams = (): { path: string; values: number[] }[] | null => {
    const out: { path: string; values: number[] }[] = [];
    for (const p of params) {
      const path = p.path.trim();
      const values = p.values
        .split(",")
        .map((v) => Number(v.trim()))
        .filter((v) => !Number.isNaN(v));
      if (!path || values.length === 0) {
        setError("Chaque paramètre doit avoir un chemin et au moins une valeur numérique.");
        return null;
      }
      out.push({ path, values });
    }
    if (out.length < 1 || out.length > 3) {
      setError("Balayez entre 1 et 3 paramètres.");
      return null;
    }
    return out;
  };

  const launch = async (kind: "grid" | "walkforward") => {
    if (datasetId === "") return;
    setError(null);
    const parsed = parseParams();
    if (!parsed) return;
    try {
      const res =
        kind === "grid"
          ? await api.optimizeGrid({ dataset_id: datasetId, params: parsed, metric })
          : await api.optimizeWalkforward({
              dataset_id: datasetId,
              params: parsed,
              metric,
              train_days: trainDays,
              test_days: testDays,
            });
      setJobId(res.job_id);
      setPendingOptId(res.optimize_id);
      void refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec du lancement de l'optimisation.");
    }
  };

  const selectedDataset = datasets.find((d) => d.id === datasetId);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-100">Optimisation</h1>

      {error && (
        <div className="card border-red-500/40 text-sm text-red-400" role="alert">
          {error}
        </div>
      )}

      <section className="card space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="o-dataset" className="label">
              Dataset
            </label>
            <select
              id="o-dataset"
              className="input w-72"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              {datasets.length === 0 && <option value="">Aucun dataset</option>}
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  n°{d.id} — {d.symbol} {d.timeframe}
                </option>
              ))}
            </select>
          </div>
          {selectedDataset && (
            <Badge tone="blue" mono title={selectedDataset.hash}>
              {shortHash(selectedDataset.hash)}
            </Badge>
          )}
          <div>
            <label htmlFor="o-metric" className="label">
              Métrique objectif
            </label>
            <select
              id="o-metric"
              className="input w-52"
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
            >
              {OPTIMIZE_METRICS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <p className="label !mb-0">Paramètres balayés (1 à 3)</p>
          {params.map((p, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <input
                className="input w-80 font-mono text-xs"
                placeholder="chemin, ex. entries.volume_percentile"
                aria-label={`Chemin du paramètre ${i + 1}`}
                value={p.path}
                onChange={(e) =>
                  setParams(params.map((x, j) => (j === i ? { ...x, path: e.target.value } : x)))
                }
              />
              <input
                className="input w-72 font-mono text-xs"
                placeholder="valeurs séparées par des virgules, ex. 60, 70, 80"
                aria-label={`Valeurs du paramètre ${i + 1}`}
                value={p.values}
                onChange={(e) =>
                  setParams(params.map((x, j) => (j === i ? { ...x, values: e.target.value } : x)))
                }
              />
              <button
                className="btn-secondary !px-2"
                aria-label={`Supprimer le paramètre ${i + 1}`}
                disabled={params.length <= 1}
                onClick={() => setParams(params.filter((_, j) => j !== i))}
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          {params.length < 3 && (
            <button
              className="btn-secondary"
              onClick={() => setParams([...params, { path: "", values: "" }])}
            >
              <Plus size={14} aria-hidden="true" /> Ajouter un paramètre
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <button
            className="btn-primary"
            disabled={datasetId === "" || job?.status === "en_cours"}
            onClick={() => launch("grid")}
          >
            <Play size={15} aria-hidden="true" /> Lancer le grid search
          </button>
          <div className="flex items-end gap-2">
            <div>
              <label htmlFor="o-train" className="label">
                Train (jours)
              </label>
              <input
                id="o-train"
                type="number"
                className="input w-24"
                min={1}
                value={trainDays}
                onChange={(e) => setTrainDays(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="o-test" className="label">
                Test (jours)
              </label>
              <input
                id="o-test"
                type="number"
                className="input w-24"
                min={1}
                value={testDays}
                onChange={(e) => setTestDays(Number(e.target.value))}
              />
            </div>
            <button
              className="btn-success"
              disabled={datasetId === "" || job?.status === "en_cours"}
              onClick={() => launch("walkforward")}
            >
              <Play size={15} aria-hidden="true" /> Lancer le walk-forward
            </button>
          </div>
        </div>

        {job && job.status === "en_cours" && (
          <ProgressBar value={job.progress} label="Optimisation en cours" />
        )}
        {job?.status === "erreur" && (
          <p className="text-sm text-red-400" role="alert">
            Erreur : {job.error}
          </p>
        )}
      </section>

      {detail && <OptimizeResults detail={detail} metric={metric} />}

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Optimisations précédentes</h2>
        <DataTable
          columns={jobColumns(openJob)}
          rows={jobs}
          rowKey={(j) => j.id}
          empty="Aucune optimisation pour l'instant."
          maxHeight="18rem"
        />
      </section>
    </div>
  );
}

function jobColumns(onOpen: (id: number) => void): Column<OptimizeJobSummary>[] {
  return [
    { key: "id", header: "N°", render: (j) => j.id },
    {
      key: "kind",
      header: "Type",
      render: (j) => (j.kind === "grid" ? "Grid search" : "Walk-forward"),
    },
    { key: "dataset", header: "Dataset", render: (j) => `n°${j.dataset_id}` },
    { key: "created", header: "Créé le", render: (j) => fmtDateTime(j.created_at) },
    { key: "status", header: "Statut", render: (j) => <StatusBadge status={j.status} /> },
    {
      key: "open",
      header: "",
      render: (j) =>
        j.status === "termine" ? (
          <button className="btn-secondary !py-0.5 text-xs" onClick={() => onOpen(j.id)}>
            Ouvrir
          </button>
        ) : null,
    },
  ];
}

// --------------------------------------------------------------------------- //

function OptimizeResults({ detail, metric }: { detail: OptimizeJobDetail; metric: string }) {
  if (detail.kind === "grid") {
    const results = (detail.results as GridResult[]) ?? [];
    const stability = detail.stability as StabilityReport | undefined;
    return (
      <section className="space-y-4">
        {stability && (
          <div className="card">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 className="text-sm font-semibold text-slate-300">
                Stabilité — grid search n°{detail.id}
              </h2>
              <Badge tone="green">
                Optimum : {Object.entries(stability.optimum.params)
                  .map(([k, v]) => `${k}=${fmtNum(v)}`)
                  .join(", ")}{" "}
                → {fmtNum(stability.optimum.valeur)}
              </Badge>
            </div>
            <StabilityHeatmap stability={stability} />
          </div>
        )}
        <div className="card">
          <h2 className="mb-2 text-sm font-semibold text-slate-300">
            Résultats du grid ({results.length} combinaisons)
          </h2>
          <DataTable
            columns={gridColumns(results, stability?.metrique ?? metric)}
            rows={[...results].sort(
              (a, b) =>
                (Number(b[stability?.metrique ?? metric]) || 0) -
                (Number(a[stability?.metrique ?? metric]) || 0),
            )}
            rowKey={(_r, i) => i}
            dense
            maxHeight="22rem"
          />
        </div>
      </section>
    );
  }

  const report = detail.results as WalkForwardReport | undefined;
  if (!report) return null;
  const agg = report.metriques_agregees_test;
  return (
    <section className="space-y-4">
      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">
          Walk-forward n°{detail.id} — {report.nb_fenetres} fenêtres (paramètres :{" "}
          <span className="font-mono">{report.params_balayes.join(", ")}</span>)
        </h2>
        <DataTable
          columns={wfColumns()}
          rows={report.fenetres}
          rowKey={(_w, i) => i}
          dense
        />
      </div>
      <div className="card">
        <h2 className="mb-2 text-sm font-semibold text-slate-300">
          Métriques agrégées (fenêtres de test uniquement)
        </h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm md:grid-cols-3">
          <Kv k="PnL net" v={fmtMoney(agg.pnl_net)} />
          <Kv k="PnL net (%)" v={fmtPct(agg.pnl_net_pct, 2)} />
          <Kv k="Espérance" v={fmtR(agg.expectancy_r)} />
          <Kv k="Profit factor" v={fmtRatio(agg.profit_factor)} />
          <Kv k="Taux de réussite" v={fmtPct(agg.win_rate_pct, 1)} />
          <Kv k="Sharpe" v={fmtRatio(agg.sharpe)} />
          <Kv k="Drawdown max (%)" v={fmtPct(agg.max_drawdown_pct, 2)} />
          <Kv k="Trades" v={fmtInt(agg.nb_trades)} />
          <Kv k="Exposition" v={fmtPct(agg.exposition_pct, 1)} />
        </div>
      </div>
    </section>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return (
    <p className="flex justify-between gap-3 border-b border-slate-800/60 py-1">
      <span className="text-slate-400">{k}</span>
      <span className="tabular-nums text-slate-200">{v}</span>
    </p>
  );
}

function gridColumns(results: GridResult[], metric: string): Column<GridResult>[] {
  const paramNames = results.length ? Object.keys(results[0].params) : [];
  return [
    ...paramNames.map((p) => ({
      key: p,
      header: <span className="font-mono normal-case">{p}</span>,
      align: "right" as const,
      render: (r: GridResult) => fmtNum(r.params[p]),
    })),
    {
      key: "metric",
      header: <span className="font-mono normal-case">{metric}</span>,
      align: "right",
      render: (r) => <span className="font-semibold">{fmtNum(Number(r[metric]))}</span>,
    },
    {
      key: "nb",
      header: "Trades",
      align: "right",
      render: (r) => fmtInt(Number(r["nb_trades"])),
    },
    {
      key: "pnl",
      header: "PnL net",
      align: "right",
      render: (r) => fmtMoney(Number(r["pnl_net"])),
    },
  ];
}

function wfColumns(): Column<import("../api/types").WalkForwardWindow>[] {
  return [
    {
      key: "fen",
      header: "Fenêtre test",
      render: (w) => `${fmtDate(w.fenetre.test[0])} → ${fmtDate(w.fenetre.test[1])}`,
    },
    {
      key: "params",
      header: "Paramètres retenus",
      render: (w) => (
        <span className="font-mono text-xs">
          {Object.entries(w.params_retenus)
            .map(([k, v]) => `${k}=${fmtNum(v)}`)
            .join(", ")}
        </span>
      ),
    },
    {
      key: "plateau",
      header: "Plateau",
      align: "right",
      render: (w) => (
        <span className="inline-flex items-center gap-1">
          {fmtRatio(w.score_plateau)}
          {w.optimum_isole && (
            <Badge tone="red" title="Optimum isolé sur la fenêtre d'entraînement">
              ⚠
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: "pnl",
      header: "PnL net test",
      align: "right",
      render: (w) => fmtMoney(w.metriques_test.pnl_net),
    },
    {
      key: "exp",
      header: "Espérance test",
      align: "right",
      render: (w) => fmtR(w.metriques_test.expectancy_r),
    },
    {
      key: "pf",
      header: "Profit factor test",
      align: "right",
      render: (w) => fmtRatio(w.metriques_test.profit_factor),
    },
    {
      key: "dd",
      header: "DD max test",
      align: "right",
      render: (w) => fmtPct(w.metriques_test.max_drawdown_pct, 2),
    },
    {
      key: "nb",
      header: "Trades",
      align: "right",
      render: (w) => fmtInt(w.metriques_test.nb_trades),
    },
  ];
}
