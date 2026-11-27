"""Privacy-conscious local telemetry and optional Langfuse tracing."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# USD per 1M text tokens, checked against Groq's official model documentation
# on 2026-11-27. Unknown or retired models intentionally have no default rate.
MODEL_PRICING_TABLE: Dict[str, Dict[str, float]] = {
    "openai/gpt-oss-120b": {"prompt_per_million": 0.15, "cached_prompt_per_million": 0.075, "completion_per_million": 0.60},
    "openai/gpt-oss-20b": {"prompt_per_million": 0.075, "cached_prompt_per_million": 0.0375, "completion_per_million": 0.30},
}


def calculate_model_cost_usd(
    model_name: Optional[str], prompt_tokens: Optional[int], completion_tokens: Optional[int],
    cached_prompt_tokens: Optional[int] = None,
) -> Optional[float]:
    """Return an estimate only for a model with an explicit configured rate."""
    if prompt_tokens is None or completion_tokens is None or cached_prompt_tokens is None:
        return None
    rates = MODEL_PRICING_TABLE.get(model_name or "")
    if rates is None:
        return None
    cached_prompt_tokens = min(max(int(cached_prompt_tokens), 0), int(prompt_tokens))
    uncached_prompt_tokens = int(prompt_tokens) - cached_prompt_tokens
    prompt_cost = (
        uncached_prompt_tokens / 1_000_000.0 * rates["prompt_per_million"]
        + cached_prompt_tokens / 1_000_000.0 * rates["cached_prompt_per_million"]
    )
    completion_cost = completion_tokens / 1_000_000.0 * rates["completion_per_million"]
    return round(prompt_cost + completion_cost, 8)


CAPTURE_CONTENT_OPT_IN = os.environ.get("TELEMETRY_CAPTURE_CONTENT", "false").lower() == "true"
_SENSITIVE_KEYS = {
    "question", "query", "sql", "rows", "sql_result", "preview", "raw_content",
    "answer", "final_response", "prompt", "context", "document_text", "authorization",
    "token", "password", "secret", "api_key", "email", "customer_id",
}


def sanitize_telemetry_payload(data: Any, opt_in: bool = CAPTURE_CONTENT_OPT_IN) -> Any:
    """Redact sensitive values recursively; Langfuse calls do not include content at all."""
    if opt_in:
        return data
    if isinstance(data, dict):
        return {
            key: "[REDACTED_BY_POLICY]" if str(key).lower() in _SENSITIVE_KEYS
            else sanitize_telemetry_payload(value, opt_in=False)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [sanitize_telemetry_payload(item, opt_in=False) for item in data]
    return data


def langfuse_enabled() -> bool:
    return os.environ.get("LANGFUSE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


_LANGFUSE_CLIENT = None
_LANGFUSE_CLIENT_INITIALIZED = False


def get_langfuse_client():
    """Lazily initialize Langfuse; missing configuration keeps the app usable offline."""
    global _LANGFUSE_CLIENT, _LANGFUSE_CLIENT_INITIALIZED
    if not langfuse_enabled():
        return None
    if _LANGFUSE_CLIENT_INITIALIZED:
        return _LANGFUSE_CLIENT

    _LANGFUSE_CLIENT_INITIALIZED = True
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
    if not public_key or not secret_key:
        logger.warning("Langfuse is enabled but credentials are missing; tracing is disabled.")
        return None

    try:
        from langfuse import Langfuse

        _LANGFUSE_CLIENT = Langfuse(public_key=public_key, secret_key=secret_key, base_url=host)
    except Exception as exc:  # Telemetry must never prevent an analytical request.
        logger.warning("Langfuse initialization failed (%s); tracing is disabled.", type(exc).__name__)
        _LANGFUSE_CLIENT = None
    return _LANGFUSE_CLIENT


@contextmanager
def langfuse_observation(
    name: str,
    *,
    as_type: str = "span",
    trace_id: Optional[str] = None,
    parent_observation_id: Optional[str] = None,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[Any]:
    """Create a privacy-safe observation, falling back cleanly when unavailable."""
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    kwargs: Dict[str, Any] = {
        "name": name,
        "as_type": as_type,
        "metadata": sanitize_telemetry_payload(metadata or {}, opt_in=False),
    }
    if model and as_type == "generation":
        kwargs["model"] = model
    if trace_id:
        trace_context = {"trace_id": trace_id}
        if parent_observation_id:
            trace_context["parent_span_id"] = parent_observation_id
        kwargs["trace_context"] = trace_context

    try:
        observation_context = client.start_as_current_observation(**kwargs)
        observation = observation_context.__enter__()
    except Exception as exc:
        logger.warning("Langfuse observation could not start (%s).", type(exc).__name__)
        yield None
        return

    try:
        yield observation
    except BaseException as exc:
        try:
            observation_context.__exit__(type(exc), exc, exc.__traceback__)
        except Exception as trace_exc:
            logger.warning("Langfuse observation close failed (%s).", type(trace_exc).__name__)
        raise
    else:
        try:
            observation_context.__exit__(None, None, None)
        except Exception as exc:
            logger.warning("Langfuse observation close failed (%s).", type(exc).__name__)


def flush_langfuse() -> None:
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed (%s).", type(exc).__name__)


class NodeSpan(BaseModel):
    node_name: str
    start_time: float
    end_time: Optional[float] = None
    latency_seconds: float = 0.0
    status: str = "running"
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_prompt_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class QueryTelemetry(BaseModel):
    request_id: str
    total_latency_seconds: float = 0.0
    model_name: Optional[str] = None
    total_prompt_tokens: Optional[int] = None
    total_completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    repair_count: int = 0
    spans: List[NodeSpan] = Field(default_factory=list)


class TraceContext:
    """Small local recorder used to summarize node execution without Langfuse."""

    def __init__(self, request_id: str, model_name: Optional[str] = None):
        self.request_id = request_id
        self.model_name = model_name
        self.spans: List[NodeSpan] = []
        self._active_spans: Dict[str, float] = {}
        self.start_time = time.time()

    def start_span(self, node_name: str) -> None:
        self._active_spans[node_name] = time.time()

    def end_span(
        self,
        node_name: str,
        status: str = "completed",
        usage: Optional[Dict[str, int]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> NodeSpan:
        start_t = self._active_spans.pop(node_name, time.time())
        end_t = time.time()
        prompt = (usage or {}).get("prompt_tokens")
        completion = (usage or {}).get("completion_tokens")
        total = (usage or {}).get("total_tokens")
        cached_prompt = (usage or {}).get("cached_prompt_tokens")
        if total is None and prompt is not None and completion is not None:
            total = prompt + completion
        span = NodeSpan(
            node_name=node_name,
            start_time=start_t,
            end_time=end_t,
            latency_seconds=round(end_t - start_t, 4),
            status=status,
            model=self.model_name if usage is not None else None,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cached_prompt_tokens=cached_prompt,
            cost_usd=calculate_model_cost_usd(self.model_name, prompt, completion, cached_prompt),
            details=sanitize_telemetry_payload(details or {}),
        )
        self.spans.append(span)
        return span

    def summarize(self, repair_count: int = 0) -> QueryTelemetry:
        model_spans = [span for span in self.spans if span.model]
        usage_complete = bool(model_spans) and all(span.total_tokens is not None for span in model_spans)
        prompt = sum(span.prompt_tokens or 0 for span in model_spans) if usage_complete else None
        completion = sum(span.completion_tokens or 0 for span in model_spans) if usage_complete else None
        total = sum(span.total_tokens or 0 for span in model_spans) if usage_complete else None
        costs = [span.cost_usd for span in model_spans]
        cost = round(sum(value for value in costs if value is not None), 8) if costs and all(value is not None for value in costs) else None
        return QueryTelemetry(
            request_id=self.request_id,
            total_latency_seconds=round(time.time() - self.start_time, 4),
            model_name=self.model_name,
            total_prompt_tokens=prompt,
            total_completion_tokens=completion,
            total_tokens=total,
            total_cost_usd=cost,
            repair_count=repair_count,
            spans=self.spans,
        )


def record_node_span(
    state: Dict[str, Any],
    node_name: str,
    start_time: float,
    status: str = "completed",
    usage: Optional[Dict[str, int]] = None,
    model: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Append local metrics; do not store model input/output in telemetry details."""
    spans = list(state.get("node_spans") or [])
    latency = round(time.time() - start_time, 4)
    prompt = (usage or {}).get("prompt_tokens") if usage is not None else None
    completion = (usage or {}).get("completion_tokens") if usage is not None else None
    total = (usage or {}).get("total_tokens") if usage is not None else None
    cached_prompt = (usage or {}).get("cached_prompt_tokens") if usage is not None else None
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    span = {
        "node_name": node_name,
        "latency_seconds": latency,
        "status": status,
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_prompt_tokens": cached_prompt,
        "cost_usd": calculate_model_cost_usd(model, prompt, completion, cached_prompt),
        "details": sanitize_telemetry_payload(details or {}),
    }
    spans.append(span)
    return spans


def append_duration_span(
    spans: List[Dict[str, Any]], node_name: str, latency_seconds: Optional[float], status: str = "completed"
) -> List[Dict[str, Any]]:
    """Append a child-stage timing when the parent graph node records several stages."""
    if latency_seconds is None:
        return spans
    spans.append({
        "node_name": node_name,
        "latency_seconds": round(max(0.0, float(latency_seconds)), 4),
        "status": status,
        "model": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "details": {},
    })
    return spans
