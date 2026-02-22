"""Chat API: streaming conversation endpoint with tool-call support.

This is the core conversational interface — the biggest gap vs commercial assistants.
Provides SSE streaming so the frontend can show tokens as they arrive.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.config import MODEL_NAME, RISKY_TOOLS
from core.client import get_client
from skills import tools_schema, available_functions
from skills.audit_tools import log_tool_call

router = APIRouter(prefix="/chat", tags=["chat"])

# ── In-memory session store (lightweight, no DB needed) ──
_sessions: Dict[str, List[dict]] = {}
MAX_SESSIONS = 64
MAX_HISTORY_MESSAGES = 60


def _load_global_memory() -> str:
    path = "memories/global.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return f"\n\n【全局记忆】:\n{content}"
    return ""


def _system_prompt() -> str:
    return (
        "你是一个智能个人助手，拥有多种工具能力。\n"
        "\n工作原则：\n"
        "1. 先理解用户意图，必要时先用 read_file / find_file / list_dir 获取上下文。\n"
        "2. 复杂任务先调用 create_plan 制定计划，然后逐步执行，每完成一步用 update_plan 更新进度。\n"
        "3. 修改代码时优先用 edit_file (精确编辑)，只有创建新文件时才用 write_code_file。\n"
        "4. 涉及文件修改等高风险操作时，先说明要做什么再调用工具。\n"
        "5. 遇到错误时分析原因并尝试自主修复，而非直接报错。\n"
        "6. 用简洁清晰的中文回复。"
    ) + _load_global_memory()


def _get_session(session_id: str) -> List[dict]:
    if session_id not in _sessions:
        if len(_sessions) >= MAX_SESSIONS:
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[session_id] = [{"role": "system", "content": _system_prompt()}]
    return _sessions[session_id]


def _trim_history(messages: List[dict]) -> List[dict]:
    if len(messages) > MAX_HISTORY_MESSAGES + 1:
        return [messages[0]] + messages[-(MAX_HISTORY_MESSAGES):]
    return messages


# ── Request / Response models ──

class ChatRequest(BaseModel):
    session_id: str = Field(default="", description="Session ID. Empty = new session.")
    message: str = Field(..., description="User message text.")
    auto_approve: bool = Field(default=False, description="Auto-approve risky tools (for trusted callers).")


class SessionInfo(BaseModel):
    session_id: str
    message_count: int


# ── SSE streaming chat ──

def _sse_event(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """SSE streaming chat endpoint. Returns event stream with token/tool/done events."""
    session_id = req.session_id or uuid.uuid4().hex[:16]
    messages = _get_session(session_id)
    messages.append({"role": "user", "content": req.message})
    messages[:] = _trim_history(messages)

    client = get_client()

    async def generate():
        yield _sse_event("session", {"session_id": session_id})

        max_steps = 15
        step = 0

        while step < max_steps:
            step += 1

            try:
                stream = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    tools=tools_schema,
                    tool_choice="auto",
                    stream=True,
                )
            except Exception as e:
                yield _sse_event("error", {"message": f"API error: {e}"})
                return

            collected_content = []
            collected_tool_calls: Dict[int, dict] = {}
            has_tool_calls = False

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    collected_content.append(delta.content)
                    yield _sse_event("token", {"text": delta.content})

                if delta.tool_calls:
                    has_tool_calls = True
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                        if tc.id:
                            collected_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                collected_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                collected_tool_calls[idx]["arguments"] += tc.function.arguments

            full_content = "".join(collected_content)

            if not has_tool_calls:
                ai_msg = {"role": "assistant", "content": full_content or None}
                messages.append(ai_msg)
                yield _sse_event("done", {"session_id": session_id, "message_count": len(messages)})
                return

            # Build assistant message with tool_calls
            tool_calls_list = []
            for idx in sorted(collected_tool_calls.keys()):
                tc = collected_tool_calls[idx]
                tool_calls_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })

            ai_msg = {"role": "assistant", "content": full_content or None, "tool_calls": tool_calls_list}
            messages.append(ai_msg)

            # Execute tool calls
            for tc in tool_calls_list:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                is_risky = func_name in RISKY_TOOLS

                if is_risky and not req.auto_approve:
                    yield _sse_event("approval_required", {
                        "tool": func_name,
                        "args": args,
                        "tool_call_id": tc["id"],
                    })
                    result = f"⏸️ 需要用户审批: {func_name}。请在前端确认后重新发送。"
                elif func_name in available_functions:
                    yield _sse_event("tool_start", {"tool": func_name, "args": args})
                    t0 = time.time()
                    try:
                        result = str(available_functions[func_name](**args))
                    except Exception as e:
                        result = f"Error: {e}"
                    elapsed_ms = (time.time() - t0) * 1000
                    log_tool_call(func_name, args, result, elapsed_ms)
                    yield _sse_event("tool_result", {
                        "tool": func_name,
                        "result": result[:2000],
                        "elapsed_ms": round(elapsed_ms, 1),
                    })
                else:
                    result = f"Error: Tool {func_name} not found"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": result,
                })

        yield _sse_event("error", {"message": f"Reached max agent steps ({max_steps})"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions")
def list_sessions():
    """List active chat sessions."""
    return [
        {"session_id": sid, "message_count": len(msgs)}
        for sid, msgs in _sessions.items()
    ]


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a chat session."""
    if session_id in _sessions:
        del _sessions[session_id]
        return {"ok": True}
    return {"ok": False, "error": "session not found"}
