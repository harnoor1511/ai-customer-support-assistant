import { useRef, useState } from "react";
import { triageBatchFile } from "../api/supportApi";
import BatchResultsTable from "./BatchResultsTable";

export default function BatchUploadPanel() {
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [batchResponse, setBatchResponse] = useState(null);
  const fileInputRef = useRef(null);

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setLoading(true);
    setError("");
    setBatchResponse(null);

    try {
      const data = await triageBatchFile(file);
      setBatchResponse(data);
    } catch (err) {
      setError(err.message || "Failed to process the uploaded dataset.");
    } finally {
      setLoading(false);
    }
  }

  function resetUpload() {
    setFileName("");
    setBatchResponse(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div>
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6">
        <label className="block text-sm font-medium text-slate-700 mb-2">
          Upload a dataset (.csv or .json)
        </label>
        <p className="text-xs text-slate-500 mb-4">
          CSV needs a <code className="bg-slate-100 px-1 rounded">message</code> column (an{" "}
          <code className="bg-slate-100 px-1 rounded">id</code> column is optional). JSON should be a
          list of strings or <code className="bg-slate-100 px-1 rounded">{"{id, message}"}</code>{" "}
          objects. Max 200 rows.
        </p>

        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.json"
            onChange={handleFileChange}
            disabled={loading}
            className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-xl file:border-0 file:bg-indigo-600 file:px-4 file:py-2.5 file:text-sm file:font-semibold file:text-white hover:file:bg-indigo-700 file:cursor-pointer disabled:opacity-50"
          />
          {fileName && !loading && (
            <button
              type="button"
              onClick={resetUpload}
              className="text-xs text-slate-400 hover:text-slate-600 whitespace-nowrap"
            >
              Clear
            </button>
          )}
        </div>

        {loading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <span className="h-4 w-4 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
            Processing {fileName}… this may take a bit for larger datasets.
          </div>
        )}
      </div>

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <BatchResultsTable batchResponse={batchResponse} />
    </div>
  );
}
