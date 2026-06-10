import type { ReactNode } from "react";

export type BadgeTone = "green" | "red" | "amber" | "blue" | "slate";

const tones: Record<BadgeTone, string> = {
  green: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  red: "bg-red-500/15 text-red-400 border-red-500/30",
  amber: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  blue: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  slate: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

export default function Badge({
  tone = "slate",
  children,
  title,
  mono = false,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  title?: string;
  mono?: boolean;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
        tones[tone]
      } ${mono ? "font-mono" : ""}`}
    >
      {children}
    </span>
  );
}

/** Badge de statut de job / backtest / proposition. */
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { tone: BadgeTone; label: string }> = {
    en_cours: { tone: "blue", label: "En cours" },
    termine: { tone: "green", label: "Terminé" },
    erreur: { tone: "red", label: "Erreur" },
    proposee: { tone: "amber", label: "Proposée" },
    appliquee: { tone: "green", label: "Appliquée" },
    auto_appliquee: { tone: "green", label: "Auto-appliquée" },
    rejetee: { tone: "red", label: "Rejetée" },
  };
  const v = map[status] ?? { tone: "slate" as BadgeTone, label: status };
  return <Badge tone={v.tone}>{v.label}</Badge>;
}
