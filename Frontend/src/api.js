const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

function readableError(status, data) {
  if (status === 503) return "All AI providers are currently unavailable. Please try again shortly.";
  if (status === 422) {
    const d = data && data.detail;
    if (Array.isArray(d) && d.length) return "Invalid input: " + d.map((e) => e.msg).join("; ");
    return "Invalid input. Messages must be 1-4000 characters.";
  }
  if (data && typeof data.detail === "string") return data.detail;
  return `Request failed (HTTP ${status}).`;
}

export async function sendChat({ sessionId, message, systemPrompt, simulate }) {
  const headers = { "Content-Type": "application/json" };
  if (simulate) headers["X-Simulate-Failure"] = simulate;
  const body = { session_id: sessionId, message };
  if (systemPrompt && systemPrompt.trim()) body.system_prompt = systemPrompt;
  let res;
  try {
    res = await fetch(`${API_URL}/chat`, { method: "POST", headers, body: JSON.stringify(body) });
  } catch {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw new Error(readableError(res.status, data));
  return data;
}
