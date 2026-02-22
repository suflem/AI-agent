# skills/scheduler.py
# 个人自动化调度器：定义定时任务规则，支持手动触发和状态查看
# 设计为 cron-like 规则引擎，实际定时执行需外部触发（如系统 cron / Windows 任务计划）

import os
import json
import time
import re
from datetime import datetime
from .registry import register
from .path_safety import guard_path

SCHEDULER_DATA_REL = "data/scheduler"
JOBS_FILE = "jobs.json"
RUN_LOG_FILE = "run_log.jsonl"
MAX_LOG_LINES = 200


def _ensure_scheduler_dir():
    dir_obj, err = guard_path(SCHEDULER_DATA_REL, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not dir_obj.exists():
        dir_obj.mkdir(parents=True, exist_ok=True)
    return dir_obj


def _scheduler_file(filename):
    dir_obj = _ensure_scheduler_dir()
    file_obj, err = guard_path(str(dir_obj / filename), must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    return file_obj


def _load_jobs():
    jobs_obj = _scheduler_file(JOBS_FILE)
    if jobs_obj.exists():
        with open(jobs_obj, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def _save_jobs(jobs):
    jobs_obj = _scheduler_file(JOBS_FILE)
    with open(jobs_obj, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def _append_run_log(entry: dict):
    log_obj = _scheduler_file(RUN_LOG_FILE)
    with open(log_obj, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_run_log(max_lines=50):
    log_obj = _scheduler_file(RUN_LOG_FILE)
    if not log_obj.exists():
        return []
    lines = []
    with open(log_obj, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)
    return lines[-max_lines:]


# 预定义的任务模板（调用已有 skill 函数）
TASK_TEMPLATES = {
    "infoflow_digest": {
        "name": "信息流摘要",
        "description": "抓取 RSS 信息流并生成 AI 摘要",
        "skill": "infoflow_pipeline",
        "default_args": {"digest_type": "briefing", "taskify": True, "create_todos": False},
    },
    "check_reminders": {
        "name": "检查提醒",
        "description": "检查到期的提醒事项",
        "skill": "reminder_manage",
        "default_args": {"action": "check"},
    },
    "check_reminders_push": {
        "name": "提醒推送",
        "description": "检查到期提醒并推送到通知渠道",
        "skill": "reminder_push",
        "default_args": {},
    },
    "daily_briefing": {
        "name": "每日简报",
        "description": "获取信息流摘要 + 检查提醒 + 列出待办",
        "skill": "_composite_daily_briefing",
        "default_args": {},
    },
    "daily_briefing_push": {
        "name": "每日简报推送",
        "description": "生成每日简报并推送到通知渠道",
        "skill": "_composite_daily_briefing_push",
        "default_args": {},
    },
    "runtime_health_quick": {
        "name": "运行健康检查",
        "description": "快速健康检查，确认系统可稳定运行",
        "skill": "runtime_health",
        "default_args": {"level": "quick"},
    },
    "backup_cleanup": {
        "name": "备份清理",
        "description": "清理过期的编辑备份文件",
        "skill": "backup_clean",
        "default_args": {"keep": 3},
    },
    "notebook_digest": {
        "name": "Notebook 摘要",
        "description": "对指定 NotebookLM 笔记本生成摘要",
        "skill": "notebooklm_connector",
        "default_args": {"action": "digest", "notebook_id": "default"},
    },
}

# 支持的 schedule 格式
SCHEDULE_HELP = (
    "调度格式示例:\n"
    "  'daily 08:00'    — 每天 08:00\n"
    "  'daily 20:30'    — 每天 20:30\n"
    "  'hourly'         — 每小时\n"
    "  'manual'         — 仅手动触发\n"
    "  'weekday 09:00'  — 工作日 09:00\n"
)


def _parse_schedule(schedule_str: str):
    """Validate and normalize schedule string."""
    s = (schedule_str or "manual").strip().lower()

    if s == "manual":
        return "manual", None
    if s == "hourly":
        return "hourly", None
    m = re.fullmatch(r"daily\s+(\d{2}:\d{2})", s)
    if m:
        return f"daily {m.group(1)}", None
    m = re.fullmatch(r"weekday\s+(\d{2}:\d{2})", s)
    if m:
        return f"weekday {m.group(1)}", None

    return None, f"❌ 无效的调度格式: '{schedule_str}'\n{SCHEDULE_HELP}"


def _should_run_now(schedule: str, last_run: str) -> bool:
    """Check if a job should run based on schedule and last run time."""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")

    if schedule == "manual":
        return False

    if last_run:
        try:
            last_dt = datetime.strptime(last_run, "%Y-%m-%d %H:%M")
        except Exception:
            last_dt = datetime.min
    else:
        last_dt = datetime.min

    if schedule == "hourly":
        diff_minutes = (now - last_dt).total_seconds() / 60
        return diff_minutes >= 55

    if schedule.startswith("daily "):
        target_time = schedule.split(" ", 1)[1]
        target_str = f"{now.strftime('%Y-%m-%d')} {target_time}"
        if now_str >= target_str and last_run < target_str:
            return True
        return False

    if schedule.startswith("weekday "):
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        target_time = schedule.split(" ", 1)[1]
        target_str = f"{now.strftime('%Y-%m-%d')} {target_time}"
        if now_str >= target_str and last_run < target_str:
            return True
        return False

    return False


def _run_single_job(job: dict):
    """Execute a single scheduled job and return result string."""
    from skills import available_functions

    template_id = job.get("template", "")
    template = TASK_TEMPLATES.get(template_id, {})
    skill_name = template.get("skill", "")
    merged_args = dict(template.get("default_args", {}))
    merged_args.update(job.get("custom_args", {}))

    # Composite: daily briefing
    if skill_name == "_composite_daily_briefing":
        return _composite_daily_briefing()
    if skill_name == "_composite_daily_briefing_push":
        return _composite_daily_briefing_push()

    if skill_name not in available_functions:
        return f"❌ 技能未找到: {skill_name}"

    try:
        result = available_functions[skill_name](**merged_args)
        return str(result)
    except Exception as e:
        return f"❌ 执行失败: {e}"


def _composite_daily_briefing():
    """Composite job: info flow + reminders + todos."""
    from skills import available_functions

    parts = []

    # 1. Info flow digest
    if "infoflow_pipeline" in available_functions:
        try:
            r = available_functions["infoflow_pipeline"](
                digest_type="briefing", taskify=True, create_todos=False
            )
            parts.append(f"📰 信息流:\n{r}")
        except Exception as e:
            parts.append(f"📰 信息流失败: {e}")

    # 2. Check reminders
    if "reminder_manage" in available_functions:
        try:
            r = available_functions["reminder_manage"](action="check")
            parts.append(f"\n⏰ 提醒:\n{r}")
        except Exception as e:
            parts.append(f"\n⏰ 提醒检查失败: {e}")

    # 3. List todos
    if "todo_manage" in available_functions:
        try:
            r = available_functions["todo_manage"](action="list")
            parts.append(f"\n📋 待办:\n{r}")
        except Exception as e:
            parts.append(f"\n📋 待办列表失败: {e}")

    return "\n".join(parts) if parts else "⚠️ 无可用的子任务"


def _composite_daily_briefing_push():
    """Composite job: generate briefing then push via notify channels."""
    from skills import available_functions

    briefing = _composite_daily_briefing()
    if "notify_send" not in available_functions:
        return briefing + "\n\n⚠️ 未找到 notify_send，未执行推送。"

    try:
        push_result = available_functions["notify_send"](
            title="每日简报",
            content=briefing,
            channel_names="",
        )
        return briefing + "\n\n📨 推送结果:\n" + str(push_result)
    except Exception as e:
        return briefing + f"\n\n❌ 推送失败: {e}"


# ==========================================
# 1. 管理定时任务
# ==========================================
scheduler_manage_schema = {
    "type": "function",
    "function": {
        "name": "scheduler_manage",
        "description": (
            "管理个人自动化定时任务。支持添加、删除、列出、启用/禁用任务。"
            "任务基于预定义模板，如信息流摘要、提醒检查、每日简报等。"
            "调度格式: 'daily HH:MM' / 'weekday HH:MM' / 'hourly' / 'manual'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: add(添加), remove(删除), list(列出), enable(启用), disable(禁用), templates(查看模板)",
                },
                "job_id": {"type": "string", "description": "任务 ID (remove/enable/disable 时需要)"},
                "template": {
                    "type": "string",
                    "description": "任务模板 ID (add 时需要)，如 infoflow_digest, daily_briefing 等",
                },
                "schedule": {
                    "type": "string",
                    "description": "调度规则 (add 时需要)，如 'daily 08:00', 'hourly', 'manual'",
                },
                "custom_args": {
                    "type": "object",
                    "description": "覆盖模板默认参数的自定义参数",
                },
            },
            "required": ["action"],
        },
    },
}


@register(scheduler_manage_schema)
def scheduler_manage(
    action: str,
    job_id: str = "",
    template: str = "",
    schedule: str = "manual",
    custom_args: dict = None,
):
    """管理定时任务"""
    try:
        action = (action or "").strip().lower()

        if action == "templates":
            lines = ["📋 可用任务模板:\n"]
            for tid, tpl in TASK_TEMPLATES.items():
                lines.append(f"  [{tid}]")
                lines.append(f"    名称: {tpl['name']}")
                lines.append(f"    描述: {tpl['description']}")
                lines.append(f"    调用: {tpl['skill']}")
                if tpl.get("default_args"):
                    lines.append(f"    默认参数: {json.dumps(tpl['default_args'], ensure_ascii=False)}")
                lines.append("")
            lines.append(SCHEDULE_HELP)
            return "\n".join(lines)

        jobs = _load_jobs()

        if action == "list":
            if not jobs:
                return "📅 暂无定时任务。使用 scheduler_manage(action='templates') 查看可用模板。"

            lines = ["📅 定时任务列表:\n"]
            for j in jobs:
                status = "✅" if j.get("enabled", True) else "⏸️"
                tpl_name = TASK_TEMPLATES.get(j.get("template", ""), {}).get("name", j.get("template", "?"))
                lines.append(f"  {status} [{j['id']}] {tpl_name}")
                lines.append(f"     调度: {j.get('schedule', 'manual')}")
                lines.append(f"     上次运行: {j.get('last_run', '从未')}")
                if j.get("custom_args"):
                    lines.append(f"     自定义参数: {json.dumps(j['custom_args'], ensure_ascii=False)}")
                lines.append("")
            return "\n".join(lines)

        elif action == "add":
            if not template:
                return "❌ 请提供 template (任务模板 ID)。使用 action='templates' 查看可用模板。"
            if template not in TASK_TEMPLATES:
                return f"❌ 未知模板: {template}。可用: {', '.join(TASK_TEMPLATES.keys())}"

            schedule_norm, schedule_err = _parse_schedule(schedule)
            if schedule_err:
                return schedule_err

            new_id = job_id or f"{template}_{int(time.time()) % 100000}"
            # Check duplicate
            if any(j["id"] == new_id for j in jobs):
                return f"❌ 任务 ID 已存在: {new_id}"

            job = {
                "id": new_id,
                "template": template,
                "schedule": schedule_norm,
                "enabled": True,
                "custom_args": custom_args or {},
                "created_at": time.strftime("%Y-%m-%d %H:%M"),
                "last_run": "",
            }
            jobs.append(job)
            _save_jobs(jobs)

            tpl_name = TASK_TEMPLATES[template]["name"]
            return (
                f"✅ 已添加定时任务: {new_id}\n"
                f"  模板: {tpl_name}\n"
                f"  调度: {schedule_norm}\n"
                f"  💡 使用 scheduler_run 手动执行，或等待外部调度器触发 scheduler_tick。"
            )

        elif action == "remove":
            if not job_id:
                return "❌ 请提供 job_id"
            before = len(jobs)
            jobs = [j for j in jobs if j["id"] != job_id]
            if len(jobs) == before:
                return f"❌ 未找到任务: {job_id}"
            _save_jobs(jobs)
            return f"✅ 已删除任务: {job_id}"

        elif action in ("enable", "disable"):
            if not job_id:
                return "❌ 请提供 job_id"
            for j in jobs:
                if j["id"] == job_id:
                    j["enabled"] = (action == "enable")
                    _save_jobs(jobs)
                    state = "启用" if action == "enable" else "禁用"
                    return f"✅ 已{state}任务: {job_id}"
            return f"❌ 未找到任务: {job_id}"

        else:
            return f"❌ 未知操作: {action}。支持: add, remove, list, enable, disable, templates"

    except Exception as e:
        return f"❌ 调度器管理失败: {e}"


# ==========================================
# 2. 手动运行指定任务
# ==========================================
scheduler_run_schema = {
    "type": "function",
    "function": {
        "name": "scheduler_run",
        "description": (
            "手动立即执行一个定时任务（无论调度规则）。"
            "执行结果会记录到运行日志。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "要运行的任务 ID"},
            },
            "required": ["job_id"],
        },
    },
}


@register(scheduler_run_schema)
def scheduler_run(job_id: str):
    """手动运行任务"""
    try:
        jobs = _load_jobs()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return f"❌ 未找到任务: {job_id}"

        tpl_name = TASK_TEMPLATES.get(job.get("template", ""), {}).get("name", job.get("template", "?"))

        t_start = time.time()
        result = _run_single_job(job)
        elapsed_ms = (time.time() - t_start) * 1000

        # Update last_run
        job["last_run"] = time.strftime("%Y-%m-%d %H:%M")
        _save_jobs(jobs)

        # Log
        _append_run_log({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "job_id": job_id,
            "template": job.get("template", ""),
            "elapsed_ms": round(elapsed_ms, 1),
            "success": not str(result).startswith("❌"),
            "result_preview": str(result)[:300],
        })

        return f"🚀 任务 '{tpl_name}' ({job_id}) 执行完成 ({elapsed_ms:.0f}ms)\n\n{result}"

    except Exception as e:
        return f"❌ 任务执行失败: {e}"


# ==========================================
# 3. 自动 Tick（外部调度器调用）
# ==========================================
scheduler_tick_schema = {
    "type": "function",
    "function": {
        "name": "scheduler_tick",
        "description": (
            "调度器心跳：检查所有启用的任务，执行到期的任务。"
            "适合被外部 cron / 任务计划程序定时调用（如每分钟一次）。"
            "也可以手动调用来检查和执行所有到期任务。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


@register(scheduler_tick_schema)
def scheduler_tick():
    """调度器心跳"""
    try:
        jobs = _load_jobs()
        if not jobs:
            return "📅 暂无定时任务"

        executed = []
        skipped = []

        for job in jobs:
            if not job.get("enabled", True):
                continue

            schedule = job.get("schedule", "manual")
            last_run = job.get("last_run", "")

            if not _should_run_now(schedule, last_run):
                continue

            tpl_name = TASK_TEMPLATES.get(job.get("template", ""), {}).get("name", job.get("template", "?"))

            t_start = time.time()
            try:
                result = _run_single_job(job)
                elapsed_ms = (time.time() - t_start) * 1000
                success = not str(result).startswith("❌")

                job["last_run"] = time.strftime("%Y-%m-%d %H:%M")

                _append_run_log({
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "job_id": job["id"],
                    "template": job.get("template", ""),
                    "elapsed_ms": round(elapsed_ms, 1),
                    "success": success,
                    "result_preview": str(result)[:300],
                })

                executed.append({
                    "id": job["id"],
                    "name": tpl_name,
                    "success": success,
                    "elapsed_ms": elapsed_ms,
                    "preview": str(result)[:200],
                })

            except Exception as e:
                executed.append({
                    "id": job["id"],
                    "name": tpl_name,
                    "success": False,
                    "elapsed_ms": 0,
                    "preview": str(e)[:200],
                })

        _save_jobs(jobs)

        if not executed:
            return "📅 调度器心跳：暂无到期任务"

        lines = [f"📅 调度器心跳：执行了 {len(executed)} 个任务\n"]
        for ex in executed:
            status = "✅" if ex["success"] else "❌"
            lines.append(f"  {status} [{ex['id']}] {ex['name']} ({ex['elapsed_ms']:.0f}ms)")
            lines.append(f"     {ex['preview']}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 调度器心跳失败: {e}"


# ==========================================
# 4. 查看运行日志
# ==========================================
scheduler_log_schema = {
    "type": "function",
    "function": {
        "name": "scheduler_log",
        "description": "查看定时任务的运行日志。",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "按任务 ID 筛选，留空查看全部"},
                "last_n": {"type": "integer", "description": "显示最近 N 条，默认 10"},
            },
            "required": [],
        },
    },
}


@register(scheduler_log_schema)
def scheduler_log(job_id: str = "", last_n: int = 10):
    """查看运行日志"""
    try:
        raw_lines = _read_run_log(100)
        if not raw_lines:
            return "📋 暂无运行日志"

        records = []
        for line in raw_lines:
            try:
                r = json.loads(line)
                if job_id and r.get("job_id", "") != job_id:
                    continue
                records.append(r)
            except Exception:
                continue

        last_n = max(1, min(int(last_n) if last_n else 10, 50))
        records = records[-last_n:]

        if not records:
            return f"📋 没有匹配的运行日志"

        lines = [f"📋 任务运行日志 ({len(records)} 条):\n"]
        for r in records:
            status = "✅" if r.get("success", True) else "❌"
            lines.append(
                f"  {status} [{r.get('ts', '?')}] {r.get('job_id', '?')} "
                f"({r.get('elapsed_ms', 0):.0f}ms)"
            )
            preview = r.get("result_preview", "")
            if preview:
                lines.append(f"     {preview[:120]}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 查看日志失败: {e}"
