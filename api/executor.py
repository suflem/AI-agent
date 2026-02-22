from __future__ import annotations

import json
import time
from typing import Any, Dict

from core.config import RISKY_TOOLS
from skills import available_functions, tools_schema

from .approvals import approval_store
from .models import ApprovalPayload, ToolCallResponse


def _preview_args(args: Dict[str, Any]) -> str:
    return json.dumps(args, ensure_ascii=False, indent=2)


def list_tools():
    items = []
    risky = set(RISKY_TOOLS)
    for schema in tools_schema:
        fn = schema.get("function", {})
        name = fn.get("name", "")
        items.append({
            "name": name,
            "description": fn.get("description", ""),
            "risky": name in risky,
            "parameters": fn.get("parameters", {}),
        })
    return sorted(items, key=lambda x: x["name"])


def call_tool(tool: str, args: Dict[str, Any], approval: ApprovalPayload) -> ToolCallResponse:
    t0 = time.time()
    if tool not in available_functions:
        return ToolCallResponse(
            success=False,
            status="error",
            tool=tool,
            error=f"Tool not found: {tool}",
            duration_ms=(time.time() - t0) * 1000,
        )

    is_risky = tool in RISKY_TOOLS
    approval = approval or ApprovalPayload()
    args = args or {}

    if is_risky:
        # Step 1: dry-run or plain call without confirmation -> return approval ticket.
        if approval.dry_run or (not approval.confirm):
            approval_id = approval_store.create(tool=tool, args=args, actor=approval.actor)
            return ToolCallResponse(
                success=False,
                status="needs_approval",
                tool=tool,
                approval_id=approval_id,
                preview=_preview_args(args),
                result="Approval required before execution.",
                duration_ms=(time.time() - t0) * 1000,
            )

        # Step 2: confirmed execution with ticket.
        if not approval.approval_id:
            return ToolCallResponse(
                success=False,
                status="error",
                tool=tool,
                error="Missing approval_id for risky tool confirmation.",
                duration_ms=(time.time() - t0) * 1000,
            )
        ticket = approval_store.pop(approval.approval_id)
        if not ticket:
            return ToolCallResponse(
                success=False,
                status="error",
                tool=tool,
                error="Approval ticket not found or expired.",
                duration_ms=(time.time() - t0) * 1000,
            )
        if ticket.get("tool") != tool:
            return ToolCallResponse(
                success=False,
                status="error",
                tool=tool,
                error="Approval ticket tool mismatch.",
                duration_ms=(time.time() - t0) * 1000,
            )
        if ticket.get("args", {}) != args:
            return ToolCallResponse(
                success=False,
                status="error",
                tool=tool,
                error="Approval ticket args mismatch. Re-run dry-run to get a fresh ticket.",
                duration_ms=(time.time() - t0) * 1000,
            )

    try:
        result = available_functions[tool](**args)
        return ToolCallResponse(
            success=True,
            status="ok",
            tool=tool,
            result=str(result),
            duration_ms=(time.time() - t0) * 1000,
        )
    except Exception as e:
        return ToolCallResponse(
            success=False,
            status="error",
            tool=tool,
            error=str(e),
            duration_ms=(time.time() - t0) * 1000,
        )

