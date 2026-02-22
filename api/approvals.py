from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional


class ApprovalStore:
    """In-memory approval tickets for risky tool calls."""

    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = int(ttl_seconds)
        self._lock = threading.Lock()
        self._items: Dict[str, Dict[str, Any]] = {}

    def _cleanup_locked(self):
        now = time.time()
        expired = [k for k, v in self._items.items() if v.get("expires_at", 0) <= now]
        for k in expired:
            self._items.pop(k, None)

    def create(self, tool: str, args: Dict[str, Any], actor: str = "ui") -> str:
        with self._lock:
            self._cleanup_locked()
            approval_id = uuid.uuid4().hex[:16]
            self._items[approval_id] = {
                "tool": tool,
                "args": args,
                "actor": actor,
                "created_at": time.time(),
                "expires_at": time.time() + self.ttl_seconds,
            }
            return approval_id

    def get(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._cleanup_locked()
            return self._items.get(approval_id)

    def pop(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._cleanup_locked()
            return self._items.pop(approval_id, None)


approval_store = ApprovalStore()

