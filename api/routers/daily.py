from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/daily", tags=["daily"])


@router.post("/todo", response_model=ToolCallResponse)
def post_todo(req: ToolCallRequest):
    return run_named_tool("todo_manage", req)


@router.post("/note", response_model=ToolCallResponse)
def post_note(req: ToolCallRequest):
    return run_named_tool("note_manage", req)


@router.post("/reminder", response_model=ToolCallResponse)
def post_reminder(req: ToolCallRequest):
    return run_named_tool("reminder_manage", req)

