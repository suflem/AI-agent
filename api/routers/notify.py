from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/notify", tags=["notify"])


@router.post("/manage", response_model=ToolCallResponse)
def post_notify_manage(req: ToolCallRequest):
    return run_named_tool("notify_manage", req)


@router.post("/send", response_model=ToolCallResponse)
def post_notify_send(req: ToolCallRequest):
    return run_named_tool("notify_send", req)


@router.post("/reminder-push", response_model=ToolCallResponse)
def post_reminder_push(req: ToolCallRequest):
    return run_named_tool("reminder_push", req)

