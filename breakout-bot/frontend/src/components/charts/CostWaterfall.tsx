import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AttributionCouts } from "../../api/types";
import { fmtMoney } from "../../utils/format";

interface Step {
  name: string;
  base: number;
  valeur: number;
  reel: number;
  color: string;
}

/** Cascade des coûts : PnL brut → frais → slippage → funding → PnL net. */
export default function CostWaterfall({
  couts,
  height = 220,
}: {
  couts: AttributionCouts;
  height?: number;
}) {
  const steps: Step[] = [];
  let cumul = 0;

  const push = (name: string, delta: number, color: string, isTotal = false) => {
    const start = isTotal ? 0 : cumul;
    const end = isTotal ? delta : cumul + delta;
    steps.push({
      name,
      base: Math.min(start, end),
      valeur: Math.abs(end - start),
      reel: isTotal ? delta : delta,
      color,
    });
    cumul = end;
  };

  push("PnL brut", couts.pnl_brut, couts.pnl_brut >= 0 ? "#10b981" : "#ef4444", true);
  push("Frais", -couts.frais, "#f87171");
  push("Slippage", -couts.slippage, "#fb923c");
  push("Funding", -couts.funding, "#f472b6");
  steps.push({
    name: "PnL net",
    base: Math.min(0, couts.pnl_net),
    valeur: Math.abs(couts.pnl_net),
    reel: couts.pnl_net,
    color: couts.pnl_net >= 0 ? "#10b981" : "#ef4444",
  });

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={steps} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="name" stroke="#475569" fontSize={11} />
        <YAxis width={70} stroke="#475569" fontSize={11} />
        <RTooltip
          contentStyle={{
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderRadius: 8,
            fontSize: 12,
          }}
          cursor={{ fill: "#33415533" }}
          formatter={(_v: unknown, _n: unknown, entry: { payload?: Step }) => [
            fmtMoney(entry.payload?.reel ?? 0),
            entry.payload?.name ?? "",
          ]}
        />
        {/* socle invisible pour l'effet cascade */}
        <Bar dataKey="base" stackId="wf" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="valeur" stackId="wf" isAnimationActive={false}>
          {steps.map((s) => (
            <Cell key={s.name} fill={s.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
