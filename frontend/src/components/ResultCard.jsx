import PriorityBadge from "./PriorityBadge";
import CategoryBadge from "./CategoryBadge";

export default function ResultCard({ result }) {
  if (!result) return null;

  const confidencePct = Math.round(result.confidence * 100);

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={result.category} />
          <PriorityBadge priority={result.priority} />
          {result.needs_human && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border bg-rose-100 text-rose-700 border-rose-300">
              Needs Human
            </span>
          )}
        </div>
        <div className="text-xs text-slate-500">
          Confidence: <span className="font-semibold text-slate-700">{confidencePct}%</span>
        </div>
      </div>

      <div className="px-6 py-4 space-y-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
            Customer-facing reply
          </h3>
          <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">{result.reply}</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
              Internal summary
            </h3>
            <p className="text-sm text-slate-600">{result.summary}</p>
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
              Suggested action
            </h3>
            <p className="text-sm text-slate-600">{result.suggested_action}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
