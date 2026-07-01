export default function CategoryBadge({ category }) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border bg-indigo-100 text-indigo-700 border-indigo-300">
      {category}
    </span>
  );
}
