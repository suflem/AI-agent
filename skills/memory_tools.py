import os
from pathlib import Path
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

# 设定记忆存储路径
MEMORY_DIR = "memories"


def _display_path(path_obj: Path):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _ensure_memory_dir():
    memory_obj, err = guard_path(MEMORY_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not memory_obj.exists():
        memory_obj.mkdir(parents=True, exist_ok=True)
    return memory_obj


def _safe_topic_name(topic_name: str):
    safe_name = "".join(c for c in (topic_name or "") if c.isalnum() or c in ("_", "-"))
    return safe_name.strip()


# ==========================================
# 1. 写入记忆 (Remember)
# ==========================================
remember_schema = {
    "type": "function",
    "function": {
        "name": "save_memory",
        "description": "保存重要的信息或要求。可以选择是'永久记住'(写入Global)还是'按话题记住'(写入特定文件)。",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要记住的具体内容"
                },
                "is_global": {
                    "type": "boolean",
                    "description": "是否为全局记忆？True=每次对话都生效(如用户喜好); False=仅在需要时调用(如项目文档)"
                },
                "topic_name": {
                    "type": "string",
                    "description": "记忆的主题/文件名 (仅当 is_global=False 时必填，例如 'project_a')"
                }
            },
            "required": ["content", "is_global"]
        }
    }
}


@register(remember_schema)
def save_memory(content: str, is_global: bool, topic_name: str = None):
    """保存记忆"""
    try:
        memory_obj = _ensure_memory_dir()

        if is_global:
            # 追加到全局记忆文件
            global_obj, err = guard_path(str(memory_obj / "global.txt"), must_exist=False, for_write=True)
            if err:
                return err
            with open(global_obj, 'a', encoding='utf-8') as f:
                f.write(f"\n- {content}")
            return f"✅ 已存入全局记忆 ({_display_path(global_obj)})。下次对话我会自动记住。"
        else:
            # 存入特定主题文件
            if not topic_name:
                return "❌ 错误：非全局记忆必须提供 topic_name (主题名)。"

            # 自动处理文件名，确保安全
            safe_name = _safe_topic_name(topic_name)
            if not safe_name:
                return "❌ topic_name 无效：仅允许字母、数字、下划线、短横线。"
            file_obj, err = guard_path(str(memory_obj / f"{safe_name}.txt"), must_exist=False, for_write=True)
            if err:
                return err

            with open(file_obj, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}")
            return f"✅ 已存入话题记忆: {safe_name} ({_display_path(file_obj)})。需要时请调用 read_memory 读取。"

    except Exception as e:
        return f"❌ 记忆保存失败: {e}"


# ==========================================
# 2. 读取记忆 (Recall)
# ==========================================
recall_schema = {
    "type": "function",
    "function": {
        "name": "read_memory",
        "description": "读取特定主题的记忆内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic_name": {
                    "type": "string",
                    "description": "要读取的主题名 (例如 'project_a')"
                }
            },
            "required": ["topic_name"]
        }
    }
}


@register(recall_schema)
def read_memory(topic_name: str):
    safe_name = _safe_topic_name(topic_name)
    if not safe_name:
        return "❌ topic_name 无效：仅允许字母、数字、下划线、短横线。"

    try:
        memory_obj = _ensure_memory_dir()
    except Exception as e:
        return f"❌ 读取记忆失败: {e}"

    file_obj, err = guard_path(str(memory_obj / f"{safe_name}.txt"), must_exist=False, for_write=False)
    if err:
        return err

    if not file_obj.exists():
        return f"❌ 未找到关于 '{topic_name}' 的记忆。"

    with open(file_obj, 'r', encoding='utf-8') as f:
        return f"📄 关于 '{topic_name}' 的记忆内容:\n{f.read()}"


# ==========================================
# 3. 查看有哪些记忆 (List)
# ==========================================
list_mem_schema = {
    "type": "function",
    "function": {
        "name": "list_memories",
        "description": "列出所有已保存的特定话题记忆列表。",
        "parameters": {"type": "object", "properties": {}}
    }
}


@register(list_mem_schema)
def list_memories():
    try:
        memory_obj = _ensure_memory_dir()
        files = [
            f.stem
            for f in memory_obj.iterdir()
            if f.is_file() and f.suffix.lower() == ".txt" and f.name != "global.txt"
        ]
        if not files:
            return "📭 目前没有特定话题的记忆。"
        return f"📂 现有的记忆话题: {', '.join(sorted(files))}"
    except Exception as e:
        return f"❌ 列出记忆失败: {e}"