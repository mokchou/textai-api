import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "positive" | "negative" | "neutral";
  badge?: ReactNode;
}

const toneClass = {
  positive: "text-emerald-400",
  negative: "text-red-400",
  neutral: "text-slate-100",
};

export default function KpiTile({ label, value, sub, tone = "neutral", badge }: Props) {
  return (
    <div className="card flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
        {badge}
      </div>
      <span className={`text-xl font-semibold tabular-nums ${toneClass[tone]}`}>{value}</span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}
