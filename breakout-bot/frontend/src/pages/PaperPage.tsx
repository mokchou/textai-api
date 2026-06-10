import { useCallback, useEffect, useState } from "react";
import { AlertOctagon, FileCheck2, Play, Square } from "lucide-react";
import { api } from "../api/client";
import type { CoherenceReport, JournalEntry, PaperSnapshot } from "../api/types";
import { useWebSocket } from "../api/ws";
import Badge from "../components/ui/Badge";
import DataTable, { type Column } from "../components/ui/DataTable";
import { fmtDateTime, fmtMoney, fmtNum, fmtPct, pnlClass } from "../utils/format";
import { etatFr, exitReasonFr, modeFr } from "../utils/metrics";

const DIRECTIONS_FR: Record<string, string> = { long: "Achat (long)", short: "Vente (short)" };

export default function PaperPage() {
  const [sessions, setSessions] = useState<PaperSnapshot[]>([]);
  const [symbol, setSymbol] = useState("");
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [journalSession, setJournalSession] = useState<number | "">("");
  const [coherence, setCoherence] = useState<{ sessionId: number; report: CoherenceReport } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshState = useCallback(async () => {
    try {
      const st = await api.paperState();
      setSessions(st.sessions);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "État du paper trading indisponible.");
    }
  }, []);

  const refreshJournal = useCallback(async (sessionId: number | "") => {
    try {
      setJournal(await api.paperJournal(sessionId === "" ? undefined : sessionId, 200));
    } catch {
      /* journal indisponible : non bloquant */
    }
  }, []);

  useEffect(() => {
    void refreshState();
    void refreshJournal("");
  }, [refreshState, refreshJournal]);

  useWebSocket("paper:state", (payload) => {
    const snap = payload as unknown as PaperSnapshot;
    if (typeof snap.session_id !== "number") return;
    setSessions((cur) => {
      const idx = cur.findIndex((s) => s.session_id === snap.session_id);
      if (idx === -1) return [...cur, snap];
      const next = [...cur];
      next[idx] = snap;
      return next;
    });
  });

  useWebSocket("paper:journal", (payload) => {
    const entry = payload as unknown as JournalEntry;
    if (!entry?.evaluation) return;
    setJournal((cur) =>
      journalSession === "" || entry.session_id === journalSession
        ? [entry, ...cur].slice(0, 200)
        : cur,
    );
  });

  useWebSocket("paper:trade", () => {
    void refreshState();
  });

  const onStart = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.paperStart(symbol.trim() || undefined);
      await refreshState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec du démarrage de la session.");
    } finally {
      setBusy(false);
    }
  };

  const onStop = async (sessionId: number) => {
    setBusy(true);
    try {
      await api.paperStop(sessionId);
      setSessions((cur) => cur.filter((s) => s.session_id !== sessionId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de l'arrêt.");
    } finally {
      setBusy(false);
    }
  };

  const onResetKill = async (sessionId: number) => {
    try {
      await api.paperKillSwitchReset(sessionId);
      await refreshState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de la reprise manuelle.");
    }
  };

  const onCoherence = async (sessionId: number) => {
    setBusy(true);
    setError(null);
    try {
      setCoherence({ sessionId, report: await api.paperCoherence(sessionId) });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rapport de cohérence indisponible.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-100">Paper trading</h1>

      {error && (
        <div className="card border-red-500/40 text-sm text-red-400" role="alert">
          {error}
        </div>
      )}

      {/* bandeau kill switch */}
      {sessions
        .filter((s) => s.kill_switch)
        .map((s) => (
          <div
            key={s.session_id}
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/60 bg-red-950/60 p-4"
          >
            <p className="flex items-center gap-2 text-sm font-semibold text-red-300">
              <AlertOctagon size={18} aria-hidden="true" />
              Kill switch déclenché — session n°{s.session_id} ({s.symbol}) :{" "}
              {s.kill_raison ?? "raison inconnue"}
            </p>
            <button className="btn-danger" onClick={() => onResetKill(s.session_id)}>
              Reprise manuelle
            </button>
          </div>
        ))}

      <section className="card flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="p-symbol" className="label">
            Symbole (optionnel — défaut : config active)
          </label>
          <input
            id="p-symbol"
            className="input w-44"
            placeholder="ex. BTCUSDT"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </div>
        <button className="btn-success" onClick={onStart} disabled={busy}>
          <Play size={15} aria-hidden="true" /> Démarrer une session
        </button>
      </section>

      {/* cartes de sessions */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sessions.length === 0 && (
          <p className="card text-sm text-slate-400">Aucune session paper active.</p>
        )}
        {sessions.map((s) => (
          <SessionCard
            key={s.session_id}
            s={s}
            busy={busy}
            onStop={onStop}
            onCoherence={onCoherence}
          />
        ))}
      </section>

      {coherence && <CoherencePanel data={coherence} onClose={() => setCoherence(null)} />}

      {/* journal de décisions */}
      <section className="card space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-sm font-semibold text-slate-300">Journal de décisions (live)</h2>
          <div>
            <label htmlFor="j-session" className="label">
              Session
            </label>
            <select
              id="j-session"
              className="input w-44"
              value={journalSession}
              onChange={(e) => {
                const v = e.target.value === "" ? "" : Number(e.target.value);
                setJournalSession(v);
                void refreshJournal(v);
              }}
            >
              <option value="">Toutes</option>
              {sessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  n°{s.session_id} — {s.symbol}
                </option>
              ))}
            </select>
          </div>
        </div>
        <DataTable
          columns={journalColumns()}
          rows={journal}
          rowKey={(j, i) => `${j.ts}-${i}`}
          empty="Aucune évaluation journalisée."
          dense
          maxHeight="24rem"
        />
      </section>
    </div>
  );
}

function SessionCard({
  s,
  busy,
  onStop,
  onCoherence,
}: {
  s: PaperSnapshot;
  busy: boolean;
  onStop: (id: number) => void;
  onCoherence: (id: number) => void;
}) {
  return (
    <div className={`card space-y-3 ${s.kill_switch ? "border-red-500/60" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-100">
          Session n°{s.session_id} — {s.symbol}
        </h2>
        <div className="flex items-center gap-2">
          <Badge tone={s.kill_switch ? "red" : "green"}>{etatFr(s.etat)}</Badge>
          <button className="btn-secondary !py-1 text-xs" onClick={() => onCoherence(s.session_id)} disabled={busy}>
            <FileCheck2 size={13} aria-hidden="true" /> Cohérence
          </button>
          <button className="btn-danger !py-1 text-xs" onClick={() => onStop(s.session_id)} disabled={busy}>
            <Square size={13} aria-hidden="true" /> Arrêter
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-xs text-slate-500">Équité</p>
          <p className="font-semibold tabular-nums text-slate-100">{fmtMoney(s.equite)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Trades</p>
          <p className="font-semibold tabular-nums text-slate-100">{s.nb_trades}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Pertes consécutives</p>
          <p className="font-semibold tabular-nums text-slate-100">{s.pertes_consecutives}</p>
        </div>
      </div>

      {s.position ? (
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm">
          <p className="mb-2 flex items-center gap-2 font-medium text-slate-200">
            Position {DIRECTIONS_FR[s.position.direction] ?? s.position.direction} —{" "}
            {modeFr(s.position.mode)}
            {s.position.trailing_actif && <Badge tone="blue">stop suiveur</Badge>}
            {!s.position.confirme && <Badge tone="amber">non confirmée</Badge>}
          </p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-3">
            <Kv k="Quantité" v={fmtNum(s.position.qty)} />
            <Kv k="Prix d'entrée" v={fmtNum(s.position.prix_entree)} />
            <Kv k="Stop courant" v={fmtNum(s.position.stop_courant)} />
            <Kv
              k="PnL latent"
              v={<span className={pnlClass(s.position.pnl_latent)}>{fmtMoney(s.position.pnl_latent)}</span>}
            />
            <Kv k="Funding cumulé" v={fmtMoney(s.position.funding_cumule)} />
          </div>
        </div>
      ) : (
        <p className="text-xs text-slate-500">Aucune position ouverte.</p>
      )}

      {s.ordres_en_attente.length > 0 && (
        <div className="text-xs">
          <p className="mb-1 text-slate-500">Ordres en attente :</p>
          <ul className="space-y-1">
            {s.ordres_en_attente.map((o, i) => (
              <li key={i} className="flex items-center gap-2 text-slate-300">
                <Badge tone={o.direction === "long" ? "green" : "red"}>
                  {DIRECTIONS_FR[o.direction] ?? o.direction}
                </Badge>
                {modeFr(o.mode)} @ {fmtNum(o.prix)}
                {o.suspendu && <Badge tone="amber">suspendu</Badge>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Kv({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <p className="flex justify-between gap-2">
      <span className="text-slate-500">{k}</span>
      <span className="tabular-nums text-slate-200">{v}</span>
    </p>
  );
}

function journalColumns(): Column<JournalEntry>[] {
  return [
    { key: "ts", header: "Horodatage", render: (j) => fmtDateTime(j.ts) },
    { key: "session", header: "Session", render: (j) => `n°${j.session_id}` },
    { key: "symbol", header: "Symbole", render: (j) => j.symbol },
    { key: "state", header: "État", render: (j) => <Badge tone="slate">{etatFr(j.state)}</Badge> },
    {
      key: "decision",
      header: "Décision",
      render: (j) =>
        j.has_decision ? (
          <Badge tone="green">
            {j.evaluation.decisions?.map((d) => d.action).join(", ") || "oui"}
          </Badge>
        ) : (
          <Badge tone="slate">refusé</Badge>
        ),
    },
    {
      key: "reasons",
      header: "Motifs (FR)",
      render: (j) => (
        <span className="block max-w-xl whitespace-normal text-xs text-slate-400">
          {j.evaluation.reasons_fr?.join(" ; ") || "—"}
        </span>
      ),
    },
  ];
}

function CoherencePanel({
  data,
  onClose,
}: {
  data: { sessionId: number; report: CoherenceReport };
  onClose: () => void;
}) {
  const r = data.report;
  return (
    <section
      className={`card space-y-3 ${r.objectif_atteint ? "border-emerald-500/50" : "border-amber-500/50"}`}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">
          Rapport de cohérence backtest / paper — session n°{data.sessionId}
        </h2>
        <button className="btn-secondary !py-1 text-xs" onClick={onClose}>
          Fermer
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-2xl font-bold tabular-nums text-slate-100">
          {fmtPct(r.pct_identiques, 1)}
        </span>
        <span className="text-sm text-slate-400">
          de trades identiques (objectif ≥ {fmtPct(r.seuil_pct, 1)})
        </span>
        <Badge tone={r.objectif_atteint ? "green" : "red"}>
          {r.objectif_atteint ? "Objectif atteint" : "Objectif non atteint"}
        </Badge>
      </div>
      <p className="text-xs text-slate-400">
        {r.nb_trades_paper} trades paper, {r.nb_trades_backtest} trades backtest,{" "}
        {r.nb_apparies} appariés, {r.nb_identiques} identiques.
      </p>
      {r.causes_ecarts_fr.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold text-slate-300">Causes des écarts :</p>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-amber-300">
            {r.causes_ecarts_fr.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {r.appariements.length > 0 && (
        <DataTable
          columns={[
            { key: "ts", header: "Entrée", render: (m) => fmtDateTime(m.entry_ts) },
            { key: "dir", header: "Direction", render: (m) => DIRECTIONS_FR[m.direction] ?? m.direction },
            {
              key: "id",
              header: "Identique",
              render: (m) =>
                m.identique ? <Badge tone="green">oui</Badge> : <Badge tone="red">non</Badge>,
            },
            {
              key: "ecart",
              header: "Écart prix entrée",
              align: "right",
              render: (m) => fmtPct(m.ecart_prix_entree_pct, 2),
            },
            {
              key: "pnlp",
              header: "PnL paper",
              align: "right",
              render: (m) => <span className={pnlClass(m.pnl_paper)}>{fmtMoney(m.pnl_paper)}</span>,
            },
            {
              key: "pnlb",
              header: "PnL backtest",
              align: "right",
              render: (m) => <span className={pnlClass(m.pnl_backtest)}>{fmtMoney(m.pnl_backtest)}</span>,
            },
            {
              key: "motifs",
              header: "Motifs sortie (paper / backtest)",
              render: (m) =>
                `${exitReasonFr(m.motif_sortie_paper)} / ${exitReasonFr(m.motif_sortie_backtest)}`,
            },
          ]}
          rows={r.appariements}
          rowKey={(m, i) => `${m.entry_ts}-${i}`}
          dense
          maxHeight="16rem"
        />
      )}
    </section>
  );
}
