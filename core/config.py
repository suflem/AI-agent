# core/config.py
# ⚙️ 配置：集中管理环境变量、Provider、模型和高风险工具列表

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent.parent


def _fallback_load_env(path: str | Path) -> None:
    """Minimal .env loader when python-dotenv is unavailable."""
    path_obj = Path(path)
    if not path_obj.exists():
        return
    try:
        with path_obj.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


def _load_env_files() -> list[str]:
    cwd_env = Path.cwd() / ".env"
    root_env = ROOT_DIR / ".env"
    candidates = [cwd_env]
    if root_env != cwd_env:
        candidates.append(root_env)

    loaded: list[str] = []
    for env_path in candidates:
        if not env_path.exists():
            continue
        if load_dotenv:
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            _fallback_load_env(env_path)
        loaded.append(str(env_path))
    return loaded


LOADED_ENV_FILES = _load_env_files()


PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "moonshot": {
        "label": "Moonshot",
        "key_envs": ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-32k",
        "openai_compatible": True,
    },
    "openai": {
        "label": "OpenAI",
        "key_envs": ["OPENAI_API_KEY"],
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "openai_compatible": True,
    },
    "deepseek": {
        "label": "DeepSeek",
        "key_envs": ["DEEPSEEK_API_KEY"],
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "openai_compatible": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "key_envs": ["OPENROUTER_API_KEY"],
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4.1-mini",
        "openai_compatible": True,
    },
    "google": {
        "label": "Google (Gemini OpenAI API)",
        "key_envs": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.0-flash",
        "openai_compatible": True,
    },
    "anthropic": {
        "label": "Anthropic",
        "key_envs": ["ANTHROPIC_API_KEY"],
        "base_url": "",
        "default_model": "claude-3-7-sonnet-latest",
        "openai_compatible": False,
        "hint": "当前工程使用 OpenAI SDK 流式工具调用；Anthropic 直连暂未适配，可先用 openrouter provider 调用 Claude。",
    },
}

PROVIDER_ALIASES = {
    "kimi": "moonshot",
    "moonshot": "moonshot",
    "openai": "openai",
    "gpt": "openai",
    "deepseek": "deepseek",
    "router": "openrouter",
    "openrouter": "openrouter",
    "google": "google",
    "gemini": "google",
    "anthropic": "anthropic",
    "claude": "anthropic",
}


def normalize_provider(name: str | None) -> str:
    raw = (name or "").strip().lower()
    if not raw:
        return "moonshot"
    return PROVIDER_ALIASES.get(raw, raw)


def list_providers() -> list[str]:
    return sorted(PROVIDER_PROFILES.keys())


def _pick_key(profile: dict[str, Any]) -> str:
    override = os.getenv("AI_API_KEY", "").strip()
    if override:
        return override
    for key_env in profile.get("key_envs", []):
        value = os.getenv(str(key_env), "").strip()
        if value:
            return value
    return ""


def key_env_candidates(provider_name: str | None = None) -> list[str]:
    provider = normalize_provider(provider_name or os.getenv("AI_PROVIDER") or "moonshot")
    profile = PROVIDER_PROFILES.get(provider, PROVIDER_PROFILES["moonshot"])
    envs = [str(x) for x in profile.get("key_envs", [])]
    # AI_API_KEY is a universal override for all providers.
    return ["AI_API_KEY", *envs]


def provider_key_diagnostics(provider_name: str | None = None) -> dict[str, Any]:
    runtime = resolve_provider_runtime(provider_name)
    provider = str(runtime["provider"])
    envs = key_env_candidates(provider)
    status = {name: bool(os.getenv(name, "").strip()) for name in envs}
    selected_from = ""
    if status.get("AI_API_KEY"):
        selected_from = "AI_API_KEY"
    else:
        for name in envs:
            if name == "AI_API_KEY":
                continue
            if status.get(name):
                selected_from = name
                break
    return {
        "provider": provider,
        "model_name": str(runtime.get("model_name") or ""),
        "openai_compatible": bool(runtime.get("openai_compatible", True)),
        "base_url": str(runtime.get("base_url") or ""),
        "has_key": bool(runtime.get("api_key")),
        "selected_key_env": selected_from,
        "env_status": status,
        "loaded_env_files": list(LOADED_ENV_FILES),
        "cwd": str(Path.cwd()),
        "project_root": str(ROOT_DIR),
    }


def resolve_provider_runtime(provider_name: str | None = None) -> dict[str, Any]:
    normalized = normalize_provider(provider_name or os.getenv("AI_PROVIDER") or "moonshot")
    profile = PROVIDER_PROFILES.get(normalized, PROVIDER_PROFILES["moonshot"])
    provider = normalized if normalized in PROVIDER_PROFILES else "moonshot"
    return {
        "provider": provider,
        "label": profile["label"],
        "api_key": _pick_key(profile),
        "base_url": os.getenv("AI_BASE_URL", str(profile.get("base_url", "") or "")),
        "model_name": os.getenv("AI_MODEL", str(profile.get("default_model", ""))),
        "openai_compatible": bool(profile.get("openai_compatible", True)),
        "hint": str(profile.get("hint", "")),
    }


_runtime = resolve_provider_runtime()
PROVIDER_NAME = _runtime["provider"]
PROVIDER_LABEL = _runtime["label"]
PROVIDER_OPENAI_COMPATIBLE = _runtime["openai_compatible"]
PROVIDER_HINT = _runtime["hint"]

API_KEY = _runtime["api_key"]
BASE_URL = _runtime["base_url"]
MODEL_NAME = _runtime["model_name"]

# 🔴 高风险工具列表
RISKY_TOOLS = {
    "write_code_file",
    "move_file_by_ext",
    "delete_file",
    "save_memory",
    "run_command",
    "edit_file",
    "insert_text",
    "delete_lines",
    "multi_edit",
    "create_file",
    "rename_file",
    "video_clip",
    "undo_edit",
    "notify_manage",
    "grad_school_manage",
    "grad_school_research",
    "reminder_push",
    "runtime_smoke",
    "skill_scaffold_create",
}

if not API_KEY:
    envs = key_env_candidates(PROVIDER_NAME)
    print(f"⚠️  警告: 未找到 {PROVIDER_NAME} 的 API Key，请配置: {', '.join(envs)}")
if not PROVIDER_OPENAI_COMPATIBLE:
    hint = PROVIDER_HINT or "该 provider 暂未兼容当前 SDK。"
    print(f"⚠️  提示: {hint}")
