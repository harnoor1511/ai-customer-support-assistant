import { useState, useRef } from "react";
import { triageMessage } from "./api/supportApi";
import ResultCard from "./components/ResultCard";
import BatchUploadPanel from "./components/BatchUploadPanel";

const MAX_CHARS = 8000;

export default function App() {
  const [mode, setMode] = useState("single"); // "single" | "batch"
  const [message, setMessage] = useState("");
  const [thread, setThread] = useState([]); // [{ role: "user"|"assistant", content, result? }]
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Stable per-chat-session ID — created once, reused for every message
  // in this session so the backend can recall prior turns.
  const conversationIdRef = useRef(crypto.randomUUID());

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError("");

    // Show the user's message immediately.
    setThread((prev) => [...prev, { role: "user", content: trimmed }]);
    setMessage("");

    try {
      const data = await triageMessage(trimmed, conversationIdRef.current);
      setThread((prev) => [...prev, { role: "assistant", content: data.reply, result: data }]);
    } catch (err) {
      setError(err.message || "Failed to get a response. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleNewConversation() {
    conversationIdRef.current = crypto.randomUUID();
    setThread([]);
    setError("");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-4xl mx-auto px-6 py-5">
          <h1 className="text-xl font-bold text-slate-900">AI Customer Support Assistant</h1>
          <p className="text-sm text-slate-500 mt-1">
            Chat with the assistant, or upload a dataset to process a full batch at once.
          </p>

          <div className="mt-4 flex items-center justify-between">
            <div className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1">
              <ModeButton active={mode === "single"} onClick={() => setMode("single")}>
                Chat
              </ModeButton>
              <ModeButton active={mode === "batch"} onClick={() => setMode("batch")}>
                Batch (upload dataset)
              </ModeButton>
            </div>

            {mode === "single" && thread.length > 0 && (
              <button
                onClick={handleNewConversation}
                className="text-xs font-medium text-slate-500 hover:text-slate-700 underline"
              >
                Start new conversation
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {mode === "single" ? (
          <>
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 space-y-4 mb-6 min-h-[120px]">
              {thread.length === 0 && (
                <p className="text-sm text-slate-400">
                  Send a message to start the conversation. The assistant will remember context
                  within this session (e.g. if it asks for your order ID, you can just reply with it).
                </p>
              )}

              {thread.map((turn, i) =>
                turn.role === "user" ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[80%] rounded-xl bg-indigo-600 text-white px-4 py-2.5 text-sm">
                      {turn.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-start">
                      <div className="max-w-[80%] rounded-xl bg-slate-100 text-slate-800 px-4 py-2.5 text-sm">
                        {turn.content}
                      </div>
                    </div>
                    {/* Full structured result for this assistant turn (category, priority, etc.) */}
                    <ResultCard result={turn.result} />
                  </div>
                )
              )}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-xl bg-slate-100 text-slate-400 px-4 py-2.5 text-sm inline-flex items-center gap-2">
                    <span className="h-3 w-3 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
                    Thinking…
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4">
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value.slice(0, MAX_CHARS))}
                placeholder="Type your message… (press Enter to send)"
                rows={3}
                maxLength={MAX_CHARS}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-y"
              />

              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  {message.length} / {MAX_CHARS} characters
                </span>
                <button
                  type="submit"
                  disabled={loading || !message.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  {loading ? (
                    <>
                      <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      Sending…
                    </>
                  ) : (
                    "Send"
                  )}
                </button>
              </div>
            </form>

            {error && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}
          </>
        ) : (
          <BatchUploadPanel />
        )}
      </main>
    </div>
  );
}

function ModeButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
        active ? "bg-white text-indigo-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}