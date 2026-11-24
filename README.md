# LLM Chatbot with Key Failover and Response Caching

React + FastAPI + LiteLLM + SQLite. Multi-turn chat with an API-key pool that fails over automatically, LiteLLM response caching, and per-request metadata (source, model, latency, tokens) shown next to every reply.

## 1. Live URLs

- Frontend: `<TODO: deployed frontend URL>`
- Backend: `<TODO: deployed backend URL>` (try `/health`)
- Repo: `<TODO: GitHub URL>`
- Demo video: `<TODO>`

## 2. Run locally

### With Docker
```bash
cp .env.example .env      # put 2+ OpenRouter keys in LLM_API_KEYS (LLM_MODEL=openrouter/<model-id>)
make up                   # backend :8000, frontend :3000
make down
```
SQLite lives in the named volume `app_data` mounted at `/data`, so history survives restarts.

### Without Docker
```bash
# backend (Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export LLM_API_KEYS=key1,key2 ENABLE_FAILURE_SIMULATION=true DATABASE_URL=sqlite:///./app.db
uvicorn app.main:app --port 8000
# tests (no network/keys needed)
python -m pytest -q tests

# frontend
cd frontend && npm install && VITE_API_URL=http://localhost:8000 npm run dev   # :3000
```

Environment variables are listed in `.env.example` (`LLM_API_KEYS`, `DATABASE_URL`, `ALLOWED_ORIGINS`, `ENABLE_FAILURE_SIMULATION`, `LLM_MODEL`, `DEFAULT_SYSTEM_PROMPT`, `LLM_TIMEOUT_SECONDS`, `VITE_API_URL`).

## 3. Design decisions

**Key fallback.** `LLM_API_KEYS` is parsed into `key_1..key_n`. For each request `llm.complete` walks the pool in order and calls `litellm.completion(api_key=...)`. Any failure of a key (429, quota, 5xx, timeout, connection error, bad key) moves to the next key and increments `fallback_attempts`. If all keys fail the API returns `503 {"detail": "all providers unavailable"}` and nothing is written to history. Key values are never returned or logged; only `key_id`. A manual ordered loop (rather than a Router) keeps `key_id`/`fallback_attempts` exact and makes the failure-simulation hook trivial.

**Failure simulation.** `X-Simulate-Failure: key_1=429,key_2=500` / `*=429` (statuses 429/500/502/503) raises the matching LiteLLM exception for those keys inside that request only, before any provider call, so the remaining keys still produce real answers. Honored only when `ENABLE_FAILURE_SIMULATION=true`.

**Caching.** `litellm.cache = Cache(type="local")` (in-memory) with `caching=True` per call. LiteLLM's key is the model plus the full message list (system + history + new message); the API key is not part of it. The same first message in a new session therefore hits the cache; any different message or history misses. A hit is detected through the response's `cache_hit` flag, reported as `LLM_CACHE` with `key_id: null`, `fallback_attempts: 0`, the stored reply text and stored usage. Because a hit never touches a key, a simulated failure on `key_1` still falls through to `key_2`, which may then serve the cached answer. The cache is in-memory, so it is cleared on restart (history in SQLite is not).

**SQLite session storage.** Stdlib `sqlite3`, schema created at startup (`messages` per the spec, plus an index and a small `sessions` table holding the per-session system prompt). The user and assistant rows are written together only after a successful LLM call, so 422/503 never pollute history. The client sends only the new message; the backend rebuilds `[system, ...history, new]` each time. Assistant rows store the metadata JSON, so the history endpoint returns it.

**Errors.** Validation errors → 422 JSON, unknown session → 404, all keys down → 503, anything else → generic JSON 500 (no stack traces).

## 4. Verification

```bash
B=http://localhost:8000
curl $B/health

# live, then cache hit in a NEW session (same first message -> LLM_CACHE, key_id null, faster)
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"a1","message":"What is the capital of France?"}'
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"a2","message":"What is the capital of France?"}'

# failover: key_1 fails -> key_2 answers (key_id=key_2, fallback_attempts=1)
curl -s $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"a3","message":"Tell me a joke"}'

# all keys fail -> 503 {"detail":"all providers unavailable"}, nothing stored
curl -si $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"a4","message":"hello there"}'
curl -si $B/sessions/a4/messages        # 404 session not found

# multi-turn + history + per-request tokens
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"m1","message":"My name is Asha."}'
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"m1","message":"What is my name?"}'
curl -s $B/sessions/m1/messages
```
In the UI, every assistant bubble shows source, model, latency, input and output tokens (that request only). Settings → "Simulate failure header" sends `X-Simulate-Failure` for the demo. `make test` runs 18 backend tests (validation, multi-turn, isolation, caching, failover, 503, 404).

## 5. Setup Used

- Editor: VS Code
- AI tools: Claude Code (Claude) for scaffolding, implementation and tests

## 6. Bonus features

- In-UI failure-simulation field so failover can be demoed without curl.
- Cache-hit/live colored badges and `key_id` / `fallback_attempts` shown per reply.
- Per-session system prompt persisted in SQLite.
