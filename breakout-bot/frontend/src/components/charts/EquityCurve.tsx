import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "../../api/types";
import { fmtDateTime, fmtMoney, fmtPct } from "../../utils/format";

const AXIS = { stroke: "#475569", fontSize: 11 } as const;
const tooltipStyle = {
  backgroundColor: "#0f172a",
  border: "1px solid #334155",
  borderRadius: 8,
  fontSize: 12,
} as const;

function tsTick(ts: number): string {
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" }).format(new Date(ts));
}

/** Courbe d'équité + drawdown : deux AreaCharts synchronisés (syncId). */
export default function EquityCurve({
  data,
  height = 220,
  showDrawdown = true,
}: {
  data: EquityPoint[];
  height?: number;
  showDrawdown?: boolean;
}) {
  if (!data.length) {
    return <p className="py-8 text-center text-sm text-slate-500">Aucune donnée d'équité.</p>;
  }
  return (
    <div className="space-y-1">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} syncId="equity-sync" margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="ts" tickFormatter={tsTick} {...AXIS} minTickGap={48} />
          <YAxis domain={["auto", "auto"]} width={70} {...AXIS} />
          <RTooltip
            contentStyle={tooltipStyle}
            labelFormatter={(v) => fmtDateTime(Number(v))}
            formatter={(v) => [fmtMoney(Number(v)), "Équité"]}
          />
          <Area type="monotone" dataKey="equite" stroke="#10b981" strokeWidth={1.5} fill="url(#eqFill)" name="Équité" />
        </AreaChart>
      </ResponsiveContainer>
      {showDrawdown && (
        <ResponsiveContainer width="100%" height={Math.round(height * 0.55)}>
          <AreaChart data={data} syncId="equity-sync" margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.02} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.35} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="ts" tickFormatter={tsTick} {...AXIS} minTickGap={48} />
            <YAxis width={70} {...AXIS} />
            <RTooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => fmtDateTime(Number(v))}
              formatter={(v) => [fmtPct(Number(v), 2), "Drawdown"]}
            />
            <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={1.5} fill="url(#ddFill)" name="Drawdown" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/** Mini-sparkline d'équité pour le tableau de bord. */
export function EquitySparkline({
  data,
  height = 64,
}: {
  data: { ts: number; equite: number }[];
  height?: number;
}) {
  if (!data.length) {
    return <p className="py-4 text-center text-xs text-slate-500">Aucune donnée d'équité.</p>;
  }
  const positive = data[data.length - 1].equite >= data[0].equite;
  const color = positive ? "#10b981" : "#ef4444";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <YAxis domain={["auto", "auto"]} hide />
        <RTooltip
          contentStyle={tooltipStyle}
          labelFormatter={() => ""}
          formatter={(v) => [fmtMoney(Number(v)), "Équité"]}
        />
        <Area type="monotone" dataKey="equite" stroke={color} strokeWidth={1.5} fill="url(#sparkFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const COMPARE_COLORS = ["#38bdf8", "#10b981", "#f59e0b", "#a78bfa"];

/** Superposition de plusieurs courbes d'équité (comparaison de backtests). */
export function EquityCompare({
  series,
  height = 300,
}: {
  series: { name: string; data: EquityPoint[] }[];
  height?: number;
}) {
  if (!series.length) return null;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="ts"
          type="number"
          domain={["dataMin", "dataMax"]}
          tickFormatter={tsTick}
          {...AXIS}
          minTickGap={48}
          allowDuplicatedCategory={false}
        />
        <YAxis domain={["auto", "auto"]} width={70} {...AXIS} />
        <RTooltip
          contentStyle={tooltipStyle}
          labelFormatter={(v) => fmtDateTime(Number(v))}
          formatter={(v: unknown, name: unknown) => [fmtMoney(Number(v)), String(name)]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Line
            key={s.name}
            data={s.data}
            dataKey="equite"
            name={s.name}
            stroke={COMPARE_COLORS[i % COMPARE_COLORS.length]}
            strokeWidth={1.5}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
