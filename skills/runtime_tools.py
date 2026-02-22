# skills/runtime_tools.py
# 运行稳定性工具：健康检查 + 冒烟测试

import json
import os
import platform
import time
import uuid
from pathlib import Path

from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _bool_mark(ok: bool):
    return "✅" if ok else "❌"


def _warn_mark(ok: bool):
    return "✅" if ok else "⚠️"


def _safe_load_json(path_obj: Path):
    if not path_obj.exists():
        return None, None
    try:
        with open(path_obj, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def _get_env_value(key: str):
    v = (os.getenv(key) or "").strip()
    if v:
        return v
    # Fallback: read .env directly when current process didn't load it.
    try:
        env_obj, err = guard_path(".env", must_exist=False, for_write=False)
        if err or (not env_obj.exists()):
            return ""
        with open(env_obj, "r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if not text or text.startswith("#") or "=" not in text:
                    continue
                k, val = text.split("=", 1)
                if k.strip() == key:
                    return val.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def _ensure_writeable_dir(rel_path: str):
    dir_obj, err = guard_path(rel_path, must_exist=False, for_write=True)
    if err:
        return False, err
    if not dir_obj.exists():
        dir_obj.mkdir(parents=True, exist_ok=True)
    probe = dir_obj / f".probe_{int(time.time())}.tmp"
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        probe.unlink(missing_ok=True)
        return True, str(dir_obj)
    except Exception as e:
        return False, str(e)


runtime_health_schema = {
    "type": "function",
    "function": {
        "name": "runtime_health",
        "description": (
            "运行健康检查。用于在上线前快速确认配置、目录可写性、关键依赖、数据文件完整性。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "检查级别: quick(快速) / full(包含更多检查)，默认 quick"
                }
            },
            "required": []
        }
    }
}


@register(runtime_health_schema)
def runtime_health(level: str = "quick"):
    try:
        level = (level or "quick").strip().lower()
        full = level == "full"

        lines = []
        issues = []
        warns = []

        # 1) 基础环境
        lines.append("🩺 Runtime Health")
        lines.append(f"- Python: {platform.python_version()} ({platform.system()} {platform.release()})")
        lines.append(f"- Workspace: {WORKSPACE_ROOT}")

        # 2) 关键目录可写
        for rel in ["data", "memories", "memories/chat_history", "data/knowledge_base", "data/notifications"]:
            ok, msg = _ensure_writeable_dir(rel)
            lines.append(f"- {_bool_mark(ok)} write-check `{rel}`: {msg}")
            if not ok:
                issues.append(f"{rel} 不可写: {msg}")

        # 3) 配置与 API key
        key = _get_env_value("KIMI_API_KEY")
        key_ok = bool(key)
        lines.append(f"- {_warn_mark(key_ok)} KIMI_API_KEY: {'set' if key_ok else 'empty'}")
        if not key_ok:
            warns.append("缺少 KIMI_API_KEY，涉及 LLM 的工具将不可用。")

        serper_ok = bool(_get_env_value("SERPER_API_KEY"))
        bing_ok = bool(_get_env_value("BING_API_KEY"))
        search_ok = serper_ok or bing_ok
        lines.append(
            f"- {_warn_mark(search_ok)} search key: "
            f"SERPER_API_KEY={'set' if serper_ok else 'empty'}, "
            f"BING_API_KEY={'set' if bing_ok else 'empty'}"
        )
        if not search_ok:
            warns.append("未配置搜索 API Key（SERPER_API_KEY / BING_API_KEY），联网搜索可能失败。")

        # 4) 关键依赖检测
        deps = [
            ("openai", True),
            ("rich", True),
            ("psutil", True),
            ("chromadb", True),
            ("dotenv", True),
            ("PyPDF2", False),
            ("pptx", False),  # python-pptx
        ]
        for dep, required in deps:
            try:
                __import__(dep)
                ok = True
            except Exception:
                ok = False
            mark = _bool_mark(ok) if required else _warn_mark(ok)
            lines.append(f"- {mark} dependency `{dep}`: {'ok' if ok else 'missing'}")
            if required and not ok:
                issues.append(f"缺少必需依赖: {dep}")
            if (not required) and (not ok):
                warns.append(f"缺少可选依赖: {dep}（相关功能受限）")

        # 5) 技能注册与核心能力存在性
        from skills import available_functions, tools_schema
        tool_count = len(tools_schema)
        lines.append(f"- ✅ registered tools: {tool_count}")
        core_tools = [
            "read_file", "edit_file", "run_command", "kb_build", "kb_query",
            "rss_manage", "infoflow_pipeline", "grad_school_manage",
            "grad_school_scorecard", "grad_application_timeline",
            "notify_manage", "notify_send",
        ]
        missing = [x for x in core_tools if x not in available_functions]
        lines.append(f"- {_bool_mark(len(missing) == 0)} core tools present: {len(core_tools) - len(missing)}/{len(core_tools)}")
        if missing:
            issues.append("缺失核心工具: " + ", ".join(missing))

        # 6) 数据文件完整性检查（JSON）
        json_files = [
            "data/todos.json",
            "data/reminders.json",
            "data/notifications/channels.json",
            "data/grad_school/profiles.json",
            "data/scheduler/jobs.json",
        ]
        for rel in json_files:
            path_obj, err = guard_path(rel, must_exist=False, for_write=False)
            if err:
                lines.append(f"- ⚠️ json `{rel}` path error: {err}")
                warns.append(f"{rel} 路径异常: {err}")
                continue
            data, jerr = _safe_load_json(path_obj)
            if not path_obj.exists():
                lines.append(f"- ✅ json `{rel}`: not-created (ok)")
            elif jerr:
                lines.append(f"- ❌ json `{rel}`: broken ({jerr})")
                issues.append(f"{rel} JSON 损坏: {jerr}")
            else:
                dtype = type(data).__name__
                lines.append(f"- ✅ json `{rel}`: ok ({dtype})")

        # 7) full 级别：执行只读/轻写检查
        if full:
            lines.append("")
            lines.append("🔬 Full checks")
            checks = [
                ("todo_manage(list)", lambda f: f["todo_manage"](action="list")),
                ("reminder_manage(list)", lambda f: f["reminder_manage"](action="list")),
                ("scheduler_manage(list)", lambda f: f["scheduler_manage"](action="list")),
                ("notify_manage(list)", lambda f: f["notify_manage"](action="list")),
                ("kb_manage(list)", lambda f: f["kb_manage"](action="list")),
            ]
            for name, fn in checks:
                try:
                    result = fn(available_functions)
                    ok = isinstance(result, str) and (not result.startswith("❌"))
                    lines.append(f"- {_warn_mark(ok)} {name}: {'ok' if ok else str(result)[:120]}")
                    if not ok:
                        warns.append(f"{name} 返回异常: {str(result)[:120]}")
                except Exception as e:
                    lines.append(f"- ❌ {name}: {e}")
                    issues.append(f"{name} 异常: {e}")

        lines.append("")
        if issues:
            lines.append(f"结论: ❌ 不健康（{len(issues)} 个阻断问题，{len(warns)} 个警告）")
        elif warns:
            lines.append(f"结论: ⚠️ 基本健康（0 阻断，{len(warns)} 个警告）")
        else:
            lines.append("结论: ✅ 健康（无阻断问题）")

        if issues:
            lines.append("阻断问题:")
            lines.extend([f"- {x}" for x in issues[:20]])
        if warns:
            lines.append("警告:")
            lines.extend([f"- {x}" for x in warns[:20]])

        return "\n".join(lines)
    except Exception as e:
        return f"❌ runtime_health 失败: {e}"


runtime_smoke_schema = {
    "type": "function",
    "function": {
        "name": "runtime_smoke",
        "description": (
            "运行端到端冒烟测试（会写入并清理少量测试数据），用于发布前稳定性验收。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cleanup": {"type": "boolean", "description": "是否自动清理测试数据，默认 true"}
            },
            "required": []
        }
    }
}


@register(runtime_smoke_schema)
def runtime_smoke(cleanup: bool = True):
    try:
        from skills import available_functions

        cleanup = bool(cleanup)
        run_id = uuid.uuid4().hex[:8]
        tag = f"smoke_{run_id}"
        lines = [f"🧪 Runtime Smoke ({tag})"]
        failures = []

        # 1) todo add/list/delete
        todo_id = None
        try:
            r1 = available_functions["todo_manage"](action="add", content=f"[{tag}] smoke todo")
            lines.append(f"- todo add: {r1}")
            m = None
            if isinstance(r1, str):
                import re as _re
                m = _re.search(r"#(\d+)", r1)
            if m:
                todo_id = int(m.group(1))
            r2 = available_functions["todo_manage"](action="list")
            ok = isinstance(r2, str) and (tag in r2 or "待办事项列表" in r2)
            lines.append(f"- todo list: {'ok' if ok else 'unexpected'}")
            if not ok:
                failures.append("todo list 异常")
        except Exception as e:
            failures.append(f"todo 测试失败: {e}")

        # 2) grad_school upsert/remove
        try:
            rs = available_functions["grad_school_manage"](
                action="upsert",
                school=f"SmokeU-{tag}",
                program="MSCS",
                intake="2099 Fall",
                info_json='{"application_deadline":"2099-12-01","min_gpa":3.0}'
            )
            lines.append(f"- grad upsert: {rs}")
        except Exception as e:
            failures.append(f"grad upsert 失败: {e}")

        # 3) notify channel upsert/send/remove (console)
        channel_name = f"ch_{tag}"
        try:
            rn1 = available_functions["notify_manage"](
                action="upsert",
                channel_name=channel_name,
                channel_type="console",
                enabled=True,
                config_json="{}",
            )
            lines.append(f"- notify upsert: {rn1}")
            rn2 = available_functions["notify_send"](
                title=f"Smoke {tag}",
                content="runtime smoke test",
                channel_names=channel_name,
            )
            ok = isinstance(rn2, str) and ("1/1" in rn2 or "✅" in rn2)
            lines.append(f"- notify send: {'ok' if ok else rn2}")
            if not ok:
                failures.append("notify send 失败")
        except Exception as e:
            failures.append(f"notify 测试失败: {e}")

        # cleanup
        if cleanup:
            try:
                if todo_id:
                    available_functions["todo_manage"](action="delete", todo_id=todo_id)
            except Exception:
                pass
            try:
                available_functions["grad_school_manage"](
                    action="remove",
                    school=f"SmokeU-{tag}",
                    program="MSCS",
                )
            except Exception:
                pass
            try:
                available_functions["notify_manage"](
                    action="remove",
                    channel_name=channel_name,
                )
            except Exception:
                pass
            lines.append("- cleanup: done")

        if failures:
            lines.append(f"结论: ❌ 失败 ({len(failures)} 项)")
            lines.extend([f"- {x}" for x in failures[:20]])
        else:
            lines.append("结论: ✅ 通过")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ runtime_smoke 失败: {e}"
