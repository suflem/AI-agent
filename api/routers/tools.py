from __future__ import annotations

from fastapi import APIRouter

from api.executor import call_tool, list_tools
from api.models import ToolCallRequest, ToolCallResponse

router = APIRouter(prefix="/tool", tags=["tool"])


@router.get("/list")
def get_tool_list():
    return {"tools": list_tools()}


@router.post("/call", response_model=ToolCallResponse)
def post_tool_call(tool: str, req: ToolCallRequest):
    return call_tool(tool=tool, args=req.args, approval=req.approval)

