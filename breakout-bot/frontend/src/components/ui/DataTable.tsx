import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  empty?: string;
  dense?: boolean;
  maxHeight?: string;
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty = "Aucune donnée.",
  dense = false,
  maxHeight,
}: Props<T>) {
  return (
    <div
      className="overflow-auto rounded-lg border border-slate-800"
      style={maxHeight ? { maxHeight } : undefined}
    >
      <table className="w-full min-w-max text-sm">
        <thead className="sticky top-0 z-10 bg-slate-800/95 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-3 py-2 font-medium ${
                  c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left"
                }`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-slate-500">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={rowKey(row, i)} className="hover:bg-slate-800/40">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 ${dense ? "py-1" : "py-1.5"} tabular-nums ${
                      c.align === "right"
                        ? "text-right"
                        : c.align === "center"
                          ? "text-center"
                          : "text-left"
                    }`}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
