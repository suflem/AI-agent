from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/grad", tags=["grad"])


@router.post("/manage", response_model=ToolCallResponse)
def post_grad_manage(req: ToolCallRequest):
    return run_named_tool("grad_school_manage", req)


@router.post("/research", response_model=ToolCallResponse)
def post_grad_research(req: ToolCallRequest):
    return run_named_tool("grad_school_research", req)


@router.post("/compare", response_model=ToolCallResponse)
def post_grad_compare(req: ToolCallRequest):
    return run_named_tool("grad_school_compare", req)


@router.post("/scorecard", response_model=ToolCallResponse)
def post_grad_scorecard(req: ToolCallRequest):
    return run_named_tool("grad_school_scorecard", req)


@router.post("/timeline", response_model=ToolCallResponse)
def post_grad_timeline(req: ToolCallRequest):
    return run_named_tool("grad_application_timeline", req)

