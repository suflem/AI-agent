# core/client.py
# 🔌 连接：按 provider 初始化 OpenAI 兼容客户端

from __future__ import annotations

from typing import Any

from .config import (
    API_KEY,
    BASE_URL,
    PROVIDER_HINT,
    PROVIDER_NAME,
    PROVIDER_OPENAI_COMPATIBLE,
    resolve_provider_runtime,
)


def _build_openai_client(api_key: str, base_url: str):
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("❌ 缺少依赖 openai，请先安装: pip install openai") from e
    return OpenAI(api_key=api_key, base_url=base_url or None)


def get_runtime_provider_config(provider: str | None = None) -> dict[str, Any]:
    return resolve_provider_runtime(provider)


def get_client(provider: str | None = None):
    runtime = get_runtime_provider_config(provider)
    if not runtime.get("openai_compatible", True):
        hint = runtime.get("hint") or PROVIDER_HINT or "当前 provider 不兼容 OpenAI SDK。"
        raise RuntimeError(f"❌ provider={runtime['provider']} 暂不可用: {hint}")
    if not runtime.get("api_key"):
        raise RuntimeError(f"❌ provider={runtime['provider']} 未配置 API Key")
    return _build_openai_client(str(runtime["api_key"]), str(runtime["base_url"]))


def get_default_client():
    if not PROVIDER_OPENAI_COMPATIBLE:
        raise RuntimeError(f"❌ provider={PROVIDER_NAME} 暂不可用: {PROVIDER_HINT}")
    if not API_KEY:
        raise RuntimeError(f"❌ provider={PROVIDER_NAME} 未配置 API Key")
    return _build_openai_client(API_KEY, BASE_URL)
