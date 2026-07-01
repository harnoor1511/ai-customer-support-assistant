// Thin API client for the support backend. Keeping this isolated means
// swapping base URL, adding auth headers, or adding new endpoints
// (history, feedback, etc.) later won't touch component code.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function handleResponse(res) {
  if (!res.ok) {
    let detail = "Something went wrong while contacting the support assistant.";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse failure, use default detail
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function triageMessage(message, conversationId) {
  const res = await fetch(`${API_BASE_URL}/api/support/triage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  return handleResponse(res);
}

// items: [{ id, message }, ...]
export async function triageBatch(items) {
  const res = await fetch(`${API_BASE_URL}/api/support/triage-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: items }),
  });
  return handleResponse(res);
}

// file: a File object (.csv or .json)
export async function triageBatchFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/support/triage-batch-file`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(res);
}
