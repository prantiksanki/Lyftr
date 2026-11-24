import functools
import os
import tempfile

import litellm
import pytest
from fastapi.testclient import TestClient

CALLS = []


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{os.path.join(tmp, 'app.db')}")
    monkeypatch.setenv("LLM_API_KEYS", "fake-key-1,fake-key-2")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")

    real = litellm.completion
    CALLS.clear()

    @functools.wraps(real)
    def fake(*args, **kwargs):
        CALLS.append(kwargs)
        last = kwargs["messages"][-1]["content"]
        kwargs.setdefault("mock_response", f"echo: {last}")
        return real(*args, **kwargs)

    from app import llm
    monkeypatch.setattr(llm.litellm, "completion", fake)

    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def chat(c, sid, msg, headers=None, **extra):
    return c.post("/chat", json={"session_id": sid, "message": msg, **extra}, headers=headers or {})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


@pytest.mark.parametrize(
    "body",
    [
        {"session_id": "", "message": "hi"},
        {"session_id": "s", "message": "   "},
        {"session_id": "s", "message": "x" * 4001},
        {"message": "hi"},
        {"session_id": "s"},
    ],
)
def test_validation_422(client, body):
    r = client.post("/chat", json=body)
    assert r.status_code == 422 and "detail" in r.json()


def test_malformed_json(client):
    r = client.post("/chat", content="{bad", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_chat_and_history(client):
    r = chat(client, "s1", "hello")
    assert r.status_code == 200
    d = r.json()
    m = d["metadata"]
    assert d["reply"] and m["resolution_source"] == "LIVE_INFERENCE"
    assert m["key_id"] == "key_1" and m["fallback_attempts"] == 0
    assert isinstance(m["latency_ms"], int) and m["input_tokens"] > 0 and m["output_tokens"] > 0
    h = client.get("/sessions/s1/messages").json()
    assert [x["role"] for x in h["messages"]] == ["user", "assistant"]
    assert h["messages"][1]["metadata"]["input_tokens"] == m["input_tokens"]


def test_multi_turn_context_sent(client):
    chat(client, "s2", "my name is Bob")
    chat(client, "s2", "what is my name?")
    sent = CALLS[-1]["messages"]
    assert [x["role"] for x in sent] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "my name is Bob"


def test_sessions_isolated(client):
    chat(client, "a", "only in a")
    chat(client, "b", "only in b")
    assert len(client.get("/sessions/a/messages").json()["messages"]) == 2
    assert "only in a" not in str(client.get("/sessions/b/messages").json())


def test_unknown_session_404(client):
    r = client.get("/sessions/nope/messages")
    assert r.status_code == 404 and r.json() == {"detail": "session not found"}


def test_cache_hit_across_sessions(client):
    first = chat(client, "c1", "capital of France?").json()
    second = chat(client, "c2", "capital of France?").json()
    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    m = second["metadata"]
    assert m["resolution_source"] == "LLM_CACHE"
    assert second["reply"] == first["reply"]
    assert m["key_id"] is None and m["fallback_attempts"] == 0
    assert m["input_tokens"] == first["metadata"]["input_tokens"]
    third = chat(client, "c3", "a different question").json()
    assert third["metadata"]["resolution_source"] == "LIVE_INFERENCE"


@pytest.mark.parametrize("hdr", ["key_1=429", "key_1=500", "key_1=503"])
def test_failover(client, hdr):
    r = chat(client, "f-" + hdr, "q " + hdr, headers={"X-Simulate-Failure": hdr})
    assert r.status_code == 200
    m = r.json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1


def test_all_fail_503_not_stored(client):
    r = chat(client, "dead", "q dead", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503 and r.json() == {"detail": "all providers unavailable"}
    assert client.get("/sessions/dead/messages").status_code == 404


def test_both_keys_listed(client):
    r = chat(client, "both", "q both", headers={"X-Simulate-Failure": "key_1=429,key_2=500"})
    assert r.status_code == 503


def test_simulation_ignored_when_disabled(client, monkeypatch):
    client.app.state.settings.enable_failure_simulation = False
    # settings object is captured by closure; same instance
    r = chat(client, "off", "q off", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 200
