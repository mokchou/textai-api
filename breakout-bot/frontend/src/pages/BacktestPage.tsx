import { useCallback, useEffect, useMemo, useState } from "react";
import { Database, Download, Play } from "lucide-react";
import { api } from "../api/client";
import type { BacktestDetail, BacktestSummary, Dataset, Trade } from "../api/types";
import { useJob } from "../api/ws";
import CostWaterfall from "../components/charts/CostWaterfall";
import EquityCurve from "../components/charts/EquityCurve";
import Badge, { StatusBadge } from "../components/ui/Badge";
import DataTable, { type Column } from "../components/ui/DataTable";
import ProgressBar from "../components/ui/ProgressBar";
import { fmtDateTime, fmtMoney, fmtNum, fmtR, pnlClass, shortHash } from "../utils/format";
import { exitReasonFr, METRIC_DEFS, modeFr } from "../utils/metrics";

const DIRECTIONS_FR: Record<string, string> = { long: "Achat (long)", short: "Vente (short)" };

export default function BacktestPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState<number | "">("");
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [detail, setDetail] = useState<BacktestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // construction de dataset
  const [showBuild, setShowBuild] = useState(false);
  const [buildForm, setBuildForm] = useState({ symbol: "BTCUSDT", timeframe: "15m", start: "", end: "" });
  const [buildJobId, setBuildJobId] = useState<string | null>(null);

  // backtest en cours
  const [btJobId, setBtJobId] = useState<string | null>(null);
  const [pendingBtId, setPendingBtId] = useState<number | null>(null);

  const refreshDatasets = useCallback(async () => {
    try {
      const ds = await api.datasets();
      setDatasets(ds);
      setDatasetId((cur) => (cur === "" && ds.length > 0 ? ds[0].id : cur));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement des datasets.");
    }
  }, []);

  const refreshBacktests = useCallback(async () => {
    try {
      setBacktests(await api.backtests());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement des backtests.");
    }
  }, []);

  useEffect(() => {
    void refreshDatasets();
    void refreshBacktests();
  }, [refreshDatasets, refreshBacktests]);

  const buildJob = useJob(buildJobId, (job) => {
    if (job.status === "termine") {
      void refreshDatasets();
      setShowBuild(false);
    }
    setBuildJobId(null);
  });

  const btJob = useJob(btJobId, (job) => {
    void refreshBacktests();
    if (job.status === "termine" && pendingBtId != null) {
      void loadBacktest(pendingBtId);
    }
    setBtJobId(null);
    setPendingBtId(null);
  });

  const loadBacktest = async (id: number) => {
    try {
      setDetail(await api.backtest(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement du backtest.");
    }
  };

  const onBuild = async () => {
    setError(null);
    const start = Date.parse(buildForm.start);
    const end = Date.parse(buildForm.end);
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) {
      setError("Dates de début et de fin invalides.");
      return;
    }
    try {
      const res = await api.datasetBuild({
        symbol: buildForm.symbol.trim().toUpperCase(),
        timeframe: buildForm.timeframe,
        start_ts: start,
        end_ts: end,
      });
      setBuildJobId(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec du lancement de la construction.");
    }
  };

  const onLaunch = async () => {
    if (datasetId === "") return;
    setError(null);
    try {
      const res = await api.backtestLaunch({ dataset_id: datasetId });
      setBtJobId(res.job_id);
      setPendingBtId(res.backtest_id);
      void refreshBacktests();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec du lancement du backtest.");
    }
  };

  const selectedDataset = datasets.find((d) => d.id === datasetId);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-100">Backtest</h1>

      {error && (
        <div className="card border-red-500/40 text-sm text-red-400" role="alert">
          {error}
        </div>
      )}

      {/* ------------------------------ lancement ----------------------------- */}
      <section className="card space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="dataset" className="label">
              Dataset
            </label>
            <select
              id="dataset"
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
          <button className="btn-secondary" onClick={() => setShowBuild((v) => !v)}>
            <Database size={15} aria-hidden="true" /> Construire un dataset
          </button>
          <button
            className="btn-primary"
            onClick={onLaunch}
            disabled={datasetId === "" || btJob?.status === "en_cours"}
          >
            <Play size={15} aria-hidden="true" /> Lancer le backtest
          </button>
        </div>

        {showBuild && (
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-300">Nouveau dataset</h2>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="b-symbol" className="label">
                  Symbole
                </label>
                <input
                  id="b-symbol"
                  className="input w-36"
                  value={buildForm.symbol}
                  onChange={(e) => setBuildForm({ ...buildForm, symbol: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="b-tf" className="label">
                  Unité de temps
                </label>
                <select
                  id="b-tf"
                  className="input w-28"
                  value={buildForm.timeframe}
                  onChange={(e) => setBuildForm({ ...buildForm, timeframe: e.target.value })}
                >
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                </select>
              </div>
              <div>
                <label htmlFor="b-start" className="label">
                  Début
                </label>
                <input
                  id="b-start"
                  type="date"
                  className="input w-40"
                  value={buildForm.start}
                  onChange={(e) => setBuildForm({ ...buildForm, start: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="b-end" className="label">
                  Fin
                </label>
                <input
                  id="b-end"
                  type="date"
                  className="input w-40"
                  value={buildForm.end}
                  onChange={(e) => setBuildForm({ ...buildForm, end: e.target.value })}
                />
              </div>
              <button
                className="btn-primary"
                onClick={onBuild}
                disabled={buildJob?.status === "en_cours"}
              >
                Construire
              </button>
            </div>
            {buildJob && buildJob.status === "en_cours" && (
              <div className="mt-3">
                <ProgressBar value={buildJob.progress} label="Construction du dataset" />
              </div>
            )}
            {buildJob?.status === "erreur" && (
              <p className="mt-2 text-sm text-red-400" role="alert">
                Erreur : {buildJob.error}
              </p>
            )}
          </div>
        )}

        {btJob && btJob.status === "en_cours" && (
          <ProgressBar value={btJob.progress} label="Backtest en cours" />
        )}
        {btJob?.status === "erreur" && (
          <p className="text-sm text-red-400" role="alert">
            Erreur du backtest : {btJob.error}
          </p>
        )}
      </section>

      {/* ------------------------------ résultats ------------------------------ */}
      {detail?.report && (
        <BacktestResults detail={detail} />
      )}

      {/* --------------------------- backtests passés -------------------------- */}
      <section className="card">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Backtests précédents</h2>
        <DataTable
          columns={pastColumns(loadBacktest)}
          rows={backtests}
          rowKey={(b) => b.id}
          empty="Aucun backtest pour l'instant."
          maxHeight="20rem"
        />
      </section>
    </div>
  );
}

function pastColumns(onOpen: (id: number) => void): Column<BacktestSummary>[] {
  return [
    { key: "id", header: "N°", render: (b) => b.id },
    { key: "symbol", header: "Symbole", render: (b) => `${b.symbol ?? "?"} ${b.timeframe ?? ""}` },
    {
      key: "hash",
      header: "Hash dataset",
      render: (b) => (
        <span className="font-mono text-xs text-sky-400" title={b.dataset_hash ?? undefined}>
          {shortHash(b.dataset_hash)}
        </span>
      ),
    },
    { key: "started", header: "Lancé le", render: (b) => fmtDateTime(b.started_at) },
    { key: "status", header: "Statut", render: (b) => <StatusBadge status={b.status} /> },
    {
      key: "open",
      header: "",
      render: (b) =>
        b.status === "termine" ? (
          <button className="btn-secondary !py-0.5 text-xs" onClick={() => onOpen(b.id)}>
            Ouvrir
          </button>
        ) : null,
    },
  ];
}

// --------------------------------------------------------------------------- //

function BacktestResults({ detail }: { detail: BacktestDetail }) {
  const report = detail.report!;
  const [fMode, setFMode] = useState("");
  const [fDirection, setFDirection] = useState("");
  const [fReason, setFReason] = useState("");

  const modes = useMemo(() => [...new Set(report.trades.map((t) => t.mode))], [report.trades]);
  const directions = useMemo(() => [...new Set(report.trades.map((t) => t.direction))], [report.trades]);
  const reasons = useMemo(() => [...new Set(report.trades.map((t) => t.exit_reason))], [report.trades]);

  const trades = report.trades.filter(
    (t) =>
      (!fMode || t.mode === fMode) &&
      (!fDirection || t.direction === fDirection) &&
      (!fReason || t.exit_reason === fReason),
  );

  const tradeColumns: Column<Trade>[] = [
    { key: "entry", header: "Entrée", render: (t) => fmtDateTime(t.entry_ts) },
    { key: "dir", header: "Direction", render: (t) => DIRECTIONS_FR[t.direction] ?? t.direction },
    { key: "mode", header: "Mode", render: (t) => modeFr(t.mode) },
    { key: "pe", header: "Prix entrée", align: "right", render: (t) => fmtNum(t.entry_price) },
    { key: "ps", header: "Prix sortie", align: "right", render: (t) => fmtNum(t.exit_price) },
    { key: "qty", header: "Quantité", align: "right", render: (t) => fmtNum(t.qty) },
    { key: "reason", header: "Motif de sortie", render: (t) => exitReasonFr(t.exit_reason) },
    {
      key: "pnl",
      header: "PnL net",
      align: "right",
      render: (t) => <span className={pnlClass(t.pnl_net)}>{fmtMoney(t.pnl_net)}</span>,
    },
    {
      key: "r",
      header: "R",
      align: "right",
      render: (t) => <span className={pnlClass(t.r_multiple)}>{fmtR(t.r_multiple)}</span>,
    },
    {
      key: "aborted",
      header: "Avorté",
      align: "center",
      render: (t) => (t.aborted ? <Badge tone="amber">oui</Badge> : ""),
    },
  ];

  return (
    <section className="space-y-4">
      <div className="card">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Résultats — backtest n°{detail.id}
          </h2>
          <Badge tone="blue" mono title={report.run_id}>
            run {shortHash(report.run_id)}
          </Badge>
        </div>
        <EquityCurve data={detail.equity ?? []} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 text-sm font-semibold text-slate-300">Métriques</h2>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-800/70">
              {METRIC_DEFS.map((d) => (
                <tr key={d.key}>
                  <td className="py-1 text-slate-400">{d.label}</td>
                  <td className="py-1 text-right tabular-nums text-slate-200">
                    {d.fmt(report.metriques[d.key] as number | null)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2 className="mb-2 text-sm font-semibold text-slate-300">Attribution des coûts</h2>
          <CostWaterfall couts={report.attribution_couts} />
          {report.attribution_couts.edge_fragile && (
            <p className="mt-2 text-xs text-red-400" role="alert">
              {report.attribution_couts.avertissement_fr ??
                "Edge fragile : les coûts pèsent lourdement sur le PnL brut."}
            </p>
          )}
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Trades ({trades.length}/{report.trades.length})
          </h2>
          <div className="flex flex-wrap items-end gap-2">
            <FilterSelect
              id="f-mode"
              label="Mode"
              value={fMode}
              onChange={setFMode}
              options={modes}
              labelFor={modeFr}
            />
            <FilterSelect
              id="f-dir"
              label="Direction"
              value={fDirection}
              onChange={setFDirection}
              options={directions}
              labelFor={(d) => DIRECTIONS_FR[d] ?? d}
            />
            <FilterSelect
              id="f-reason"
              label="Motif de sortie"
              value={fReason}
              onChange={setFReason}
              options={reasons}
              labelFor={exitReasonFr}
            />
            <a className="btn-secondary" href={`/api/backtests/${detail.id}/trades.csv`} download>
              <Download size={15} aria-hidden="true" /> Exporter CSV
            </a>
          </div>
        </div>
        <DataTable
          columns={tradeColumns}
          rows={trades}
          rowKey={(t, i) => `${t.entry_ts}-${i}`}
          empty="Aucun trade ne correspond aux filtres."
          dense
          maxHeight="28rem"
        />
      </div>
    </section>
  );
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
  labelFor = (s) => s,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  labelFor?: (s: string) => string;
}) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <select id={id} className="input w-40" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Tous</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {labelFor(o)}
          </option>
        ))}
      </select>
    </div>
  );
}
