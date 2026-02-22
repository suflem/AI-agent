from __future__ import annotations

from fastapi import APIRouter

from api.models import ToolCallRequest, ToolCallResponse
from ._helpers import run_named_tool

router = APIRouter(prefix="/feed", tags=["feed"])


@router.post("/rss", response_model=ToolCallResponse)
def post_rss_manage(req: ToolCallRequest):
    return run_named_tool("rss_manage", req)


@router.post("/wechat", response_model=ToolCallResponse)
def post_wechat_bridge(req: ToolCallRequest):
    return run_named_tool("wechat_bridge", req)


@router.post("/pipeline", response_model=ToolCallResponse)
def post_infoflow_pipeline(req: ToolCallRequest):
    return run_named_tool("infoflow_pipeline", req)


@router.post("/digest", response_model=ToolCallResponse)
def post_feed_digest(req: ToolCallRequest):
    return run_named_tool("feed_digest", req)

