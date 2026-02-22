from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("/build", response_model=ToolCallResponse)
def post_kb_build(req: ToolCallRequest):
    return run_named_tool("kb_build", req)


@router.post("/query", response_model=ToolCallResponse)
def post_kb_query(req: ToolCallRequest):
    return run_named_tool("kb_query", req)


@router.post("/manage", response_model=ToolCallResponse)
def post_kb_manage(req: ToolCallRequest):
    return run_named_tool("kb_manage", req)

