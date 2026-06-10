import type { StabilityReport } from "../../api/types";
import { fmtNum, fmtRatio } from "../../utils/format";
import Badge from "../ui/Badge";

/** Couleur d'une cellule : du sombre (faible) à l'émeraude (élevé). */
function cellColor(v: number | null, min: number, max: number): string {
  if (v == null || !isFinite(v)) return "#1e293b";
  const t = max > min ? (v - min) / (max - min) : 0.5;
  const light = 14 + t * 36; // 14 % → 50 %
  return `hsl(160, ${30 + t * 45}%, ${light}%)`;
}

/** Heatmap de stabilité du grid search : barres en 1D, grille colorée en 2D,
 *  optimum mis en évidence. */
export default function StabilityHeatmap({ stability }: { stability: StabilityReport }) {
  const { parametres, axes, heatmap, optimum } = stability;
  if (!heatmap || !parametres?.length) {
    return <p className="text-sm text-slate-500">Pas de carte de stabilité disponible.</p>;
  }
  if (parametres.length > 2) {
    return (
      <p className="text-sm text-slate-500">
        Carte non affichable au-delà de 2 paramètres ({parametres.length} balayés) — voir le tableau
        des résultats.
      </p>
    );
  }

  const flat = heatmap.flat().filter((v): v is number => v != null && isFinite(v));
  const min = Math.min(...flat);
  const max = Math.max(...flat);

  const warning = stability.optimum_isole && (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="red">⚠ Optimum isolé — risque de sur-optimisation</Badge>
      {stability.avertissement_fr && (
        <span className="text-xs text-red-300">{stability.avertissement_fr}</span>
      )}
    </div>
  );

  // ----------------------------------- 1D ---------------------------------- //
  if (parametres.length === 1) {
    const values = heatmap[0] ?? [];
    const axis = axes[0] ?? [];
    const bestIdx = axis.findIndex((a) => a === optimum.params[parametres[0]]);
    return (
      <div className="space-y-3">
        {warning}
        <div className="flex items-end gap-1" style={{ height: 160 }}>
          {values.map((v, i) => {
            const t = v != null && max > min ? (v - min) / (max - min) : 0.5;
            const isBest = i === bestIdx;
            return (
              <div key={i} className="flex h-full flex-1 flex-col justify-end gap-1 text-center">
                <div
                  title={`${parametres[0]} = ${fmtNum(axis[i])} → ${fmtNum(v)}`}
                  className={`mx-auto w-full rounded-t ${isBest ? "ring-2 ring-amber-400" : ""}`}
                  style={{
                    height: `${8 + t * 85}%`,
                    backgroundColor: cellColor(v, min, max),
                  }}
                />
                <span className={`text-[10px] ${isBest ? "font-bold text-amber-400" : "text-slate-500"}`}>
                  {fmtNum(axis[i])}
                </span>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-slate-400">
          Axe : <span className="font-mono">{parametres[0]}</span> — métrique{" "}
          <span className="font-mono">{stability.metrique}</span> — score de plateau{" "}
          {fmtRatio(stability.score_plateau)}
        </p>
      </div>
    );
  }

  // ----------------------------------- 2D ---------------------------------- //
  const [p0, p1] = parametres;
  const rows = axes[0] ?? [];
  const cols = axes[1] ?? [];
  return (
    <div className="space-y-3">
      {warning}
      <div className="overflow-auto">
        <div
          className="grid w-max gap-1"
          style={{ gridTemplateColumns: `auto repeat(${cols.length}, 3.5rem)` }}
        >
          <div />
          {cols.map((c, j) => (
            <div key={j} className="text-center text-[10px] text-slate-400">
              {fmtNum(c)}
            </div>
          ))}
          {rows.map((r, i) => (
            <FragmentRow
              key={i}
              rowLabel={fmtNum(r)}
              cells={cols.map((c, j) => {
                const v = heatmap[i]?.[j] ?? null;
                const isBest = optimum.params[p0] === r && optimum.params[p1] === c;
                return { v, isBest, title: `${p0}=${fmtNum(r)}, ${p1}=${fmtNum(c)} → ${fmtNum(v)}` };
              })}
              min={min}
              max={max}
            />
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400">
        Lignes : <span className="font-mono">{p0}</span> — colonnes :{" "}
        <span className="font-mono">{p1}</span> — métrique{" "}
        <span className="font-mono">{stability.metrique}</span> — score de plateau{" "}
        {fmtRatio(stability.score_plateau)} — optimum encadré en ambre
      </p>
    </div>
  );
}

function FragmentRow({
  rowLabel,
  cells,
  min,
  max,
}: {
  rowLabel: string;
  cells: { v: number | null; isBest: boolean; title: string }[];
  min: number;
  max: number;
}) {
  return (
    <>
      <div className="pr-2 text-right text-[10px] leading-9 text-slate-400">{rowLabel}</div>
      {cells.map((c, j) => (
        <div
          key={j}
          title={c.title}
          className={`flex h-9 items-center justify-center rounded text-[10px] font-medium text-slate-100 ${
            c.isBest ? "ring-2 ring-amber-400" : ""
          }`}
          style={{ backgroundColor: cellColor(c.v, min, max) }}
        >
          {c.v != null ? c.v.toFixed(2) : "—"}
        </div>
      ))}
    </>
  );
}
