from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/academic", tags=["academic"])


@router.post("/write", response_model=ToolCallResponse)
def post_academic_write(req: ToolCallRequest):
    return run_named_tool("academic_write", req)


@router.post("/revise", response_model=ToolCallResponse)
def post_academic_revise(req: ToolCallRequest):
    return run_named_tool("academic_revise", req)

