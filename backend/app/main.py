import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import llm
from .config import get_settings
from .db import Database
from .schemas import ChatRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()
    db = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db.init()
        llm.setup_cache()
        yield

    app = FastAPI(title="LLM Chatbot", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(_: Request, exc: StarletteHTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exc(_: Request, exc: RequestValidationError):
        errors = [
            {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def any_exc(_: Request, exc: Exception):
        logger.exception("unhandled error")
        return JSONResponse({"detail": "internal server error"}, status_code=500)

    @app.get("/health")
    def health():
        if not db.ping() or not settings.api_keys:
            raise HTTPException(status_code=503, detail="service not ready")
        return {
            "status": "ok",
            "keys_configured": len(settings.api_keys),
            "cache_enabled": llm.cache_enabled(),
        }

    @app.post("/chat")
    async def chat(
        body: ChatRequest,
        x_simulate_failure: Optional[str] = Header(default=None),
    ):
        started = time.perf_counter()
        simulate = (
            llm.parse_simulation(x_simulate_failure) if settings.enable_failure_simulation else {}
        )
        sid = body.session_id
        system_prompt = (
            body.system_prompt
            if body.system_prompt and body.system_prompt.strip()
            else (db.get_system_prompt(sid) or settings.default_system_prompt)
        )
        history = db.get_history(sid)
        messages = (
            [{"role": "system", "content": system_prompt}]
            + [{"role": m["role"], "content": m["content"]} for m in history]
            + [{"role": "user", "content": body.message}]
        )
        try:
            result = await run_in_threadpool(llm.complete, messages, settings, simulate)
        except llm.AllProvidersUnavailable:
            raise HTTPException(status_code=503, detail="all providers unavailable")

        metadata = {
            "resolution_source": result.resolution_source,
            "model": result.model,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "key_id": result.key_id,
            "fallback_attempts": result.fallback_attempts,
        }
        db.save_exchange(sid, system_prompt, body.message, result.reply, metadata)
        return {"session_id": sid, "reply": result.reply, "metadata": metadata}

    @app.get("/sessions/{session_id}/messages")
    def session_messages(session_id: str):
        if not db.session_exists(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        out = []
        for m in db.get_history(session_id):
            item = {"role": m["role"], "content": m["content"]}
            if m["role"] == "assistant" and m["metadata"]:
                item["metadata"] = m["metadata"]
            out.append(item)
        return {"session_id": session_id, "messages": out}

    return app


app = create_app()
