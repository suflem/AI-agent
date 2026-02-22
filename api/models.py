from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalPayload(BaseModel):
    dry_run: bool = Field(default=False, description="Whether to request approval preview only.")
    confirm: bool = Field(default=False, description="Whether this call confirms a prior approval request.")
    approval_id: str = Field(default="", description="Approval ticket id returned by a dry-run call.")
    actor: str = Field(default="ui", description="Caller identity for audit trace.")


class ToolCallRequest(BaseModel):
    args: Dict[str, Any] = Field(default_factory=dict)
    approval: ApprovalPayload = Field(default_factory=ApprovalPayload)


class ToolCallResponse(BaseModel):
    success: bool
    status: str = Field(description="ok | needs_approval | error")
    tool: str
    result: Optional[str] = None
    error: Optional[str] = None
    approval_id: Optional[str] = None
    preview: Optional[str] = None
    duration_ms: float = 0.0


class SmokeRequest(BaseModel):
    cleanup: bool = True

