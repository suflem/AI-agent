# skills/path_safety.py
# Unified path and file safety helpers used by file/edit tools.

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = Path(os.getenv("AI_AGENT_WORKSPACE_ROOT", str(PROJECT_ROOT))).resolve()

# Protect only truly core files to avoid accidental lockout on normal files.
PROTECTED_RELATIVE_PATHS = {
    ".env",
    "core/config.py",
    "core/engine.py",
    "core/client.py",
    "core/ui.py",
    "skills/registry.py",
    "skills/__init__.py",
}


def resolve_workspace_path(path_value: str, must_exist: bool = False):
    """Resolve path and ensure it stays inside workspace root."""
    if not path_value or not str(path_value).strip():
        return None, "❌ 路径不能为空"

    raw_path = Path(str(path_value).strip()).expanduser()
    candidate = raw_path if raw_path.is_absolute() else WORKSPACE_ROOT / raw_path

    try:
        candidate = candidate.resolve(strict=False)
    except Exception:
        return None, f"❌ 无法解析路径: {path_value}"

    try:
        candidate.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return None, (
            f"❌ 路径越界: {candidate}。"
            f"只允许在工作区内操作: {WORKSPACE_ROOT}"
        )

    if must_exist and not candidate.exists():
        return None, f"❌ 路径不存在: {candidate}"

    return candidate, None


def is_protected_path(path_obj: Path) -> bool:
    """Check if the path points to a protected core file."""
    try:
        rel = path_obj.resolve(strict=False).relative_to(WORKSPACE_ROOT).as_posix().lower()
    except Exception:
        rel = path_obj.name.lower()
    return rel in PROTECTED_RELATIVE_PATHS


def guard_path(path_value: str, must_exist: bool = False, for_write: bool = False):
    """Validate path is in workspace; optionally block writes to protected files."""
    path_obj, err = resolve_workspace_path(path_value, must_exist=must_exist)
    if err:
        return None, err

    if for_write and is_protected_path(path_obj):
        return None, f"❌ 拒绝访问：禁止修改核心文件 '{path_obj.name}'。"

    return path_obj, None
