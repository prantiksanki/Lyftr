import { useEffect, useMemo, useRef, useState } from "react";
import { sendChat } from "./api.js";

const newSessionId = () =>
  "s-" + (crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(16).slice(2, 10));

function Meta({ m }) {
  return (
    <div className="meta">
      <span className={"badge " + (m.resolution_source === "LLM_CACHE" ? "cache" : "live")}>
        <span data-testid="meta-source">{m.resolution_source}</span>
      </span>
      <span>
        model: <span data-testid="meta-model">{m.model}</span>
      </span>
      <span>
        latency: <span data-testid="meta-latency">{m.latency_ms} ms</span>
      </span>
      <span>
        in: <span data-testid="meta-input-tokens">{m.input_tokens}</span>
      </span>
      <span>
        out: <span data-testid="meta-output-tokens">{m.output_tokens}</span>
      </span>
      <span className="muted">
        key: {m.key_id ?? "—"} · fallbacks: {m.fallback_attempts}
      </span>
    </div>
  );
}

export default function App() {
  const sessionId = useMemo(newSessionId, []); // new session on every page load
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simulate, setSimulate] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const data = await sendChat({ sessionId, message: text, systemPrompt, simulate });
      setMessages((m) => [...m, { role: "assistant", content: data.reply, metadata: data.metadata }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "error", content: e.message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>LLM Chatbot</h1>
        <span className="muted">session {sessionId}</span>
      </header>

      <details className="settings">
        <summary>Settings</summary>
        <label>
          System prompt (applies to this session)
          <textarea
            data-testid="system-prompt-input"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={2}
            placeholder="You are a helpful assistant."
          />
        </label>
        <label>
          Simulate failure header (demo only, e.g. key_1=429)
          <input value={simulate} onChange={(e) => setSimulate(e.target.value)} placeholder="key_1=429" />
        </label>
      </details>

      <main className="chat">
        {messages.length === 0 && <p className="muted center">Say hello to start the conversation.</p>}
        {messages.map((m, i) =>
          m.role === "assistant" ? (
            <div key={i} className="bubble assistant" data-testid="assistant-message">
              <div className="text">{m.content}</div>
              <Meta m={m.metadata} />
            </div>
          ) : m.role === "error" ? (
            <div key={i} className="bubble error" role="alert">
              {m.content}
            </div>
          ) : (
            <div key={i} className="bubble user">
              {m.content}
            </div>
          )
        )}
        {busy && <div className="bubble assistant muted">Thinking…</div>}
        <div ref={endRef} />
      </main>

      <footer>
        <textarea
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          placeholder="Type a message…"
        />
        <button data-testid="send-button" onClick={send} disabled={busy}>
          Send
        </button>
      </footer>
    </div>
  );
}
