"""LiteLLM gateway: key pool, ordered failover, built-in response caching."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import litellm
from litellm.caching import Cache

logger = logging.getLogger("llm")
litellm.drop_params = True
litellm.suppress_debug_info = True

SIMULATED_STATUSES = {429, 500, 502, 503}


class AllProvidersUnavailable(Exception):
    pass


@dataclass
class LLMResult:
    reply: str
    resolution_source: str
    model: str
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]
    fallback_attempts: int


def setup_cache() -> None:
    litellm.cache = Cache(type="local")


def cache_enabled() -> bool:
    return litellm.cache is not None


def parse_simulation(header: Optional[str]) -> Dict[str, int]:
    """'key_1=429,key_2=500' / '*=429' -> {'key_1': 429, ...}. Invalid pairs are ignored."""
    out: Dict[str, int] = {}
    if not header:
        return out
    for part in header.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v.isdigit() and int(v) in SIMULATED_STATUSES:
            out[k] = int(v)
    return out


def _simulated_error(status: int, model: str) -> Exception:
    cls = {
        429: litellm.RateLimitError,
        500: litellm.InternalServerError,
        502: litellm.InternalServerError,
        503: litellm.ServiceUnavailableError,
    }[status]
    return cls(message=f"simulated {status}", llm_provider="simulated", model=model)


def _extract(resp, key_id: str, attempts: int, model: str) -> LLMResult:
    cache_hit = bool((getattr(resp, "_hidden_params", None) or {}).get("cache_hit"))
    usage = getattr(resp, "usage", None)
    return LLMResult(
        reply=resp.choices[0].message.content or "",
        resolution_source="LLM_CACHE" if cache_hit else "LIVE_INFERENCE",
        model=model,
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        key_id=None if cache_hit else key_id,
        fallback_attempts=0 if cache_hit else attempts,
    )


def complete(messages: List[dict], settings, simulate: Dict[str, int]) -> LLMResult:
    """Try keys in order; fail over on any provider error. Raises AllProvidersUnavailable."""
    model = settings.model
    attempts = 0
    for idx, key in enumerate(settings.api_keys, start=1):
        key_id = f"key_{idx}"
        status = simulate.get(key_id, simulate.get("*"))
        try:
            if status:
                raise _simulated_error(status, model)
            resp = litellm.completion(
                model=model,
                messages=messages,
                api_key=key,
                caching=True,
                timeout=settings.request_timeout,
                num_retries=0,
            )
            result = _extract(resp, key_id, attempts, model)
            if not result.reply:
                raise ValueError("empty reply")
            return result
        except Exception as e:  # any failure of this key -> next key
            attempts += 1
            logger.warning("%s failed (%s): %s", key_id, type(e).__name__, str(e)[:160].replace(key, "***"))
    raise AllProvidersUnavailable()
