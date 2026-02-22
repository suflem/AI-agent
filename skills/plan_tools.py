# skills/plan_tools.py
# 多步规划工具：让 AI 在执行复杂任务前先列出计划

import json
import os
from .registry import register

PLAN_FILE = os.path.join("data", "current_plan.json")


def _load_plan():
    if os.path.exists(PLAN_FILE):
        try:
            with open(PLAN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"steps": [], "current_step": 0}


def _save_plan(plan):
    os.makedirs(os.path.dirname(PLAN_FILE), exist_ok=True)
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

create_plan_schema = {
    "type": "function",
    "function": {
        "name": "create_plan",
        "description": (
            "为复杂任务创建执行计划。当用户的请求涉及多个步骤时，"
            "先调用此工具列出计划，再逐步执行。每完成一步调用 update_plan 更新进度。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "任务描述"
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "计划步骤列表，按顺序排列"
                }
            },
            "required": ["task", "steps"]
        }
    }
}

update_plan_schema = {
    "type": "function",
    "function": {
        "name": "update_plan",
        "description": "更新当前计划的进度。标记某一步为已完成或失败。",
        "parameters": {
            "type": "object",
            "properties": {
                "step_index": {
                    "type": "integer",
                    "description": "步骤编号 (从 0 开始)"
                },
                "status": {
                    "type": "string",
                    "description": "状态: done / failed / skipped",
                    "enum": ["done", "failed", "skipped"]
                },
                "note": {
                    "type": "string",
                    "description": "备注信息 (可选)"
                }
            },
            "required": ["step_index", "status"]
        }
    }
}


@register(create_plan_schema)
def create_plan(task: str, steps: list):
    """创建执行计划"""
    if isinstance(steps, str):
        import json as _json
        steps = _json.loads(steps)
    plan = {
        "task": task,
        "steps": [{"desc": s, "status": "pending", "note": ""} for s in steps],
        "current_step": 0
    }
    _save_plan(plan)
    lines = [f"📋 计划: {task}", ""]
    for i, step in enumerate(plan["steps"]):
        lines.append(f"  {i}. ⬜ {step['desc']}")
    return "\n".join(lines)


@register(update_plan_schema)
def update_plan(step_index: int, status: str, note: str = ""):
    """更新计划进度"""
    plan = _load_plan()
    step_index = int(step_index)
    if not plan["steps"]:
        return "❌ 当前没有活跃的计划。请先调用 create_plan。"
    if step_index < 0 or step_index >= len(plan["steps"]):
        return f"❌ 无效步骤编号: {step_index}"

    icons = {"done": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⬜"}
    plan["steps"][step_index]["status"] = status
    plan["steps"][step_index]["note"] = note

    # 自动推进 current_step
    for i, s in enumerate(plan["steps"]):
        if s["status"] == "pending":
            plan["current_step"] = i
            break

    _save_plan(plan)

    # 渲染进度
    lines = [f"📋 计划: {plan['task']}", ""]
    for i, step in enumerate(plan["steps"]):
        icon = icons.get(step["status"], "⬜")
        suffix = f" ({step['note']})" if step["note"] else ""
        marker = " 👈" if i == plan["current_step"] and step["status"] == "pending" else ""
        lines.append(f"  {i}. {icon} {step['desc']}{suffix}{marker}")

    done_count = sum(1 for s in plan["steps"] if s["status"] == "done")
    total = len(plan["steps"])
    lines.append(f"\n进度: {done_count}/{total}")
    return "\n".join(lines)
