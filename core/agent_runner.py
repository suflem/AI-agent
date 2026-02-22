from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Callable

from skills import available_functions, tools_schema
from skills.audit_tools import log_tool_call

from .client import get_client, get_runtime_provider_config
from .config import MODEL_NAME, PROVIDER_NAME, RISKY_TOOLS, list_providers, provider_key_diagnostics
from .opencode_runtime import OpencodeRuntime
from .pricing import estimate_cost_usd, pricing_snapshot
from .theme_registry import (
    get_active_theme_name,
    get_theme,
    list_theme_names,
    list_themes_for_cli,
    set_active_theme_name,
)

MAX_HISTORY_ROUNDS = 30
MAX_TOOL_RETRIES = 3
DEFAULT_MAX_STEPS = 15
CHAT_HISTORY_DIR = "memories/chat_history"
CHAT_SESSION_DIR = os.path.join(CHAT_HISTORY_DIR, "sessions")
LATEST_SESSION_FILE = os.path.join(CHAT_HISTORY_DIR, "latest_session.txt")

BUILD_MODE_STEPS = {
    "fast": 8,
    "balanced": DEFAULT_MAX_STEPS,
    "deep": 24,
}


def _ensure_chat_dirs() -> None:
    os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
    os.makedirs(CHAT_SESSION_DIR, exist_ok=True)


def _serialize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serializable = []
    for msg in messages:
        if hasattr(msg, "model_dump"):
            serializable.append(msg.model_dump(exclude_none=True))
        else:
            serializable.append(msg)
    return serializable


def _extract_session_title(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if str(msg.get("role", "")) == "user":
            text = str(msg.get("content", "")).strip()
            if text:
                one_line = text.splitlines()[0].strip()
                return one_line[:48] + ("..." if len(one_line) > 48 else "")
    return "new session"


def load_global_memory() -> str:
    path = "memories/global.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return f"\n\n【全局记忆】:\n{content}"
    return ""


def save_chat_history(
    messages: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    provider_name: str = "",
    model_name: str = "",
    build_mode: str = "",
) -> None:
    _ensure_chat_dirs()
    serializable = _serialize_messages(messages)

    with open(os.path.join(CHAT_HISTORY_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

    if not session_id:
        return

    payload = {
        "session_id": session_id,
        "provider": provider_name,
        "model": model_name,
        "build_mode": build_mode,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "title": _extract_session_title(serializable),
        "messages": serializable,
    }
    session_path = os.path.join(CHAT_SESSION_DIR, f"{session_id}.json")
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(LATEST_SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_id)


def _load_session_payload(session_id: str) -> dict[str, Any] | None:
    if not session_id.strip():
        return None
    path = os.path.join(CHAT_SESSION_DIR, f"{session_id.strip()}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def load_latest_session_id() -> str:
    if os.path.exists(LATEST_SESSION_FILE):
        try:
            with open(LATEST_SESSION_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""


def load_chat_history(session_id: str | None = None) -> list[dict[str, Any]] | None:
    if session_id:
        payload = _load_session_payload(session_id)
        if payload and isinstance(payload.get("messages"), list):
            return payload["messages"]
        return None

    latest_sid = load_latest_session_id()
    if latest_sid:
        payload = _load_session_payload(latest_sid)
        if payload and isinstance(payload.get("messages"), list):
            return payload["messages"]

    filepath = os.path.join(CHAT_HISTORY_DIR, "latest.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                return loaded
        except Exception:
            return None
    return None


def list_saved_chat_sessions(limit: int = 20) -> list[dict[str, Any]]:
    _ensure_chat_dirs()
    items: list[tuple[float, dict[str, Any]]] = []
    for entry in os.scandir(CHAT_SESSION_DIR):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        try:
            with open(entry.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                continue
            messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
            updated_at = str(payload.get("updated_at", "")).strip()
            ts = entry.stat().st_mtime
            if updated_at:
                try:
                    ts = datetime.fromisoformat(updated_at).timestamp()
                except Exception:
                    pass
            items.append(
                (
                    ts,
                    {
                        "session_id": str(payload.get("session_id", entry.name[:-5])),
                        "provider": str(payload.get("provider", "")),
                        "model": str(payload.get("model", "")),
                        "build_mode": str(payload.get("build_mode", "")),
                        "updated_at": updated_at,
                        "title": str(payload.get("title", "")) or _extract_session_title(messages),
                        "message_count": len(messages),
                    },
                )
            )
        except Exception:
            continue

    ordered = [item for _, item in sorted(items, key=lambda x: x[0], reverse=True)]
    if limit > 0:
        return ordered[:limit]
    return ordered


def _usage_value(usage: Any, key: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(key) or 0)
    return int(getattr(usage, key, 0) or 0)


def _estimate_tokens(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, int(chars) // 2)


class AgentRunner:
    def __init__(
        self,
        *,
        provider_name: str = PROVIDER_NAME,
        model_name: str = MODEL_NAME,
        build_mode: str = "balanced",
        max_history_rounds: int = MAX_HISTORY_ROUNDS,
        max_tool_retries: int = MAX_TOOL_RETRIES,
        approval_callback: Callable[[str, dict[str, Any]], tuple[bool, str | None, dict[str, Any] | None]] | None = None,
        auto_approve_risky: bool = False,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.build_mode = build_mode if build_mode in BUILD_MODE_STEPS else "balanced"
        self.max_history_rounds = max(1, int(max_history_rounds))
        self.max_tool_retries = max(1, int(max_tool_retries))
        self.approval_callback = approval_callback
        self.auto_approve_risky = auto_approve_risky
        self.cancel_requested = False
        self.should_exit = False
        self.theme_name = get_active_theme_name("tui")

        self.client = get_client(self.provider_name)
        self.runtime = OpencodeRuntime(
            provider=self.provider_name,
            model=self.model_name,
            max_steps=BUILD_MODE_STEPS[self.build_mode],
            max_retries=self.max_tool_retries,
            build_mode=self.build_mode,
        )
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt()}]
        self.chat_session_id = self.runtime.session_id
        self._new_chat_seq = 1

    def _system_prompt(self) -> str:
        return (
            "你是一个智能个人助手，拥有多种工具能力。\n"
            "\n工作原则：\n"
            "1. 先理解用户意图，必要时先用 read_file / find_file / list_dir 获取上下文。\n"
            "2. 复杂任务先调用 create_plan 制定计划，然后逐步执行，每完成一步用 update_plan 更新进度。\n"
            "3. 修改代码时优先用 edit_file (精确编辑)，只有创建新文件时才用 write_code_file。\n"
            "4. 涉及文件修改等高风险操作时，先说明要做什么再调用工具。\n"
            "5. 遇到错误时分析原因并尝试自主修复，而非直接报错。\n"
            "6. 用简洁清晰的中文回复。"
        ) + load_global_memory()

    def _save_active_session(self) -> None:
        save_chat_history(
            self.messages,
            session_id=self.chat_session_id,
            provider_name=self.provider_name,
            model_name=self.model_name,
            build_mode=self.build_mode,
        )

    def new_session(self, *, announce: bool = True) -> str:
        self.chat_session_id = f"{self.runtime.session_id}_c{self._new_chat_seq}"
        self._new_chat_seq += 1
        self.messages = [{"role": "system", "content": self._system_prompt()}]
        self.runtime.system_message(f"已创建新会话: {self.chat_session_id}")
        if announce:
            self.runtime.emit("session.switched", session_id=self.chat_session_id, title="new session")
        self._save_active_session()
        return self.chat_session_id

    def switch_session(self, session_id: str) -> bool:
        payload = _load_session_payload(session_id)
        if not payload:
            self.runtime.system_message(f"未找到会话: {session_id}")
            return False
        loaded_messages = payload.get("messages")
        if not isinstance(loaded_messages, list) or len(loaded_messages) <= 0:
            self.runtime.system_message(f"会话为空或损坏: {session_id}")
            return False

        self.chat_session_id = str(payload.get("session_id") or session_id)
        self.messages = loaded_messages
        provider = str(payload.get("provider") or "").strip()
        model = str(payload.get("model") or "").strip()
        if provider:
            self.provider_name = provider
            try:
                self.client = get_client(provider)
                self.runtime.set_provider(provider)
            except Exception as e:
                self.runtime.system_message(f"provider 恢复失败，沿用当前: {e}")
        if model:
            self.model_name = model
            self.runtime.set_model(model)

        title = str(payload.get("title") or _extract_session_title(self.messages))
        self.runtime.system_message(f"已切换会话: {self.chat_session_id} · {title}")
        self.runtime.emit("session.switched", session_id=self.chat_session_id, title=title)
        self._save_active_session()
        return True

    def on(self, handler: Callable[[Any], None]) -> None:
        self.runtime.on(handler)

    def resume_history(self, resume: bool) -> bool:
        prev = load_chat_history()
        if not prev or len(prev) <= 1 or not resume:
            return False
        self.messages = prev
        latest_sid = load_latest_session_id()
        if latest_sid:
            self.chat_session_id = latest_sid
        self.runtime.system_message(
            f"已恢复 {len(self.messages) - 1} 条历史消息 · session={self.chat_session_id}"
        )
        self.runtime.emit("session.switched", session_id=self.chat_session_id, title=_extract_session_title(self.messages))
        return True

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def _clear_cancel(self) -> None:
        self.cancel_requested = False

    def slash_commands(self) -> list[str]:
        return [
            "/help",
            "/provider [name]",
            "/providers",
            "/model [name]",
            "/build [fast|balanced|deep]",
            "/approve [on|off]",
            "/sessions",
            "/session [id]",
            "/new",
            "/themes",
            "/theme [name]",
            "/doctor [provider]",
            "/stats",
            "/clear",
            "/exit",
        ]

    def _doctor_lines(self, provider_arg: str = "") -> list[str]:
        diag = provider_key_diagnostics(provider_arg or self.provider_name)
        lines = [
            f"provider={diag['provider']} model={diag['model_name']}",
            f"compatible={diag['openai_compatible']} has_key={diag['has_key']} from={diag['selected_key_env'] or '-'}",
            f"base_url={diag['base_url'] or '-'}",
            f"cwd={diag['cwd']}",
            f"project_root={diag['project_root']}",
        ]
        env_status = diag.get("env_status", {})
        if isinstance(env_status, dict):
            for name, ok in env_status.items():
                lines.append(f"{name}: {'SET' if ok else 'MISSING'}")
        loaded_files = diag.get("loaded_env_files", [])
        if loaded_files:
            lines.append("loaded_env=" + "; ".join(str(x) for x in loaded_files))
        else:
            lines.append("loaded_env=(none)")
        return lines

    def _switch_theme(self, theme_name: str) -> tuple[bool, str]:
        ok, resolved = set_active_theme_name(theme_name, "tui")
        if not ok or not resolved:
            return False, ""
        self.theme_name = resolved
        self.runtime.emit("runtime.theme.changed", theme=resolved)
        return True, resolved

    def _switch_provider(self, provider_name: str) -> str:
        runtime = get_runtime_provider_config(provider_name)
        provider = str(runtime["provider"])
        if not runtime.get("openai_compatible", True):
            hint = runtime.get("hint") or "当前 provider 不兼容。"
            return f"❌ provider={provider} 暂不可用: {hint}"
        if not runtime.get("api_key"):
            return f"❌ provider={provider} 缺少 API Key"

        self.provider_name = provider
        self.client = get_client(provider)
        self.runtime.set_provider(provider)
        default_model = str(runtime.get("model_name") or "").strip()
        if default_model:
            self.model_name = default_model
            self.runtime.set_model(default_model)
        self._save_active_session()
        return f"✅ provider 已切换到 {provider}"

    def _session_lines(self, limit: int = 12) -> list[str]:
        lines = []
        for item in list_saved_chat_sessions(limit=limit):
            sid = item["session_id"]
            mark = "*" if sid == self.chat_session_id else " "
            lines.append(
                f"{mark} {sid} | {item['provider'] or '-'} | {item['model'] or '-'} | {item['message_count']} msg | {item['title']}"
            )
        return lines

    def _handle_slash(self, text: str) -> dict[str, Any]:
        raw = text.strip()
        parts = raw[1:].split(maxsplit=1)
        cmd = (parts[0] if parts else "").lower()
        arg = (parts[1] if len(parts) > 1 else "").strip()

        if cmd in {"help", "h", "?"}:
            return {"kind": "command", "action": "help", "commands": self.slash_commands()}

        if cmd == "provider":
            if not arg:
                self.runtime.system_message(f"current provider: {self.provider_name}")
                return {"kind": "command", "action": "none"}
            msg = self._switch_provider(arg)
            self.runtime.system_message(msg)
            return {"kind": "command", "action": "none"}

        if cmd == "providers":
            self.runtime.system_message("providers: " + ", ".join(list_providers()))
            return {"kind": "command", "action": "none"}

        if cmd == "model":
            if arg:
                self.model_name = arg
                self.runtime.set_model(arg)
                snap = pricing_snapshot(arg)
                self.runtime.system_message(
                    f"pricing: prompt=${snap['prompt_usd_per_1m']}/1M, completion=${snap['completion_usd_per_1m']}/1M"
                )
                self._save_active_session()
            else:
                self.runtime.system_message(f"current model: {self.model_name}")
            return {"kind": "command", "action": "none"}

        if cmd == "build":
            if not arg:
                self.runtime.system_message(
                    f"current build mode: {self.build_mode} (max_steps={self.runtime.max_steps})"
                )
                return {"kind": "command", "action": "none"}
            mode = arg.lower()
            if mode not in BUILD_MODE_STEPS:
                self.runtime.system_message(f"未知 build mode: {mode}，可选: fast / balanced / deep")
                return {"kind": "command", "action": "none"}
            self.build_mode = mode
            self.runtime.set_build_mode(mode, BUILD_MODE_STEPS[mode])
            self._save_active_session()
            return {"kind": "command", "action": "none"}

        if cmd == "approve":
            if not arg:
                flag = "on" if self.auto_approve_risky else "off"
                self.runtime.system_message(f"auto approve: {flag}")
                return {"kind": "command", "action": "none"}
            low = arg.lower()
            if low in {"on", "true", "1"}:
                self.auto_approve_risky = True
                self.runtime.system_message("auto approve 已开启")
            elif low in {"off", "false", "0"}:
                self.auto_approve_risky = False
                self.runtime.system_message("auto approve 已关闭")
            else:
                self.runtime.system_message("用法: /approve [on|off]")
            return {"kind": "command", "action": "none"}

        if cmd == "sessions":
            lines = self._session_lines(limit=20)
            if not lines:
                self.runtime.system_message("未找到会话记录")
                return {"kind": "command", "action": "none"}
            self.runtime.system_message("saved sessions:\n" + "\n".join(lines))
            return {"kind": "command", "action": "sessions", "sessions": lines}

        if cmd == "session":
            if not arg:
                self.runtime.system_message("用法: /session <session_id>")
                return {"kind": "command", "action": "none"}
            ok = self.switch_session(arg)
            if ok:
                return {"kind": "command", "action": "session_switched", "session_id": self.chat_session_id}
            return {"kind": "command", "action": "none"}

        if cmd == "new":
            sid = self.new_session()
            return {"kind": "command", "action": "session_switched", "session_id": sid}

        if cmd == "themes":
            rows = list_themes_for_cli()
            if not rows:
                self.runtime.system_message("no themes found")
                return {"kind": "command", "action": "none"}
            return {"kind": "command", "action": "themes", "themes": rows}

        if cmd == "theme":
            if not arg:
                current = self.theme_name or get_active_theme_name("tui")
                info = get_theme(current) or {}
                label = str(info.get("label", "")).strip()
                variant = str(info.get("variant", "dark")).strip()
                self.runtime.system_message(f"current theme: {current} ({variant}) {label}")
                return {"kind": "command", "action": "none"}
            ok, resolved = self._switch_theme(arg)
            if not ok:
                available = ", ".join(list_theme_names())
                self.runtime.system_message(f"未知主题: {arg}，可用: {available}")
                return {"kind": "command", "action": "none"}
            return {"kind": "command", "action": "theme_changed", "theme": resolved}

        if cmd == "doctor":
            lines = self._doctor_lines(arg)
            return {"kind": "command", "action": "doctor", "lines": lines}

        if cmd == "stats":
            return {"kind": "command", "action": "stats", "stats": self.runtime.get_stats()}

        if cmd == "clear":
            return {"kind": "command", "action": "clear"}

        if cmd in {"exit", "quit"}:
            self.should_exit = True
            self._save_active_session()
            self.runtime.system_message("对话已保存")
            self.runtime.finish("user_exit")
            return {"kind": "command", "action": "exit"}

        self.runtime.system_message(f"未知命令: /{cmd}，输入 /help 查看可用命令")
        return {"kind": "command", "action": "none"}

    def _trim_messages(self) -> None:
        max_messages = self.max_history_rounds * 2 + 1
        if len(self.messages) > max_messages:
            self.messages = [self.messages[0]] + self.messages[-(max_messages - 1):]

    def _create_stream(self):
        base_kwargs = {
            "model": self.model_name,
            "messages": self.messages,
            "tools": tools_schema,
            "tool_choice": "auto",
            "stream": True,
        }
        try:
            return self.client.chat.completions.create(**base_kwargs, stream_options={"include_usage": True})
        except TypeError:
            return self.client.chat.completions.create(**base_kwargs)
        except Exception as e:
            if "stream_options" in str(e).lower():
                return self.client.chat.completions.create(**base_kwargs)
            raise

    def _stream_chat(self) -> tuple[dict[str, Any], bool, dict[str, int], bool]:
        stream = self._create_stream()

        collected_content: list[str] = []
        collected_tool_calls: dict[int, dict[str, str]] = {}
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        is_tool_call = False
        first_content = True
        reasoning_open = False
        reasoning_chars = 0
        canceled = False

        for chunk in stream:
            if self.cancel_requested:
                canceled = True
                break

            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage:
                usage["prompt_tokens"] = _usage_value(chunk_usage, "prompt_tokens")
                usage["completion_tokens"] = _usage_value(chunk_usage, "completion_tokens")
                usage["total_tokens"] = _usage_value(chunk_usage, "total_tokens")

            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            reasoning_text = (
                getattr(delta, "reasoning_content", None)
                or getattr(delta, "reasoning", None)
                or getattr(delta, "thinking", None)
            )
            if reasoning_text:
                if not reasoning_open:
                    self.runtime.clear_stage()
                    self.runtime.assistant_reasoning_start()
                    reasoning_open = True
                self.runtime.assistant_reasoning_token(reasoning_text)
                reasoning_chars += len(reasoning_text)

            if delta.content:
                if reasoning_open:
                    self.runtime.assistant_reasoning_end()
                    reasoning_open = False
                if first_content:
                    self.runtime.clear_stage()
                    self.runtime.assistant_stream_start()
                    first_content = False
                self.runtime.assistant_stream_token(delta.content)
                collected_content.append(delta.content)

            if delta.tool_calls:
                is_tool_call = True
                if first_content:
                    self.runtime.clear_stage()
                    first_content = False
                if reasoning_open:
                    self.runtime.assistant_reasoning_end()
                    reasoning_open = False
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "arguments": "",
                        }
                    if tc.id:
                        collected_tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            collected_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            collected_tool_calls[idx]["arguments"] += tc.function.arguments

        if reasoning_open:
            self.runtime.assistant_reasoning_end()

        full_content = "".join(collected_content)
        if full_content:
            self.runtime.assistant_stream_end()

        if usage["total_tokens"] <= 0:
            prompt_chars = sum(len(str(item.get("content", "") or "")) for item in self.messages)
            answer_chars = len(full_content) + reasoning_chars
            usage["prompt_tokens"] = _estimate_tokens(prompt_chars)
            usage["completion_tokens"] = _estimate_tokens(answer_chars)
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

        result_msg: dict[str, Any] = {"role": "assistant", "content": full_content or None}
        if collected_tool_calls:
            result_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for _, tc in sorted(collected_tool_calls.items(), key=lambda item: item[0])
            ]

        return result_msg, is_tool_call, usage, canceled

    def _approve(self, func_name: str, args: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
        if func_name not in RISKY_TOOLS:
            return True, None, args
        if self.auto_approve_risky:
            return True, None, args
        if self.approval_callback:
            return self.approval_callback(func_name, args)
        return False, "🚫 高风险工具需要审批（可用 /approve on 临时自动批准）。", None

    def _run_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        self.runtime.tool_plan(len(tool_calls))

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            result: Any = None
            risky = func_name in RISKY_TOOLS
            self.runtime.tool_call(func_name, args=args, risky=risky)
            should_run, reject_reason, new_args = self._approve(func_name, args)
            if should_run and new_args:
                args = new_args
            if not should_run:
                result = reject_reason

            t_start = time.time()
            if should_run:
                if func_name in available_functions:
                    retries = 0
                    while retries < self.max_tool_retries:
                        try:
                            self.runtime.stage(
                                "工具执行中",
                                f"{func_name} · try {retries + 1}/{self.max_tool_retries}",
                            )
                            result = available_functions[func_name](**args)
                            self.runtime.clear_stage()
                            break
                        except Exception as e:
                            retries += 1
                            if retries >= self.max_tool_retries:
                                result = f"Error (已重试{self.max_tool_retries}次): {e}"
                                self.runtime.system_message("工具执行失败，已达最大重试次数")
                            else:
                                self.runtime.system_message(
                                    f"执行出错，重试中 ({retries}/{self.max_tool_retries})..."
                                )
                                time.sleep(0.5)
                else:
                    result = f"Error: Tool {func_name} not found"
            self.runtime.clear_stage()
            elapsed_ms = (time.time() - t_start) * 1000

            log_tool_call(func_name, args, str(result), elapsed_ms)
            self.runtime.tool_result(
                result,
                success=not str(result).startswith("Error"),
                elapsed_ms=elapsed_ms,
            )

            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": str(result),
                }
            )

    def handle_input(self, user_input: str) -> dict[str, Any]:
        text = (user_input or "").lstrip("\ufeff").strip()
        if not text:
            return {"kind": "noop"}
        if text.startswith("/"):
            return self._handle_slash(text)
        if text.lower() in {"exit", "quit"}:
            self.should_exit = True
            self._save_active_session()
            self.runtime.system_message("对话已保存")
            self.runtime.finish("user_exit")
            return {"kind": "exit"}

        self.messages.append({"role": "user", "content": text})
        self.runtime.user_turn(text)
        self._trim_messages()

        self.runtime.stage("准备请求模型", "构建上下文")

        agent_steps = 0
        self._clear_cancel()
        while agent_steps < self.runtime.max_steps:
            agent_steps += 1
            self.runtime.set_agent_step(agent_steps)
            self.runtime.stage("模型推理中", f"step {agent_steps}/{self.runtime.max_steps}")

            try:
                ai_msg, has_tool_calls, usage, canceled = self._stream_chat()
                cost_usd = estimate_cost_usd(
                    self.model_name,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                self.runtime.add_usage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost_usd=cost_usd,
                )
                if canceled:
                    self.runtime.clear_stage()
                    self.runtime.system_message("已取消当前生成")
                    break
            except Exception as api_err:
                self.runtime.clear_stage()
                self.runtime.system_message(f"API 调用失败: {api_err}")
                break

            if not has_tool_calls:
                self.messages.append(ai_msg)
                break

            self.messages.append(ai_msg)
            self._run_tool_calls(ai_msg.get("tool_calls", []))
            self.runtime.stage("继续推理", f"已完成 {len(ai_msg.get('tool_calls', []))} 个工具")

        if agent_steps >= self.runtime.max_steps:
            self.runtime.step_limit()

        self._save_active_session()
        return {"kind": "turn_done", "steps": agent_steps}
