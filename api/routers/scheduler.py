from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/manage", response_model=ToolCallResponse)
def post_scheduler_manage(req: ToolCallRequest):
    return run_named_tool("scheduler_manage", req)


@router.post("/run", response_model=ToolCallResponse)
def post_scheduler_run(req: ToolCallRequest):
    return run_named_tool("scheduler_run", req)


@router.post("/tick", response_model=ToolCallResponse)
def post_scheduler_tick(req: ToolCallRequest):
    return run_named_tool("scheduler_tick", req)


@router.post("/log", response_model=ToolCallResponse)
def post_scheduler_log(req: ToolCallRequest):
    return run_named_tool("scheduler_log", req)

