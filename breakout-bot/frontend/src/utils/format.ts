const nf2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const nfAuto = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 4 });

/** Montant (€ / USDT) à 2 décimales, format fr-FR. */
export function fmtMoney(v: number | null | undefined, suffix = " €"): string {
  if (v == null || !isFinite(v)) return "—";
  return nf2.format(v) + suffix;
}

/** Pourcentage à 1-2 décimales. */
export function fmtPct(v: number | null | undefined, digits: 1 | 2 = 1): string {
  if (v == null || !isFinite(v)) return "—";
  return (digits === 1 ? nf1 : nf2).format(v) + " %";
}

/** Nombre générique (jusqu'à 4 décimales). */
export function fmtNum(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return nfAuto.format(v);
}

/** Nombre à 2 décimales (ratios : Sharpe, profit factor…). */
export function fmtRatio(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return nf2.format(v);
}

/** Multiple de R à 2 décimales. */
export function fmtR(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return nf2.format(v) + " R";
}

export function fmtInt(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return nf0.format(v);
}

/** Date + heure courte fr-FR depuis un timestamp en millisecondes. */
export function fmtDateTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(
    new Date(ts),
  );
}

/** Date seule fr-FR depuis un timestamp en millisecondes. */
export function fmtDate(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short" }).format(new Date(ts));
}

/** Hash tronqué pour affichage (badge). */
export function shortHash(h: string | null | undefined, n = 10): string {
  if (!h) return "—";
  return h.length > n ? h.slice(0, n) + "…" : h;
}

/** Classe Tailwind selon le signe d'un PnL. */
export function pnlClass(v: number | null | undefined): string {
  if (v == null || !isFinite(v) || v === 0) return "text-slate-300";
  return v > 0 ? "text-emerald-400" : "text-red-400";
}
