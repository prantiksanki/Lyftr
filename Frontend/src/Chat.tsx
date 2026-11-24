import { useEffect, useRef, useState } from "react"
import {
  ArrowUp,
  Database,
  Home as HomeIcon,
  KeyRound,
  PanelLeft,
  Plus,
  Settings,
  Sparkles,
  Zap,
} from "lucide-react"
import RadialGlowBackground from "@/components/ui/radial-glow-background"
import { sendChat } from "./api.js"

type Meta = {
  resolution_source: string
  model: string
  latency_ms: number
  input_tokens: number
  output_tokens: number
  key_id: string | null
  fallback_attempts: number
}
type Msg = { role: "user" | "assistant" | "error"; content: string; metadata?: Meta }

const newSessionId = () =>
  "s-" + (crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(16).slice(2, 10))

const SUGGESTIONS = [
  { icon: Sparkles, text: "Explain how a neural network learns" },
  { icon: Zap, text: "What is the Big Bang theory?" },
  { icon: Database, text: "How does blockchain work?" },
  { icon: KeyRound, text: "Explain the water cycle" },
]

function MetaRow({ m }: { m: Meta }) {
  const cache = m.resolution_source === "LLM_CACHE"
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-dashed border-white/10 pt-2 text-xs text-white/50">
      <span
        className={
          "rounded-full px-2 py-0.5 font-semibold " +
          (cache ? "bg-amber-400/15 text-amber-300" : "bg-emerald-400/15 text-emerald-300")
        }
      >
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
      <span className="text-white/35">
        key: {m.key_id ?? "—"} · fallbacks: {m.fallback_attempts}
      </span>
    </div>
  )
}

export default function Chat() {
  const [sessionId, setSessionId] = useState(newSessionId) // new session on every page load
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState("")
  const [systemPrompt, setSystemPrompt] = useState("")
  const [simulate, setSimulate] = useState("")
  const [busy, setBusy] = useState(false)
  const [sidebar, setSidebar] = useState(() => window.innerWidth >= 768)
  const endRef = useRef<HTMLDivElement>(null)
  const started = messages.length > 0

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, busy])

  async function send(override?: string) {
    const text = (override ?? input).trim()
    if (!text || busy) return
    setInput("")
    setMessages((m) => [...m, { role: "user", content: text }])
    setBusy(true)
    try {
      const data = await sendChat({ sessionId, message: text, systemPrompt, simulate })
      setMessages((m) => [...m, { role: "assistant", content: data.reply, metadata: data.metadata }])
    } catch (e) {
      setMessages((m) => [...m, { role: "error", content: (e as Error).message }])
    } finally {
      setBusy(false)
    }
  }

  function newChat() {
    setMessages([])
    setInput("")
    setSessionId(newSessionId())
  }

  const field =
    "w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder:text-white/30 outline-none focus:border-violet-400/70"

  return (
    <div className="relative isolate flex h-screen w-full overflow-hidden text-white">
      <RadialGlowBackground />

      {/* Sidebar */}
      <aside
        className={
          "flex shrink-0 flex-col border-r border-white/10 bg-black/50 backdrop-blur-xl transition-[width] duration-300 " +
          (sidebar ? "w-72" : "w-0 overflow-hidden border-r-0")
        }
      >
        <div className="flex w-72 items-center justify-between px-4 py-4">
          <span className="font-mono text-sm font-semibold">◆ LLM Chatbot</span>
          <button
            onClick={() => setSidebar(false)}
            className="cursor-pointer rounded-md p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
            aria-label="Collapse sidebar"
          >
            <PanelLeft className="size-4" />
          </button>
        </div>

        <div className="w-72 px-3">
          <button
            onClick={newChat}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-black hover:bg-white/90"
          >
            <Plus className="size-4" /> New chat
          </button>
        </div>

        <div className="mt-6 w-72 flex-1 overflow-y-auto px-4">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white/50">
            <Settings className="size-3.5" /> Settings
          </div>
          <label className="mb-4 block text-xs text-white/60">
            System prompt (this session)
            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={4}
              placeholder="You are a helpful assistant."
              className={field + " mt-1.5 resize-none"}
            />
          </label>
          <label className="block text-xs text-white/60">
            Simulate failure (demo)
            <input
              value={simulate}
              onChange={(e) => setSimulate(e.target.value)}
              placeholder="key_1=429"
              className={field + " mt-1.5"}
            />
          </label>
          <p className="mt-2 text-[11px] leading-relaxed text-white/35">
            Sends the X-Simulate-Failure header, e.g. key_1=429 or *=429.
          </p>
        </div>

        <div className="w-72 border-t border-white/10 px-4 py-3 text-xs text-white/40">
          <div className="mb-2 truncate">session {sessionId}</div>
          <a href="#/" className="flex items-center gap-2 text-white/60 hover:text-white">
            <HomeIcon className="size-3.5" /> Home
          </a>
        </div>
      </aside>

      {/* Main */}
      <main className="relative flex min-w-0 flex-1 flex-col">
        {!sidebar && (
          <button
            onClick={() => setSidebar(true)}
            className="absolute left-3 top-3 z-10 cursor-pointer rounded-md border border-white/10 bg-black/40 p-2 text-white/70 backdrop-blur hover:text-white"
            aria-label="Open sidebar"
          >
            <PanelLeft className="size-4" />
          </button>
        )}

        {/* top area: greeting (empty) or messages (chatting) */}
        <div
          className={
            "min-h-0 " +
            (started
              ? "flex-1 overflow-y-auto"
              : "flex flex-1 items-end justify-center pb-8")
          }
        >
          {started ? (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-8">
              {messages.map((m, i) =>
                m.role === "assistant" && m.metadata ? (
                  <div
                    key={i}
                    data-testid="assistant-message"
                    className="max-w-[88%] self-start rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur"
                  >
                    <div className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</div>
                    <MetaRow m={m.metadata} />
                  </div>
                ) : m.role === "error" ? (
                  <div
                    key={i}
                    role="alert"
                    className="self-center rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-2 text-sm text-red-300"
                  >
                    {m.content}
                  </div>
                ) : (
                  <div
                    key={i}
                    className="max-w-[88%] self-end whitespace-pre-wrap break-words rounded-2xl bg-violet-600 px-4 py-2.5"
                  >
                    {m.content}
                  </div>
                )
              )}
              {busy && <div className="self-start text-sm text-white/50">Thinking…</div>}
              <div ref={endRef} />
            </div>
          ) : (
            <div className="px-4 text-center">
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">What can I help you with?</h1>
              <p className="mt-3 text-white/55">Ask anything to start a conversation.</p>
            </div>
          )}
        </div>

        {/* input: centered when empty, pinned to the bottom after the first message */}
        <div className={"w-full px-4 " + (started ? "pb-5 pt-2" : "")}>
          <div className="mx-auto w-full max-w-3xl">
            <div className="rounded-2xl border border-white/10 bg-black/50 p-3 backdrop-blur-xl focus-within:border-violet-400/60">
              <textarea
                data-testid="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                rows={started ? 2 : 3}
                placeholder="Type a message…"
                className="w-full resize-none bg-transparent px-1 text-base text-white outline-none placeholder:text-white/35"
              />
              <div className="mt-1 flex items-center justify-between">
                <span className="text-xs text-white/35">Enter to send · Shift+Enter for newline</span>
                <button
                  data-testid="send-button"
                  onClick={() => send()}
                  disabled={busy}
                  className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-default disabled:opacity-50"
                >
                  Send <ArrowUp className="size-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* bottom area: suggestions (empty only) */}
        {!started && (
          <div className="flex flex-1 items-start justify-center px-4 pt-6">
            <div className="flex max-w-3xl flex-wrap justify-center gap-2.5">
              {SUGGESTIONS.map(({ icon: Icon, text }) => (
                <button
                  key={text}
                  onClick={() => send(text)}
                  className="flex cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70 backdrop-blur transition hover:bg-white/10 hover:text-white"
                >
                  <Icon className="size-3.5" /> {text}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
