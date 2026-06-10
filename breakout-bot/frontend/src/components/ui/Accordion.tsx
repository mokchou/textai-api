import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface Props {
  title: ReactNode;
  defaultOpen?: boolean;
  badge?: ReactNode;
  children: ReactNode;
}

export default function Accordion({ title, defaultOpen = false, badge, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-200 hover:bg-slate-800/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
      >
        <span className="flex items-center gap-2">
          {title}
          {badge}
        </span>
        <ChevronDown
          size={16}
          className={`shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>
      {open && <div className="border-t border-slate-800 p-4">{children}</div>}
    </div>
  );
}
