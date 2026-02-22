from __future__ import annotations

from fastapi import APIRouter, Query

from api.executor import call_tool, list_tools
from api.models import ApprovalPayload, SmokeRequest, ToolCallResponse
from core.config import RISKY_TOOLS

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=ToolCallResponse)
def get_health(level: str = Query(default="quick", pattern="^(quick|full)$")):
    return call_tool(
        tool="runtime_health",
        args={"level": level},
        approval=ApprovalPayload(dry_run=False, confirm=True),
    )


@router.post("/smoke", response_model=ToolCallResponse)
def post_smoke(req: SmokeRequest):
    return call_tool(
        tool="runtime_smoke",
        args={"cleanup": req.cleanup},
        approval=ApprovalPayload(dry_run=True, confirm=False),
    )


@router.get("/registry")
def get_registry():
    """Return full tool registry with risk metadata for dynamic frontend rendering."""
    tools = list_tools()
    risky = set(RISKY_TOOLS)

    # Group tools by module prefix (e.g. "todo_manage" → "daily", "edit_file" → "edit")
    from skills import registry as _reg
    module_map: dict = {}
    for schema in _reg.tools_schema:
        fn = schema.get("function", {})
        name = fn.get("name", "")
        # Find which module registered this tool
        func = _reg.executable_functions.get(name)
        module_name = getattr(func, "__module__", "").replace("skills.", "") if func else "unknown"
        module_map[name] = module_name

    return {
        "tools": tools,
        "modules": module_map,
        "risky_tools": sorted(risky),
    }

