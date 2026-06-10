import { useCallback, useEffect, useRef, useState } from "react";
import { Download, RotateCcw, Save, Upload } from "lucide-react";
import { api } from "../api/client";
import type { BotConfig, ConfigSchema, PresetSummary } from "../api/types";
import ConfigForm from "../components/config/ConfigForm";
import Badge from "../components/ui/Badge";
import { shortHash } from "../utils/format";

export default function ConfigurationPage() {
  const [schema, setSchema] = useState<ConfigSchema | null>(null);
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [configHash, setConfigHash] = useState<string>("");
  const [version, setVersion] = useState(0);
  const [erreurs, setErreurs] = useState<string[]>([]);
  const [valide, setValide] = useState<boolean | null>(null);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [presetName, setPresetName] = useState("");
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<number>();

  const loadPresets = useCallback(async () => {
    try {
      setPresets(await api.presets());
    } catch {
      /* présets indisponibles : non bloquant */
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [s, active] = await Promise.all([api.configSchema(), api.configActive()]);
        setSchema(s);
        setConfig(active.config);
        setConfigHash(active.config_hash);
      } catch (e) {
        setFlash({ kind: "err", text: e instanceof Error ? e.message : "Erreur de chargement." });
      }
      void loadPresets();
    })();
  }, [loadPresets]);

  /** Validation distante avec anti-rebond (600 ms). */
  const scheduleValidate = useCallback((cfg: BotConfig) => {
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await api.configValidate(cfg);
        setValide(res.valide);
        setErreurs(res.erreurs_fr);
      } catch (e) {
        setValide(false);
        setErreurs([e instanceof Error ? e.message : "Validation impossible."]);
      }
    }, 600);
  }, []);

  const replaceConfig = (cfg: BotConfig) => {
    setConfig(cfg);
    setVersion((v) => v + 1);
    scheduleValidate(cfg);
  };

  const onFieldChange = (groupKey: string, fieldName: string, value: unknown) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const next = { ...prev, [groupKey]: { ...prev[groupKey], [fieldName]: value } };
      scheduleValidate(next);
      return next;
    });
  };

  const onDefaults = async () => {
    try {
      replaceConfig(await api.configDefaults());
      setFlash({ kind: "ok", text: "Valeurs par défaut chargées (non enregistrées)." });
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Erreur." });
    }
  };

  const onSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await api.configSave(config);
      setConfigHash(res.config_hash);
      setErreurs([]);
      setValide(true);
      setFlash({ kind: "ok", text: `Configuration enregistrée (hash ${shortHash(res.config_hash)}).` });
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Échec de l'enregistrement." });
    } finally {
      setSaving(false);
    }
  };

  const onExport = () => {
    if (!config) return;
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "config-breakout-bot.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const onImportFile = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as BotConfig;
      replaceConfig(parsed);
      setFlash({ kind: "ok", text: `Fichier « ${file.name} » importé (non enregistré).` });
    } catch {
      setFlash({ kind: "err", text: "Fichier JSON invalide." });
    }
  };

  const onSavePreset = async () => {
    if (!config) return;
    const name = presetName.trim() || `préréglage ${new Date().toLocaleString("fr-FR")}`;
    try {
      await api.presetSave(name, config);
      setPresetName("");
      setFlash({ kind: "ok", text: `Préréglage « ${name} » enregistré.` });
      void loadPresets();
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Échec de l'enregistrement du préréglage." });
    }
  };

  const onLoadPreset = async (id: number) => {
    try {
      const p = await api.preset(id);
      replaceConfig(p.config);
      setFlash({ kind: "ok", text: `Préréglage « ${p.name} » chargé (non enregistré).` });
    } catch (e) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Échec du chargement du préréglage." });
    }
  };

  if (!schema || !config) {
    return <p className="text-sm text-slate-400">Chargement de la configuration…</p>;
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-100">Configuration</h1>
          <Badge tone="blue" mono title="Hash de la configuration active">
            {shortHash(configHash)}
          </Badge>
          {valide === true && <Badge tone="green">Valide</Badge>}
          {valide === false && <Badge tone="red">{erreurs.length} erreur{erreurs.length > 1 ? "s" : ""}</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-secondary" onClick={onDefaults}>
            <RotateCcw size={15} aria-hidden="true" /> Valeurs par défaut
          </button>
          <button className="btn-secondary" onClick={onExport}>
            <Download size={15} aria-hidden="true" /> Exporter JSON
          </button>
          <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
            <Upload size={15} aria-hidden="true" /> Importer JSON
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            aria-label="Importer un fichier JSON de configuration"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImportFile(f);
              e.target.value = "";
            }}
          />
          <button className="btn-primary" onClick={onSave} disabled={saving || valide === false}>
            <Save size={15} aria-hidden="true" /> {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </header>

      {flash && (
        <div
          role="status"
          className={`card text-sm ${
            flash.kind === "ok" ? "border-emerald-500/40 text-emerald-300" : "border-red-500/40 text-red-300"
          }`}
        >
          {flash.text}
        </div>
      )}

      {erreurs.length > 0 && (
        <div className="card border-red-500/40" role="alert">
          <p className="mb-1 text-sm font-semibold text-red-400">Erreurs de validation :</p>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-red-300">
            {erreurs.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="card flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="preset-name" className="label">
            Nom du préréglage
          </label>
          <input
            id="preset-name"
            className="input w-56"
            placeholder="ex. agressif BTC 15m"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
          />
        </div>
        <button className="btn-secondary" onClick={onSavePreset}>
          <Save size={15} aria-hidden="true" /> Sauvegarder le préréglage
        </button>
        <div>
          <label htmlFor="preset-load" className="label">
            Charger un préréglage
          </label>
          <select
            id="preset-load"
            className="input w-64"
            value=""
            onChange={(e) => {
              if (e.target.value) void onLoadPreset(Number(e.target.value));
            }}
          >
            <option value="">— choisir —</option>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({shortHash(p.config_hash, 8)})
              </option>
            ))}
          </select>
        </div>
      </section>

      <ConfigForm
        schema={schema}
        config={config}
        version={version}
        erreurs={erreurs}
        onFieldChange={onFieldChange}
      />
    </div>
  );
}
