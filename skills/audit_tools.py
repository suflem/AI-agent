# skills/audit_tools.py
# 工具调用审计链：记录每次工具调用的全链路日志，支持查询和统计

import os
import json
import time
from pathlib import Path
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

AUDIT_LOG_REL = "data/audit_log.jsonl"
MAX_QUERY_RESULTS = 50


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _audit_file():
    file_obj, err = guard_path(AUDIT_LOG_REL, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not file_obj.parent.exists():
        file_obj.parent.mkdir(parents=True, exist_ok=True)
    return file_obj


def log_tool_call(func_name: str, args: dict, result_str: str, elapsed_ms: float = 0):
    """Append one audit record. Called from engine.py after each tool execution."""
    try:
        file_obj = _audit_file()

        # Truncate large argument values for storage
        safe_args = {}
        for k, v in (args or {}).items():
            s = str(v)
            safe_args[k] = s[:200] + "..." if len(s) > 200 else s

        # Truncate result
        result_preview = str(result_str or "")
        if len(result_preview) > 500:
            result_preview = result_preview[:500] + "..."

        record = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": time.time(),
            "tool": func_name,
            "args_summary": safe_args,
            "result_preview": result_preview,
            "success": not result_preview.startswith("❌"),
            "elapsed_ms": round(elapsed_ms, 1),
        }

        with open(file_obj, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    except Exception:
        pass  # audit must never break the main flow


def _read_audit_lines(max_lines=500):
    """Read recent audit entries."""
    file_obj = _audit_file()
    if not file_obj.exists():
        return []

    lines = []
    with open(file_obj, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)

    # Keep only the most recent entries
    return lines[-max_lines:]


# ==========================================
# 1. 查询审计日志
# ==========================================
audit_query_schema = {
    "type": "function",
    "function": {
        "name": "audit_query",
        "description": (
            "查询工具调用审计日志。可以按工具名、时间范围、成功/失败进行筛选。"
            "帮助回顾历史操作和排查问题。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "按工具名筛选（支持部分匹配）"},
                "last_n": {"type": "integer", "description": "查看最近 N 条记录，默认 20"},
                "only_errors": {"type": "boolean", "description": "仅显示失败记录，默认 false"},
                "date": {"type": "string", "description": "按日期筛选 (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
}


@register(audit_query_schema)
def audit_query(tool_name: str = "", last_n: int = 20, only_errors: bool = False, date: str = ""):
    """查询审计日志"""
    try:
        raw_lines = _read_audit_lines(500)
        if not raw_lines:
            return "📋 审计日志为空，尚无工具调用记录。"

        records = []
        for line in raw_lines:
            try:
                records.append(json.loads(line))
            except Exception:
                continue

        # Apply filters
        if tool_name:
            tool_name_lower = tool_name.lower()
            records = [r for r in records if tool_name_lower in r.get("tool", "").lower()]

        if only_errors:
            records = [r for r in records if not r.get("success", True)]

        if date:
            records = [r for r in records if r.get("ts", "").startswith(date)]

        last_n = max(1, min(int(last_n) if last_n else 20, MAX_QUERY_RESULTS))
        records = records[-last_n:]

        if not records:
            return "📋 没有匹配的审计记录"

        lines = [f"📋 审计日志 (显示 {len(records)} 条):\n"]
        for r in records:
            status = "✅" if r.get("success", True) else "❌"
            elapsed = f" ({r['elapsed_ms']}ms)" if r.get("elapsed_ms") else ""
            lines.append(f"  {status} [{r.get('ts', '?')}] {r.get('tool', '?')}{elapsed}")

            args_summary = r.get("args_summary", {})
            if args_summary:
                brief = ", ".join(f"{k}={v}" for k, v in list(args_summary.items())[:3])
                if len(brief) > 120:
                    brief = brief[:120] + "..."
                lines.append(f"     参数: {brief}")

            result = r.get("result_preview", "")
            if result:
                one_line = result.split("\n")[0][:100]
                lines.append(f"     结果: {one_line}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 查询审计日志失败: {e}"


# ==========================================
# 2. 审计统计
# ==========================================
audit_stats_schema = {
    "type": "function",
    "function": {
        "name": "audit_stats",
        "description": "统计工具调用情况：调用次数、成功率、最常用工具、平均耗时等。",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "按日期筛选 (YYYY-MM-DD)，留空统计全部"},
            },
            "required": [],
        },
    },
}


@register(audit_stats_schema)
def audit_stats(date: str = ""):
    """审计统计"""
    try:
        raw_lines = _read_audit_lines(2000)
        if not raw_lines:
            return "📊 审计日志为空"

        records = []
        for line in raw_lines:
            try:
                records.append(json.loads(line))
            except Exception:
                continue

        if date:
            records = [r for r in records if r.get("ts", "").startswith(date)]

        if not records:
            return f"📊 没有{'匹配日期 ' + date + ' 的' if date else ''}审计记录"

        total = len(records)
        successes = sum(1 for r in records if r.get("success", True))
        failures = total - successes

        # Tool frequency
        tool_counts = {}
        tool_times = {}
        for r in records:
            name = r.get("tool", "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1
            elapsed = r.get("elapsed_ms", 0)
            if elapsed:
                tool_times.setdefault(name, []).append(elapsed)

        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)

        date_label = f" ({date})" if date else ""
        lines = [f"📊 工具调用统计{date_label}:\n"]
        lines.append(f"  总调用次数: {total}")
        lines.append(f"  成功: {successes} ({successes*100//total}%)")
        lines.append(f"  失败: {failures} ({failures*100//total}%)")

        lines.append(f"\n  🔧 工具使用排行 (Top 10):")
        for name, count in sorted_tools[:10]:
            avg_ms = ""
            if name in tool_times and tool_times[name]:
                avg = sum(tool_times[name]) / len(tool_times[name])
                avg_ms = f"  avg {avg:.0f}ms"
            lines.append(f"    {count:3d}x  {name}{avg_ms}")

        # Time range
        if records:
            first_ts = records[0].get("ts", "?")
            last_ts = records[-1].get("ts", "?")
            lines.append(f"\n  📅 记录范围: {first_ts} ~ {last_ts}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 统计失败: {e}"
