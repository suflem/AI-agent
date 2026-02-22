# skills/external_ai.py
# 外部 AI API 接口：支持多提供商调用 + 适配器架构

import os
import json
import urllib.request
import urllib.error
from .registry import register

# ==========================================
# AI 提供商配置 (可在 .env 中扩展)
# ==========================================
AI_PROVIDERS = {
    "kimi": {
        "adapter": "openai_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "base_url_env": "KIMI_BASE_URL",
        "api_key_env": "KIMI_API_KEY",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-32k",
    },
    "openai": {
        "adapter": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "base_url_env": "OPENAI_BASE_URL",
        "api_key_env": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "adapter": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    "claude": {
        "adapter": "anthropic_messages",
        "base_url": "https://api.anthropic.com/v1",
        "base_url_env": "CLAUDE_BASE_URL",
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
        "default_model": "claude-sonnet-4-20250514",
    },
    "zhipu": {
        "adapter": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "base_url_env": "ZHIPU_BASE_URL",
        "api_key_env": "ZHIPU_API_KEY",
        "models": ["glm-4-flash", "glm-4"],
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "adapter": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "base_url_env": "QWEN_BASE_URL",
        "api_key_env": "QWEN_API_KEY",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "default_model": "qwen-turbo",
    },
    "manus": {
        "adapter": "openai_compatible",
        "base_url": "",
        "base_url_env": "MANUS_BASE_URL",
        "api_key_env": "MANUS_API_KEY",
        "models": ["manus-default"],
        "default_model": "manus-default",
    },
}


def _resolve_provider(provider: str):
    if provider not in AI_PROVIDERS:
        return None, f"❌ 未知的 AI 提供商: {provider}。可选: {', '.join(AI_PROVIDERS.keys())}"

    config = dict(AI_PROVIDERS[provider])
    api_key = os.getenv(config["api_key_env"], "").strip()
    if not api_key:
        return None, f"❌ 缺少 API Key: 请在 .env 中配置 {config['api_key_env']}"

    env_base = os.getenv(config.get("base_url_env", ""), "").strip()
    base_url = env_base or config.get("base_url", "")
    if not base_url:
        return None, (
            f"❌ {provider} 缺少 BASE_URL。请在 .env 中配置 {config.get('base_url_env', 'BASE_URL')}"
        )

    config["api_key"] = api_key
    config["resolved_base_url"] = base_url.rstrip("/")
    return config, None


def _format_usage(usage: dict):
    if not usage:
        return ""
    return (
        f"\n\n📊 Token 用量: 输入 {usage.get('prompt_tokens', '?')}"
        f" + 输出 {usage.get('completion_tokens', '?')}"
        f" = {usage.get('total_tokens', '?')}"
    )


def _call_openai_compatible(config, model, messages, temperature, max_tokens):
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("缺少依赖 openai。请安装: pip install openai")

    client = OpenAI(api_key=config["api_key"], base_url=config["resolved_base_url"])
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=float(temperature),
        max_tokens=int(max_tokens),
    )
    usage_obj = response.usage
    usage = None
    if usage_obj:
        usage = {
            "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
            "completion_tokens": getattr(usage_obj, "completion_tokens", None),
            "total_tokens": getattr(usage_obj, "total_tokens", None),
        }
    return response.choices[0].message.content or "", usage


def _call_anthropic_messages(config, model, prompt, system_prompt, temperature, max_tokens):
    url = f"{config['resolved_base_url']}/messages"
    payload = {
        "model": model,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content_parts = []
    for item in data.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            content_parts.append(item.get("text", ""))

    usage_data = data.get("usage", {})
    usage = {
        "prompt_tokens": usage_data.get("input_tokens"),
        "completion_tokens": usage_data.get("output_tokens"),
        "total_tokens": (usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0)),
    }
    return "\n".join(content_parts).strip(), usage


# ==========================================
# 1. 调用外部 AI 模型
# ==========================================
call_ai_schema = {
    "type": "function",
    "function": {
        "name": "call_ai",
        "description": (
            "调用外部 AI 模型完成任务。支持: kimi, openai, deepseek, claude, zhipu, qwen, manus。"
            "使用提供商适配器提高稳定性；API Key 和 BASE_URL 均通过 .env 配置。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "发送给 AI 的提示词/问题"},
                "provider": {
                    "type": "string",
                    "description": "AI 提供商 (kimi/openai/deepseek/claude/zhipu/qwen/manus)，默认 kimi",
                },
                "model": {"type": "string", "description": "指定模型名，留空则使用默认模型"},
                "system_prompt": {"type": "string", "description": "系统提示词"},
                "temperature": {"type": "number", "description": "温度参数 (0-2)，默认 0.7"},
                "max_tokens": {"type": "integer", "description": "最大输出 token 数，默认 4096"},
            },
            "required": ["prompt"],
        },
    },
}


@register(call_ai_schema)
def call_ai(
    prompt: str,
    provider: str = "kimi",
    model: str = "",
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """调用外部 AI 模型"""
    try:
        provider = provider.lower().strip()
        config, err = _resolve_provider(provider)
        if err:
            return err

        model = model or config["default_model"]
        adapter = config.get("adapter", "openai_compatible")

        if adapter == "anthropic_messages":
            content, usage = _call_anthropic_messages(
                config=config,
                model=model,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            content, usage = _call_openai_compatible(
                config=config,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return f"🤖 [{provider}/{model}] 回复:\n\n{content}{_format_usage(usage)}"
    except urllib.error.HTTPError as e:
        return f"❌ AI 调用失败 ({provider}): HTTP {e.code} - {e.reason}"
    except Exception as e:
        return f"❌ AI 调用失败 ({provider}): {e}"


# ==========================================
# 2. 列出可用的 AI 提供商
# ==========================================
list_ai_providers_schema = {
    "type": "function",
    "function": {
        "name": "list_ai_providers",
        "description": "列出所有外部 AI 提供商状态，包括 API Key、BASE_URL 和适配器类型。",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register(list_ai_providers_schema)
def list_ai_providers():
    """列出可用的 AI 提供商"""
    lines = ["🤖 外部 AI 提供商列表:\n"]

    for name, config in AI_PROVIDERS.items():
        api_key = os.getenv(config["api_key_env"], "").strip()
        env_base = os.getenv(config.get("base_url_env", ""), "").strip()
        base_url = env_base or config.get("base_url", "")
        ready = bool(api_key and base_url)
        status = "✅ 已配置" if ready else "❌ 未配置"
        models = ", ".join(config["models"])

        lines.append(f"  [{name}] {status}")
        lines.append(f"    adapter: {config.get('adapter', 'openai_compatible')}")
        lines.append(f"    key_env: {config['api_key_env']}")
        lines.append(f"    base_env: {config.get('base_url_env', '(无)')}")
        lines.append(f"    base_url: {base_url or '(待在 .env 配置)'}")
        lines.append(f"    默认模型: {config['default_model']}")
        lines.append(f"    可用模型: {models}")
        lines.append("")

    lines.append("💡 建议：将 API Key / BASE_URL 都放在 .env，不要写入代码或 JSON 文件。")
    return "\n".join(lines)
