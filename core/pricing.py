from __future__ import annotations

import os
from typing import Any


# USD / 1M tokens (fallback estimation only).
# Unknown models default to 0.
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4.1-mini": {"prompt": 0.8, "completion": 3.2},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.6},
    "gpt-4.1": {"prompt": 2.0, "completion": 8.0},
    "moonshot-v1-8k": {"prompt": 0.25, "completion": 0.25},
    "moonshot-v1-32k": {"prompt": 0.5, "completion": 0.5},
    "moonshot-v1-128k": {"prompt": 1.0, "completion": 1.0},
    "deepseek-chat": {"prompt": 0.27, "completion": 1.1},
    "gemini-2.0-flash": {"prompt": 0.1, "completion": 0.4},
}


def _env_float(name: str, default: float = 0.0) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _resolve_rate(model_name: str) -> tuple[float, float]:
    prompt_rate = _env_float("AI_PROMPT_USD_PER_1M", 0.0)
    completion_rate = _env_float("AI_COMPLETION_USD_PER_1M", 0.0)
    if prompt_rate > 0 or completion_rate > 0:
        return prompt_rate, completion_rate

    model = (model_name or "").strip().lower()
    if not model:
        return 0.0, 0.0

    for key, rates in MODEL_PRICING_USD_PER_1M.items():
        if model.startswith(key.lower()):
            return float(rates.get("prompt", 0.0)), float(rates.get("completion", 0.0))
    return 0.0, 0.0


def estimate_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = _resolve_rate(model_name)
    if prompt_rate <= 0 and completion_rate <= 0:
        return 0.0

    p = max(0, int(prompt_tokens or 0))
    c = max(0, int(completion_tokens or 0))
    cost = (p / 1_000_000.0) * prompt_rate + (c / 1_000_000.0) * completion_rate
    return round(cost, 8)


def pricing_snapshot(model_name: str) -> dict[str, Any]:
    prompt_rate, completion_rate = _resolve_rate(model_name)
    return {
        "model": model_name,
        "prompt_usd_per_1m": prompt_rate,
        "completion_usd_per_1m": completion_rate,
    }
