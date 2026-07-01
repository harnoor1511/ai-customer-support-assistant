const PRIORITY_STYLES = {
  P0: "bg-red-100 text-red-700 border-red-300",
  P1: "bg-orange-100 text-orange-700 border-orange-300",
  P2: "bg-yellow-100 text-yellow-700 border-yellow-300",
  P3: "bg-slate-100 text-slate-600 border-slate-300",
};

export default function PriorityBadge({ priority }) {
  const style = PRIORITY_STYLES[priority] || PRIORITY_STYLES.P3;
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${style}`}>
      {priority}
    </span>
  );
}
