import { Fragment, useState } from "react";
import PriorityBadge from "./PriorityBadge";
import CategoryBadge from "./CategoryBadge";

const PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 };

export default function BatchResultsTable({ batchResponse }) {
  const [sortByPriority, setSortByPriority] = useState(false);
  const [filterNeedsHuman, setFilterNeedsHuman] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  if (!batchResponse) return null;

  let rows = [...batchResponse.results];
  if (filterNeedsHuman) {
    rows = rows.filter((r) => r.result?.needs_human);
  }
  if (sortByPriority) {
    rows.sort((a, b) => {
      const pa = PRIORITY_ORDER[a.result?.priority] ?? 99;
      const pb = PRIORITY_ORDER[b.result?.priority] ?? 99;
      return pa - pb;
    });
  }

  return (
    <div className="mt-6 space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <Stat label="Total" value={batchResponse.total} />
        <Stat label="Succeeded" value={batchResponse.succeeded} tone="text-green-700" />
        <Stat label="Failed" value={batchResponse.failed} tone="text-red-700" />
        <Stat label="Needs Human" value={batchResponse.needs_human_count} tone="text-rose-700" />
        <Stat label="Avg latency" value={`${batchResponse.avg_latency_ms} ms`} />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={sortByPriority}
            onChange={(e) => setSortByPriority(e.target.checked)}
            className="rounded border-slate-300"
          />
          Sort by priority
        </label>
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={filterNeedsHuman}
            onChange={(e) => setFilterNeedsHuman(e.target.checked)}
            className="rounded border-slate-300"
          />
          Needs-human only
        </label>
        <span className="text-slate-400">
          Showing {rows.length} of {batchResponse.total}
        </span>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">ID</th>
                <th className="px-4 py-3 text-left">Message</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-left">Priority</th>
                <th className="px-4 py-3 text-left">Confidence</th>
                <th className="px-4 py-3 text-left">Human?</th>
                <th className="px-4 py-3 text-left">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => {
                const isExpanded = expandedId === row.id;
                const r = row.result;
                return (
                  <Fragment key={row.id}>
                    <tr
                      onClick={() => setExpandedId(isExpanded ? null : row.id)}
                      className={`cursor-pointer hover:bg-slate-50 ${row.error ? "bg-red-50/40" : ""}`}
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{row.id}</td>
                      <td className="px-4 py-3 max-w-xs truncate text-slate-700">{row.message}</td>
                      <td className="px-4 py-3">{r && <CategoryBadge category={r.category} />}</td>
                      <td className="px-4 py-3">{r && <PriorityBadge priority={r.priority} />}</td>
                      <td className="px-4 py-3 text-slate-600">
                        {r ? `${Math.round(r.confidence * 100)}%` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {r?.needs_human ? (
                          <span className="text-rose-600 font-semibold">Yes</span>
                        ) : (
                          <span className="text-slate-400">No</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">{row.latency_ms ?? "—"} ms</td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-50/70">
                        <td colSpan={7} className="px-4 py-4">
                          {row.error && (
                            <p className="text-xs text-red-600 mb-2">
                              Processing error (fallback used): {row.error}
                            </p>
                          )}
                          <div className="grid sm:grid-cols-2 gap-4">
                            <div>
                              <h4 className="text-xs font-semibold uppercase text-slate-400 mb-1">
                                Full message
                              </h4>
                              <p className="text-slate-700 whitespace-pre-wrap">{row.message}</p>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold uppercase text-slate-400 mb-1">
                                Customer-facing reply
                              </h4>
                              <p className="text-slate-700 whitespace-pre-wrap">{r?.reply}</p>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold uppercase text-slate-400 mb-1">
                                Internal summary
                              </h4>
                              <p className="text-slate-600">{r?.summary}</p>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold uppercase text-slate-400 mb-1">
                                Suggested action
                              </h4>
                              <p className="text-slate-600">{r?.suggested_action}</p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "text-slate-800" }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}
