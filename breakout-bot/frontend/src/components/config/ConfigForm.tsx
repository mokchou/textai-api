import { useMemo } from "react";
import type { BotConfig, ConfigSchema } from "../../api/types";
import Accordion from "../ui/Accordion";
import ParamField from "./ParamField";

interface Props {
  schema: ConfigSchema;
  config: BotConfig;
  /** Incrémenté à chaque remplacement externe de la config (défauts, import,
   *  preset) pour réinitialiser les champs JSON. */
  version: number;
  /** Erreurs serveur FR au format « groupe.champ : message ». */
  erreurs: string[];
  onFieldChange: (groupKey: string, fieldName: string, value: unknown) => void;
}

/** Formulaire 100 % généré depuis GET /api/config/schema : une section
 *  accordéon par groupe, un champ typé par paramètre. */
export default function ConfigForm({ schema, config, version, erreurs, onFieldChange }: Props) {
  const fieldErrors = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const err of erreurs) {
      const [loc] = err.split(" : ");
      const parts = (loc ?? "").split(".");
      if (parts.length >= 2) {
        const key = `${parts[0]}.${parts[1]}`;
        map.set(key, [...(map.get(key) ?? []), err.slice(loc.length + 3) || err]);
      }
    }
    return map;
  }, [erreurs]);

  return (
    <div className="space-y-3">
      {schema.groups.map((group, gi) => {
        const groupErrorCount = group.fields.reduce(
          (n, f) => n + (fieldErrors.get(`${group.key}.${f.name}`)?.length ?? 0),
          0,
        );
        return (
          <Accordion
            key={group.key}
            title={group.label_fr}
            defaultOpen={gi === 0}
            badge={
              groupErrorCount > 0 ? (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                  {groupErrorCount} erreur{groupErrorCount > 1 ? "s" : ""}
                </span>
              ) : undefined
            }
          >
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {group.fields.map((field) => (
                <ParamField
                  key={`${group.key}.${field.name}.${version}`}
                  field={field}
                  value={config[group.key]?.[field.name]}
                  errors={fieldErrors.get(`${group.key}.${field.name}`) ?? []}
                  onChange={(v) => onFieldChange(group.key, field.name, v)}
                />
              ))}
            </div>
          </Accordion>
        );
      })}
    </div>
  );
}
