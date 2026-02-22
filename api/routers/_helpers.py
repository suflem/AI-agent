from __future__ import annotations

from api.executor import call_tool
from api.models import ToolCallRequest, ToolCallResponse


def run_named_tool(tool_name: str, req: ToolCallRequest) -> ToolCallResponse:
    return call_tool(tool=tool_name, args=req.args, approval=req.approval)

