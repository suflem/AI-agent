from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import random
import time
from typing import Any, Callable


@dataclass
class RuntimeEvent:
    type: str
    at: float
    payload: dict[str, Any] = field(default_factory=dict)


class OpencodeRuntime:
    """A lightweight event bus inspired by OpenCode's runtime architecture."""

    def __init__(
        self,
        *,
        provider: str = "moonshot",
        model: str,
        max_steps: int,
        max_retries: int,
        build_mode: str = "balanced",
        log_path: str = "data/runtime_events.jsonl",
    ):
        self.provider = provider
        self.model = model
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.build_mode = build_mode
        self.log_path = log_path
        self._handlers: list[Callable[[RuntimeEvent], None]] = []
        self.session_id = f"sess_{int(time.time())}_{random.randint(1000, 9999)}"
        self.started_at = time.time()
        self.turns = 0
        self.agent_steps = 0
        self.tool_calls = 0
        self.tool_failures = 0
        self.input_chars = 0
        self.stream_chars = 0
        self.reasoning_chars = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self._log_write_count = 0
        self._log_rotate_bytes = 8 * 1024 * 1024
        self._ensure_log_dir()
        self.emit(
            "runtime.started",
            provider=self.provider,
            model=self.model,
            build_mode=self.build_mode,
            session_id=self.session_id,
        )

    def on(self, handler: Callable[[RuntimeEvent], None]) -> None:
        self._handlers.append(handler)

    def _ensure_log_dir(self) -> None:
        parent = os.path.dirname(self.log_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _append_log(self, event: RuntimeEvent) -> None:
        self._log_write_count += 1
        if self._log_write_count % 200 == 0:
            self._maybe_rotate_log()

        record = {
            "session_id": self.session_id,
            "at": event.at,
            "at_iso": datetime.fromtimestamp(event.at).isoformat(timespec="seconds"),
            "event": event.type,
            "payload": event.payload,
            "stats": {
                "turns": self.turns,
                "steps": self.agent_steps,
                "tool_calls": self.tool_calls,
                "tool_failures": self.tool_failures,
                "input_chars": self.input_chars,
                "stream_chars": self.stream_chars,
                "reasoning_chars": self.reasoning_chars,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "total_cost_usd": round(self.total_cost_usd, 8),
                "uptime_s": round(time.time() - self.started_at, 3),
            },
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Never let telemetry logging break the main agent loop.
            return

    def _maybe_rotate_log(self) -> None:
        try:
            if not os.path.exists(self.log_path):
                return
            if os.path.getsize(self.log_path) <= self._log_rotate_bytes:
                return
            base, ext = os.path.splitext(self.log_path)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived = f"{base}.{stamp}{ext or '.jsonl'}"
            os.replace(self.log_path, archived)
        except Exception:
            return

    def emit(self, event_type: str, **payload: Any) -> None:
        event = RuntimeEvent(type=event_type, at=time.time(), payload=payload)
        self._append_log(event)
        for handler in self._handlers:
            handler(event)

    def user_turn(self, text: str) -> None:
        self.turns += 1
        self.input_chars += len(text or "")
        self.emit("turn.user", text=text)

    def stage(self, label: str, detail: str = "") -> None:
        self.emit("status.stage", label=label, detail=detail)

    def clear_stage(self) -> None:
        self.emit("status.clear")

    def assistant_stream_start(self) -> None:
        self.emit("assistant.stream.start", model=self.model)

    def assistant_stream_token(self, token: str) -> None:
        self.stream_chars += len(token or "")
        self.emit("assistant.stream.token", token=token)

    def assistant_stream_end(self) -> None:
        self.emit("assistant.stream.end")

    def assistant_reasoning_start(self) -> None:
        self.emit("assistant.reasoning.start")

    def assistant_reasoning_token(self, token: str) -> None:
        self.reasoning_chars += len(token or "")
        self.emit("assistant.reasoning.token", token=token)

    def assistant_reasoning_end(self) -> None:
        self.emit("assistant.reasoning.end")

    def system_message(self, text: str) -> None:
        self.emit("system.message", text=text)

    def tool_plan(self, count: int) -> None:
        self.emit("tool.plan", count=count)

    def tool_call(self, name: str, args: dict[str, Any], risky: bool) -> None:
        self.tool_calls += 1
        self.emit("tool.call", name=name, args=args, risky=risky)

    def tool_result(self, result: Any, *, success: bool, elapsed_ms: float) -> None:
        if not success:
            self.tool_failures += 1
        self.emit("tool.result", result=result, success=success, elapsed_ms=elapsed_ms)

    def step_limit(self) -> None:
        self.emit("agent.limit", max_steps=self.max_steps)

    def set_agent_step(self, step: int) -> None:
        self.agent_steps = step
        self.emit("agent.step", step=step, max_steps=self.max_steps)

    def set_provider(self, provider: str) -> None:
        self.provider = provider
        self.emit("runtime.provider.changed", provider=provider)

    def set_model(self, model: str) -> None:
        self.model = model
        self.emit("runtime.model.changed", model=model)

    def set_build_mode(self, mode: str, max_steps: int) -> None:
        self.build_mode = mode
        self.max_steps = max_steps
        self.emit("runtime.mode.changed", build_mode=mode, max_steps=max_steps)

    def add_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        prompt = max(0, int(prompt_tokens or 0))
        completion = max(0, int(completion_tokens or 0))
        total = max(0, int(total_tokens or 0))
        if total <= 0:
            total = prompt + completion
        cost = max(0.0, float(cost_usd or 0.0))
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total
        self.total_cost_usd += cost
        self.emit(
            "usage.tokens",
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cost_usd=cost,
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "turns": self.turns,
            "steps": self.agent_steps,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
            "input_chars": self.input_chars,
            "stream_chars": self.stream_chars,
            "reasoning_chars": self.reasoning_chars,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 8),
            "uptime_s": round(time.time() - self.started_at, 1),
        }

    def finish(self, reason: str = "stop") -> None:
        self.emit("runtime.finished", reason=reason, stats=self.get_stats())


class RichConsoleHook:
    """Render runtime events into the existing Rich UI layer."""

    def __init__(self, ui_module: Any, runtime: OpencodeRuntime):
        self.ui = ui_module
        self.runtime = runtime
        self._last_meter = 0.0
        self._last_stage_label = "thinking"
        self._last_stage_detail = ""

    def _progress(self) -> float:
        if self.runtime.max_steps <= 0:
            return 0.0
        return min(1.0, max(0.0, self.runtime.agent_steps / float(self.runtime.max_steps)))

    def handle(self, event: RuntimeEvent) -> None:
        t = event.type
        p = event.payload
        now = event.at

        if now - self._last_meter > 0.8 and t in {"status.stage", "agent.step", "tool.result", "turn.user", "usage.tokens"}:
            self._last_meter = now
            self.ui.print_runtime_meter(self.runtime.get_stats(), progress=self._progress())

        if t == "turn.user":
            self.ui.print_user(p.get("text", ""))
            return
        if t == "status.stage":
            self._last_stage_label = p.get("label", "thinking")
            self._last_stage_detail = p.get("detail", "")
            self.ui.print_thinking(self._last_stage_label, self._last_stage_detail, progress=self._progress())
            return
        if t == "agent.step":
            self.ui.print_thinking(self._last_stage_label, self._last_stage_detail, progress=self._progress())
            return
        if t == "status.clear":
            self.ui.clear_thinking()
            return
        if t == "assistant.stream.start":
            self.ui.start_assistant_stream(p.get("model", ""))
            return
        if t == "assistant.stream.token":
            self.ui.stream_token(p.get("token", ""))
            return
        if t == "assistant.stream.end":
            self.ui.stream_end()
            return
        if t == "assistant.reasoning.start":
            self.ui.start_reasoning_stream()
            return
        if t == "assistant.reasoning.token":
            self.ui.stream_reasoning_token(p.get("token", ""))
            return
        if t == "assistant.reasoning.end":
            self.ui.end_reasoning_stream()
            return
        if t == "usage.tokens":
            self.ui.print_runtime_meter(self.runtime.get_stats(), progress=self._progress())
            return
        if t == "system.message":
            self.ui.print_system(p.get("text", ""))
            return
        if t == "tool.plan":
            self.ui.print_system(f"模型规划了 {p.get('count', 0)} 个工具调用")
            return
        if t == "tool.call":
            self.ui.print_tool_exec(p.get("name", ""), args=p.get("args", {}), risky=bool(p.get("risky")))
            return
        if t == "tool.result":
            self.ui.print_tool_result(p.get("result", ""))
            return
        if t == "agent.limit":
            self.ui.print_system(f"已达最大步数限制 ({p.get('max_steps')})，停止执行")
            return
        if t == "runtime.started":
            self.ui.print_system(
                f"runtime session: {p.get('session_id')} | provider={p.get('provider', '-')} | model={p.get('model', '-')} | mode={p.get('build_mode', '-')}"
            )
            return
        if t == "runtime.provider.changed":
            self.ui.print_system(f"provider 已切换: {p.get('provider', '-')}")
            return
        if t == "runtime.model.changed":
            self.ui.print_system(f"模型已切换: {p.get('model', '-')}")
            return
        if t == "runtime.theme.changed":
            self.ui.print_system(f"主题已切换: {p.get('theme', '-')}")
            return
        if t == "runtime.mode.changed":
            self.ui.print_system(f"build mode: {p.get('build_mode', '-')} (max_steps={p.get('max_steps', '-')})")
            return
        if t == "runtime.finished":
            stats = p.get("stats", {})
            if isinstance(stats, dict):
                self.ui.print_runtime_meter(stats, progress=self._progress())
