import { useCallback, useEffect, useState } from "react";
import { Check, Play, Save, X } from "lucide-react";
import { api } from "../api/client";
import type { AdaptiveChange, AdaptiveSettings } from "../api/types";
import { useJob, useWebSocket } from "../api/ws";
import Badge, { StatusBadge } from "../components/ui/Badge";
import ProgressBar from "../components/ui/ProgressBar";
import Toggle from "../components/ui/Toggle";
import { fmtDateTime, fmtNum, fmtRatio } from "../utils/format";
import { OPTIMIZE_METRICS } from "../utils/metrics";

const DAYS_FR: { value: string; label: string }[] = [
  { value: "mon", label: "Lundi" },
  { value: "tue", label: "Mardi" },
  { value: "wed", label: "Mercredi" },
  { value: "thu", label: "Jeudi" },
  { value: "fri", label: "Vendredi" },
  { value: "sat", label: "Samedi" },
  { value: "sun", label: "Dimanche" },
];

export default function AdaptivePage() {
  const [settings, setSettings] = useState<AdaptiveSettings | null>(null);
  const [history, setHistory] = useState<AdaptiveChange[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await api.adaptiveHistory());
    } catch {
      /* non bloquant */
    }
  }, []);

  useEffect(() => {
    api
      .adaptiveSettings()
      .then(setSettings)
      .catch((e) =>
        setFlash({ kind: "err", text: e instanceof Error ? e.message : "Réglages indisponibles." }),
      );
    void refreshHistory();
  }, [refreshHistory]);

  useWebSocket("adaptive:events", () => {
    void refreshHistory();
  });

  const job = useJob(jobId, (j) => {
    setJobId(null);
    void refreshHistory();
    if (j.status === "erreur") {
      setFlash({ kind: "err", text: `Cycle adaptatif en erreur : ${j.error}` });
    } else {
      setFlash({ kind: "ok", text: "Cycle adaptatif terminé." });
    }
  });

  const onSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await api.adaptiveSettingsSave(settings);
      setFlash({ kind: "ok", text: "Réglages d'adaptation enregistrés." });
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Échec de l'enregistrement." });
    } finally {
      setSaving(false);
    }
  };

  const onRunNow = async () => {
    try {
      const res = await api.adaptiveRunNow();
      setJobId(res.job_id);
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Échec du lancement." });
    }
  };

  const onDecision = async (changeId: number, approve: boolean) => {
    try {
      if (approve) await api.adaptiveApprove(changeId);
      else await api.adaptiveReject(changeId);
      setFlash({ kind: "ok", text: approve ? "Proposition approuvée et appliquée." : "Proposition rejetée." });
      void refreshHistory();
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Action impossible." });
    }
  };

  const proposals = history.filter((h) => h.status === "proposee");

  const set = <K extends keyof AdaptiveSettings>(key: K, value: AdaptiveSettings[K]) =>
    setSettings((s) => (s ? { ...s, [key]: value } : s));

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-100">Ré-optimisation adaptative</h1>
        <button className="btn-primary" onClick={onRunNow} disabled={job?.status === "en_cours"}>
          <Play size={15} aria-hidden="true" /> Lancer maintenant
        </button>
      </header>

      {flash && (
        <div
          role="status"
          className={`card text-sm ${
            flash.kind === "ok" ? "border-emerald-500/40 text-emerald-300" : "border-red-500/40 text-red-300"
          }`}
        >
          {flash.text}
        </div>
      )}

      {job && job.status === "en_cours" && (
        <div className="card">
          <ProgressBar value={job.progress} label="Cycle adaptatif en cours (données → walk-forward → garde-fous)" />
        </div>
      )}

      {/* ------------------------------- réglages ------------------------------ */}
      {settings && (
        <section className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-300">Réglages</h2>
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <Toggle checked={settings.enabled} onChange={(v) => set("enabled", v)} label="Activation" />
              Adaptation activée
            </label>
            <div>
              <label htmlFor="a-mode" className="label">
                Mode de gouvernance
              </label>
              <select
                id="a-mode"
                className="input w-56"
                value={settings.mode}
                onChange={(e) => set("mode", e.target.value as AdaptiveSettings["mode"])}
              >
                <option value="approbation_manuelle">Approbation manuelle</option>
                <option value="auto">Automatique</option>
              </select>
            </div>
            <div>
              <label htmlFor="a-day" className="label">
                Jour (hebdomadaire, UTC)
              </label>
              <select
                id="a-day"
                className="input w-40"
                value={settings.cron_day_of_week}
                onChange={(e) => set("cron_day_of_week", e.target.value)}
              >
                {DAYS_FR.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>
            <NumField id="a-hour" label="Heure UTC" value={settings.cron_hour_utc} min={0} max={23} onChange={(v) => set("cron_hour_utc", v)} />
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <NumField id="a-lookback" label="Fenêtre de données (jours)" value={settings.lookback_days} min={1} onChange={(v) => set("lookback_days", v)} />
            <NumField id="a-train" label="Train (jours)" value={settings.train_days} min={1} onChange={(v) => set("train_days", v)} />
            <NumField id="a-test" label="Test (jours)" value={settings.test_days} min={1} onChange={(v) => set("test_days", v)} />
            <NumField id="a-points" label="Points par paramètre" value={settings.grid_points} min={2} onChange={(v) => set("grid_points", v)} />
            <div>
              <label htmlFor="a-metric" className="label">
                Métrique objectif
              </label>
              <select
                id="a-metric"
                className="input w-48"
                value={settings.metric}
                onChange={(e) => set("metric", e.target.value)}
              >
                {OPTIMIZE_METRICS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="a-params" className="label">
              Paramètres adaptables (un chemin par ligne, 3 max balayés)
            </label>
            <textarea
              id="a-params"
              className="input min-h-20 max-w-xl font-mono text-xs"
              value={settings.adaptive_params.join("\n")}
              spellCheck={false}
              onChange={(e) =>
                set(
                  "adaptive_params",
                  e.target.value
                    .split("\n")
                    .map((l) => l.trim())
                    .filter(Boolean),
                )
              }
            />
          </div>

          <div>
            <p className="label">Garde-fous</p>
            <div className="flex flex-wrap items-end gap-4">
              <NumField id="g-plateau" label="Score de plateau min" value={settings.min_plateau_score} step={0.05} onChange={(v) => set("min_plateau_score", v)} />
              <NumField id="g-pf" label="Profit factor test min" value={settings.min_profit_factor_test} step={0.05} onChange={(v) => set("min_profit_factor_test", v)} />
              <NumField id="g-dd" label="Drawdown test max (%)" value={settings.max_drawdown_test_pct} step={0.5} onChange={(v) => set("max_drawdown_test_pct", v)} />
              <NumField id="g-delta" label="Variation de paramètre max (%)" value={settings.max_param_delta_pct} step={1} onChange={(v) => set("max_param_delta_pct", v)} />
            </div>
          </div>

          <button className="btn-primary" onClick={onSave} disabled={saving}>
            <Save size={15} aria-hidden="true" /> {saving ? "Enregistrement…" : "Enregistrer les réglages"}
          </button>
        </section>
      )}

      {/* ---------------------------- propositions ----------------------------- */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-300">
          Propositions en attente ({proposals.length})
        </h2>
        {proposals.length === 0 && (
          <p className="card text-sm text-slate-500">Aucune proposition en attente d'approbation.</p>
        )}
        {proposals.map((p) => (
          <div key={p.id} className="card space-y-3 border-amber-500/40">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <StatusBadge status={p.status} />
                <span className="text-sm text-slate-300">
                  Proposition n°{p.id} — {fmtDateTime(p.ts)} (déclencheur : {p.trigger_kind})
                </span>
                {p.stability_score != null && (
                  <Badge tone="blue">stabilité {fmtRatio(p.stability_score)}</Badge>
                )}
              </div>
              <div className="flex gap-2">
                <button className="btn-success !py-1 text-xs" onClick={() => onDecision(p.id, true)}>
                  <Check size={13} aria-hidden="true" /> Approuver
                </button>
                <button className="btn-danger !py-1 text-xs" onClick={() => onDecision(p.id, false)}>
                  <X size={13} aria-hidden="true" /> Rejeter
                </button>
              </div>
            </div>
            <DiffTable diff={p.diff} />
            {p.guardrail_report && <GuardrailBlock report={p.guardrail_report} />}
          </div>
        ))}
      </section>

      {/* ------------------------------ historique ------------------------------ */}
      <section className="card space-y-3">
        <h2 className="text-sm font-semibold text-slate-300">Historique des changements</h2>
        {history.length === 0 && <p className="text-sm text-slate-500">Aucun changement journalisé.</p>}
        <ol className="space-y-3">
          {history.map((h) => (
            <li key={h.id} className="flex gap-3">
              <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-sky-500" aria-hidden="true" />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-slate-400">{fmtDateTime(h.ts)}</span>
                  <StatusBadge status={h.status} />
                  <span className="text-xs text-slate-500">déclencheur : {h.trigger_kind}</span>
                  {h.stability_score != null && (
                    <span className="text-xs text-slate-500">stabilité {fmtRatio(h.stability_score)}</span>
                  )}
                </div>
                {h.diff && Object.keys(h.diff).length > 0 && (
                  <p className="truncate font-mono text-xs text-slate-400">
                    {Object.entries(h.diff)
                      .map(([path, d]) => `${path} : ${fmtAny(d.avant)} → ${fmtAny(d.apres)}`)
                      .join(" ; ")}
                  </p>
                )}
                {h.guardrail_report && h.guardrail_report.reasons_fr?.length > 0 && (
                  <ul className="list-inside list-disc text-xs text-amber-300">
                    {h.guardrail_report.reasons_fr.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function fmtAny(v: unknown): string {
  if (typeof v === "number") return fmtNum(v);
  return String(v);
}

function NumField({
  id,
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <input
        id={id}
        type="number"
        className="input w-32"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function DiffTable({ diff }: { diff: Record<string, { avant: unknown; apres: unknown }> }) {
  const entries = Object.entries(diff ?? {});
  if (entries.length === 0) return <p className="text-xs text-slate-500">Aucun changement.</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs uppercase tracking-wide text-slate-400">
          <th className="py-1 text-left font-medium">Paramètre</th>
          <th className="py-1 text-right font-medium">Avant</th>
          <th className="py-1 text-right font-medium">Après</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800/70">
        {entries.map(([path, d]) => (
          <tr key={path}>
            <td className="py-1 font-mono text-xs text-slate-300">{path}</td>
            <td className="py-1 text-right tabular-nums text-slate-400">{fmtAny(d.avant)}</td>
            <td className="py-1 text-right tabular-nums font-semibold text-sky-400">{fmtAny(d.apres)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function GuardrailBlock({ report }: { report: { passed: boolean; reasons_fr: string[] } }) {
  return (
    <div className="text-xs">
      <p className="mb-1 flex items-center gap-2 font-semibold text-slate-300">
        Garde-fous :
        <Badge tone={report.passed ? "green" : "red"}>
          {report.passed ? "validés" : "non validés"}
        </Badge>
      </p>
      {report.reasons_fr?.length > 0 && (
        <ul className="list-inside list-disc space-y-0.5 text-amber-300">
          {report.reasons_fr.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
