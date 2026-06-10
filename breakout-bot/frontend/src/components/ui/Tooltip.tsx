import { useId, useState } from "react";
import { Info } from "lucide-react";

/** Info-bulle accessible : bouton focusable, aria-describedby, affichage au
 *  survol et au focus clavier. */
export default function Tooltip({ text }: { text: string }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Informations"
        aria-describedby={visible ? id : undefined}
        className="rounded-full text-slate-500 hover:text-sky-400 focus:text-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/60"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setVisible(false);
        }}
      >
        <Info size={14} aria-hidden="true" />
      </button>
      {visible && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-800 p-2 text-xs leading-snug text-slate-200 shadow-xl"
        >
          {text}
        </span>
      )}
    </span>
  );
}
