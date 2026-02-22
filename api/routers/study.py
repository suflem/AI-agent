from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/study", tags=["study"])


@router.post("/pack", response_model=ToolCallResponse)
def post_study_pack(req: ToolCallRequest):
    return run_named_tool("study_pack", req)


@router.post("/explain", response_model=ToolCallResponse)
def post_kb_explain(req: ToolCallRequest):
    return run_named_tool("kb_explain", req)


@router.post("/plan", response_model=ToolCallResponse)
def post_study_plan(req: ToolCallRequest):
    return run_named_tool("study_plan_generate", req)

