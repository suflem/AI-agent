# skills/daily_tools.py
# 日常信息管理工具：待办事项、笔记、提醒

import os
import json
import time
from pathlib import Path
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

DATA_DIR = "data"


def _display_path(path_obj: Path):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _safe_note_title(title: str) -> str:
    return "".join(c for c in (title or "") if c.isalnum() or c in " _-").strip()


def _ensure_data_dir():
    data_obj, err = guard_path(DATA_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not data_obj.exists():
        data_obj.mkdir(parents=True, exist_ok=True)
    return data_obj


def _load_json(filename, default=None):
    data_obj = _ensure_data_dir()
    file_obj, err = guard_path(str(data_obj / filename), must_exist=False, for_write=False)
    if err:
        return default if default is not None else {}

    if file_obj.exists():
        try:
            with open(file_obj, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


def _save_json(filename, data):
    data_obj = _ensure_data_dir()
    file_obj, err = guard_path(str(data_obj / filename), must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    with open(file_obj, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==========================================
# 1. 待办事项管理
# ==========================================
todo_manage_schema = {
    "type": "function",
    "function": {
        "name": "todo_manage",
        "description": (
            "管理待办事项列表。支持添加、完成、删除、列出待办。"
            "数据持久化保存在 data/todos.json。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: add(添加), done(标记完成), delete(删除), list(列出), clear_done(清除已完成)"
                },
                "content": {"type": "string", "description": "待办内容 (add 时必填)"},
                "todo_id": {"type": "integer", "description": "待办 ID (done/delete 时需要)"},
                "priority": {"type": "string", "description": "优先级: high/medium/low，默认 medium"},
                "category": {"type": "string", "description": "分类标签，如 '工作'、'学习'、'生活'"}
            },
            "required": ["action"]
        }
    }
}


@register(todo_manage_schema)
def todo_manage(action: str, content: str = "", todo_id: int = 0,
                priority: str = "medium", category: str = ""):
    try:
        todos = _load_json("todos.json", [])

        if action == "add":
            if not content:
                return "❌ 请提供待办内容"
            new_id = max([t.get("id", 0) for t in todos], default=0) + 1
            todo = {
                "id": new_id,
                "content": content,
                "priority": priority,
                "category": category,
                "done": False,
                "created": time.strftime("%Y-%m-%d %H:%M"),
                "completed": None
            }
            todos.append(todo)
            _save_json("todos.json", todos)
            return f"✅ 已添加待办 #{new_id}: {content}"

        elif action == "done":
            todo_id = int(todo_id) if todo_id else 0
            for t in todos:
                if t["id"] == todo_id:
                    t["done"] = True
                    t["completed"] = time.strftime("%Y-%m-%d %H:%M")
                    _save_json("todos.json", todos)
                    return f"✅ 已完成待办 #{todo_id}: {t['content']}"
            return f"❌ 未找到待办 #{todo_id}"

        elif action == "delete":
            todo_id = int(todo_id) if todo_id else 0
            before = len(todos)
            todos = [t for t in todos if t["id"] != todo_id]
            if len(todos) == before:
                return f"❌ 未找到待办 #{todo_id}"
            _save_json("todos.json", todos)
            return f"✅ 已删除待办 #{todo_id}"

        elif action == "list":
            if not todos:
                return "📋 待办列表为空"

            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            lines = ["📋 待办事项列表:\n"]

            pending = [t for t in todos if not t.get("done")]
            done = [t for t in todos if t.get("done")]

            if pending:
                lines.append("── 未完成 ──")
                for t in pending:
                    icon = priority_icon.get(t.get("priority", "medium"), "🟡")
                    cat = f" [{t['category']}]" if t.get("category") else ""
                    lines.append(f"  {icon} #{t['id']} {t['content']}{cat}")

            if done:
                lines.append(f"\n── 已完成 ({len(done)}) ──")
                for t in done[-5:]:  # 只显示最近5个
                    lines.append(f"  ✅ #{t['id']} {t['content']} ({t.get('completed', '')})")

            lines.append(f"\n📊 总计: {len(pending)} 未完成, {len(done)} 已完成")
            return "\n".join(lines)

        elif action == "clear_done":
            before = len(todos)
            todos = [t for t in todos if not t.get("done")]
            cleared = before - len(todos)
            _save_json("todos.json", todos)
            return f"✅ 已清除 {cleared} 条已完成待办"

        else:
            return f"❌ 未知操作: {action}。支持: add, done, delete, list, clear_done"

    except Exception as e:
        return f"❌ 待办管理失败: {e}"


# ==========================================
# 2. 笔记管理
# ==========================================
note_manage_schema = {
    "type": "function",
    "function": {
        "name": "note_manage",
        "description": (
            "管理笔记。支持创建、追加、查看、搜索、列出笔记。"
            "每个笔记是一个独立文件，保存在 data/notes/ 目录下。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: create(创建), append(追加), read(读取), search(搜索), list(列出), delete(删除)"
                },
                "title": {"type": "string", "description": "笔记标题 (作为文件名)"},
                "content": {"type": "string", "description": "笔记内容"},
                "query": {"type": "string", "description": "搜索关键词 (search 时使用)"}
            },
            "required": ["action"]
        }
    }
}


@register(note_manage_schema)
def note_manage(action: str, title: str = "", content: str = "", query: str = ""):
    try:
        notes_dir_obj, err = guard_path(os.path.join(DATA_DIR, "notes"), must_exist=False, for_write=True)
        if err:
            return err
        if not notes_dir_obj.exists():
            notes_dir_obj.mkdir(parents=True, exist_ok=True)

        if action == "create":
            if not title or not content:
                return "❌ 请提供标题和内容"
            safe_title = _safe_note_title(title)
            if not safe_title:
                return "❌ 笔记标题无效"
            note_obj = notes_dir_obj / f"{safe_title}.md"
            header = f"# {title}\n\n创建时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
            with open(note_obj, 'w', encoding='utf-8') as f:
                f.write(header + content)
            return f"✅ 笔记已创建: {_display_path(note_obj)}"

        elif action == "append":
            if not title or not content:
                return "❌ 请提供标题和追加内容"
            safe_title = _safe_note_title(title)
            if not safe_title:
                return "❌ 笔记标题无效"
            note_obj = notes_dir_obj / f"{safe_title}.md"
            if not note_obj.exists():
                return f"❌ 笔记不存在: {safe_title}"
            timestamp = time.strftime('%Y-%m-%d %H:%M')
            with open(note_obj, 'a', encoding='utf-8') as f:
                f.write(f"\n\n---\n\n[{timestamp}]\n\n{content}")
            return f"✅ 已追加到笔记: {safe_title}"

        elif action == "read":
            if not title:
                return "❌ 请提供笔记标题"
            safe_title = _safe_note_title(title)
            if not safe_title:
                return "❌ 笔记标题无效"
            note_obj = notes_dir_obj / f"{safe_title}.md"
            if not note_obj.exists():
                return f"❌ 笔记不存在: {safe_title}"
            with open(note_obj, 'r', encoding='utf-8') as f:
                text = f.read()
            if len(text) > 5000:
                text = text[:5000] + "\n\n... (已截断)"
            return f"📝 {text}"

        elif action == "search":
            if not query:
                return "❌ 请提供搜索关键词"
            results = []
            for fname in os.listdir(notes_dir_obj):
                if not fname.endswith('.md'):
                    continue
                note_obj = notes_dir_obj / fname
                with open(note_obj, 'r', encoding='utf-8') as f:
                    text = f.read()
                if query.lower() in text.lower():
                    # 找到包含关键词的行
                    for i, line in enumerate(text.split('\n')):
                        if query.lower() in line.lower():
                            results.append(f"  📄 {fname}:{i+1} → {line.strip()}")
                            break
            if not results:
                return f"🔍 未找到包含 '{query}' 的笔记"
            return f"🔍 搜索 '{query}' 找到 {len(results)} 条匹配:\n" + "\n".join(results)

        elif action == "list":
            files = [f for f in os.listdir(notes_dir_obj) if f.endswith('.md')]
            if not files:
                return "📝 暂无笔记"
            lines = ["📝 笔记列表:\n"]
            for f in sorted(files):
                note_obj = notes_dir_obj / f
                size = note_obj.stat().st_size
                mtime = time.strftime("%m-%d %H:%M", time.localtime(note_obj.stat().st_mtime))
                lines.append(f"  📄 {f} ({size}B, {mtime})")
            return "\n".join(lines)

        elif action == "delete":
            if not title:
                return "❌ 请提供笔记标题"
            safe_title = _safe_note_title(title)
            if not safe_title:
                return "❌ 笔记标题无效"
            note_obj = notes_dir_obj / f"{safe_title}.md"
            if not note_obj.exists():
                return f"❌ 笔记不存在: {safe_title}"
            os.remove(note_obj)
            return f"✅ 已删除笔记: {safe_title}"

        else:
            return f"❌ 未知操作: {action}。支持: create, append, read, search, list, delete"

    except Exception as e:
        return f"❌ 笔记管理失败: {e}"


# ==========================================
# 3. 提醒管理
# ==========================================
reminder_schema = {
    "type": "function",
    "function": {
        "name": "reminder_manage",
        "description": (
            "管理提醒事项。支持添加、查看、删除提醒。"
            "提醒存储在 data/reminders.json 中。实际的定时通知需要外部调度器支持。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: add(添加), list(列出), delete(删除), check(检查到期)"},
                "content": {"type": "string", "description": "提醒内容"},
                "remind_time": {"type": "string", "description": "提醒时间 (格式: YYYY-MM-DD HH:MM)"},
                "reminder_id": {"type": "integer", "description": "提醒 ID (delete 时需要)"}
            },
            "required": ["action"]
        }
    }
}


@register(reminder_schema)
def reminder_manage(action: str, content: str = "", remind_time: str = "", reminder_id: int = 0):
    try:
        reminders = _load_json("reminders.json", [])

        if action == "add":
            if not content or not remind_time:
                return "❌ 请提供提醒内容和时间"
            # 验证时间格式
            import re as _re
            if not _re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", remind_time.strip()):
                return "❌ 时间格式必须为 YYYY-MM-DD HH:MM，例如 2025-03-01 09:00"
            remind_time = remind_time.strip()
            new_id = max([r.get("id", 0) for r in reminders], default=0) + 1
            reminder = {
                "id": new_id,
                "content": content,
                "remind_time": remind_time,
                "created": time.strftime("%Y-%m-%d %H:%M"),
                "triggered": False
            }
            reminders.append(reminder)
            _save_json("reminders.json", reminders)
            return f"✅ 已添加提醒 #{new_id}: {content} (时间: {remind_time})"

        elif action == "list":
            if not reminders:
                return "⏰ 暂无提醒"
            lines = ["⏰ 提醒列表:\n"]
            now = time.strftime("%Y-%m-%d %H:%M")
            for r in sorted(reminders, key=lambda x: x.get("remind_time", "")):
                status = "✅" if r.get("triggered") else ("🔴" if r["remind_time"] <= now else "🟡")
                lines.append(f"  {status} #{r['id']} [{r['remind_time']}] {r['content']}")
            return "\n".join(lines)

        elif action == "delete":
            reminder_id = int(reminder_id) if reminder_id else 0
            before = len(reminders)
            reminders = [r for r in reminders if r["id"] != reminder_id]
            if len(reminders) == before:
                return f"❌ 未找到提醒 #{reminder_id}"
            _save_json("reminders.json", reminders)
            return f"✅ 已删除提醒 #{reminder_id}"

        elif action == "check":
            now = time.strftime("%Y-%m-%d %H:%M")
            due = [r for r in reminders if not r.get("triggered") and r["remind_time"] <= now]
            if not due:
                return "✅ 暂无到期提醒"
            lines = [f"🔔 有 {len(due)} 条到期提醒:\n"]
            for r in due:
                r["triggered"] = True
                lines.append(f"  🔔 #{r['id']} {r['content']} (设定于 {r['remind_time']})")
            _save_json("reminders.json", reminders)
            return "\n".join(lines)

        else:
            return f"❌ 未知操作: {action}。支持: add, list, delete, check"

    except Exception as e:
        return f"❌ 提醒管理失败: {e}"
