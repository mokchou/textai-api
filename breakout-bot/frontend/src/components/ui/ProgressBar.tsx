interface Props {
  /** Progression en pourcentage (0-100). */
  value: number;
  label?: string;
}

export default function ProgressBar({ value, label }: Props) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="w-full">
      {label && (
        <div className="mb-1 flex justify-between text-xs text-slate-400">
          <span>{label}</span>
          <span className="tabular-nums">{pct.toFixed(0)} %</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        className="h-2 w-full overflow-hidden rounded-full bg-slate-800"
      >
        <div
          className="h-full rounded-full bg-sky-500 transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
