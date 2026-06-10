import { useId, useState } from "react";
import type { SchemaField } from "../../api/types";
import Toggle from "../ui/Toggle";
import Tooltip from "../ui/Tooltip";

interface Props {
  field: SchemaField;
  value: unknown;
  onChange: (v: unknown) => void;
  /** Erreurs serveur (FR) associées à ce champ. */
  errors: string[];
}

/** Champ de configuration généré depuis le schéma : label FR, unité, bornes,
 *  info-bulle accessible, validation locale des bornes. */
export default function ParamField({ field, value, onChange, errors }: Props) {
  const inputId = useId();
  const [localError, setLocalError] = useState<string | null>(null);
  const [jsonText, setJsonText] = useState<string>(() =>
    field.type === "json" ? JSON.stringify(value ?? field.default, null, 2) : "",
  );

  const boundsLabel =
    field.min != null && field.max != null
      ? `${field.min} – ${field.max}`
      : field.min != null
        ? `≥ ${field.min}`
        : field.max != null
          ? `≤ ${field.max}`
          : null;

  const checkBounds = (n: number): string | null => {
    if (Number.isNaN(n)) return "Valeur numérique requise.";
    if (field.type === "integer" && !Number.isInteger(n)) return "Nombre entier requis.";
    if (field.min != null && n < field.min) return `Valeur minimale : ${field.min}.`;
    if (field.max != null && n > field.max) return `Valeur maximale : ${field.max}.`;
    return null;
  };

  const allErrors = [...(localError ? [localError] : []), ...errors];

  let control: JSX.Element;
  switch (field.type) {
    case "boolean":
      control = (
        <Toggle checked={Boolean(value)} onChange={(v) => onChange(v)} label={field.label_fr} />
      );
      break;
    case "choice":
      control = (
        <select
          id={inputId}
          className="input"
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          {(field.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
      break;
    case "json":
      control = (
        <textarea
          id={inputId}
          className={`input min-h-24 font-mono text-xs ${allErrors.length ? "border-red-500" : ""}`}
          value={jsonText}
          spellCheck={false}
          onChange={(e) => {
            setJsonText(e.target.value);
            try {
              onChange(JSON.parse(e.target.value));
              setLocalError(null);
            } catch {
              setLocalError("JSON invalide.");
            }
          }}
        />
      );
      break;
    default:
      control = (
        <input
          id={inputId}
          type="number"
          className={`input ${allErrors.length ? "border-red-500" : ""}`}
          value={value == null || value === "" ? "" : String(value)}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={field.type === "integer" ? 1 : "any"}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") {
              setLocalError("Valeur requise.");
              return;
            }
            const n = Number(raw);
            setLocalError(checkBounds(n));
            onChange(n);
          }}
        />
      );
  }

  return (
    <div>
      <label htmlFor={inputId} className="label flex items-center gap-1.5">
        <span>{field.label_fr}</span>
        {field.unit && <span className="text-slate-500">({field.unit})</span>}
        {boundsLabel && <span className="text-slate-600">[{boundsLabel}]</span>}
        {field.tooltip_fr && <Tooltip text={field.tooltip_fr} />}
      </label>
      {control}
      {allErrors.map((e, i) => (
        <p key={i} className="mt-1 text-xs text-red-400" role="alert">
          {e}
        </p>
      ))}
    </div>
  );
}
