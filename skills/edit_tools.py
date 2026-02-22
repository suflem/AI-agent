# skills/edit_tools.py
# 精确编辑工具：支持 find & replace，不再需要整文件覆盖

import difflib
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT
from .backup_tools import create_backup

# ==========================================
# 1. 精确编辑 (Find & Replace)
# ==========================================
edit_file_schema = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "【危险操作】精确编辑文件：使用 find & replace 模式修改文件的特定部分，"
            "而非覆盖整个文件。更安全，适合修复 Bug 或小范围修改。"
            "必须先用 read_file 读取文件内容，确保 old_text 与文件中的内容完全匹配。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要编辑的文件路径 (如 test/test1.py)"
                },
                "old_text": {
                    "type": "string",
                    "description": "要被替换的原始文本片段，必须与文件中的内容完全一致（包括空格和换行）"
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的新文本"
                }
            },
            "required": ["filename", "old_text", "new_text"]
        }
    }
}


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def generate_diff(old_content: str, new_content: str, filename: str) -> str:
    """生成 unified diff 文本"""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}")
    return "".join(diff)


@register(edit_file_schema)
def edit_file(filename: str, old_text: str, new_text: str):
    """精确编辑：在文件中查找 old_text 并替换为 new_text"""
    try:
        file_obj, err = guard_path(filename, must_exist=True, for_write=True)
        if err:
            return err

        if old_text == "":
            return "❌ old_text 不能为空。"

        with open(file_obj, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查 old_text 是否存在
        count = content.count(old_text)
        if count == 0:
            return (
                f"❌ 未找到匹配文本。请先用 read_file 查看文件内容，"
                f"确保 old_text 与文件中的内容完全一致（包括空格、换行）。"
            )
        if count > 1:
            return (
                f"⚠️ 找到 {count} 处匹配。为安全起见，请提供更长的上下文使匹配唯一。"
            )

        # 执行替换
        new_content = content.replace(old_text, new_text, 1)

        # 生成 diff 供日志记录
        diff_text = generate_diff(content, new_content, _display_path(file_obj))

        # 备份并写入文件
        create_backup(file_obj)
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return f"✅ 已精确编辑 '{_display_path(file_obj)}'。\n\n变更摘要:\n```diff\n{diff_text}```"

    except Exception as e:
        return f"❌ 编辑失败: {e}"


# ==========================================
# 2. 按行插入文本
# ==========================================
insert_text_schema = {
    "type": "function",
    "function": {
        "name": "insert_text",
        "description": (
            "【危险操作】在文件的指定行号处插入文本。行号从 1 开始。"
            "如果 line_number=0 表示插入到文件开头，line_number=-1 表示追加到文件末尾。"
            "适合添加 import 语句、新函数、新配置项等场景。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件路径"},
                "line_number": {"type": "integer", "description": "在第几行之后插入 (0=文件开头, -1=文件末尾)"},
                "text": {"type": "string", "description": "要插入的文本内容"}
            },
            "required": ["filename", "line_number", "text"]
        }
    }
}


@register(insert_text_schema)
def insert_text(filename: str, line_number: int, text: str):
    """在指定行号后插入文本"""
    try:
        file_obj, err = guard_path(filename, must_exist=True, for_write=True)
        if err:
            return err

        with open(file_obj, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        old_content = "".join(lines)

        if line_number == -1:
            insert_pos = len(lines)
        elif line_number == 0:
            insert_pos = 0
        else:
            insert_pos = min(line_number, len(lines))

        new_lines_to_insert = text.splitlines(keepends=True)
        if new_lines_to_insert and not new_lines_to_insert[-1].endswith('\n'):
            new_lines_to_insert[-1] += '\n'

        lines[insert_pos:insert_pos] = new_lines_to_insert
        new_content = "".join(lines)

        create_backup(file_obj)
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(new_content)

        diff_text = generate_diff(old_content, new_content, _display_path(file_obj))
        return f"✅ 已在 '{_display_path(file_obj)}' 插入 {len(new_lines_to_insert)} 行。\n```diff\n{diff_text}```"

    except Exception as e:
        return f"❌ 插入失败: {e}"


# ==========================================
# 3. 删除指定行
# ==========================================
delete_lines_schema = {
    "type": "function",
    "function": {
        "name": "delete_lines",
        "description": (
            "【危险操作】删除文件中指定范围的行。行号从 1 开始。"
            "删除前会展示即将删除的内容供确认。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件路径"},
                "start_line": {"type": "integer", "description": "起始行号 (从1开始)"},
                "end_line": {"type": "integer", "description": "结束行号 (包含此行)"}
            },
            "required": ["filename", "start_line", "end_line"]
        }
    }
}


@register(delete_lines_schema)
def delete_lines(filename: str, start_line: int, end_line: int):
    """删除指定范围的行"""
    try:
        file_obj, err = guard_path(filename, must_exist=True, for_write=True)
        if err:
            return err

        with open(file_obj, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total = len(lines)
        if start_line < 1 or end_line < start_line or start_line > total:
            return f"❌ 无效的行号范围: {start_line}-{end_line} (文件共 {total} 行)"

        end_line = min(end_line, total)
        old_content = "".join(lines)

        deleted = lines[start_line - 1:end_line]
        del lines[start_line - 1:end_line]

        new_content = "".join(lines)

        create_backup(file_obj)
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(new_content)

        deleted_preview = "".join(deleted)
        if len(deleted_preview) > 500:
            deleted_preview = deleted_preview[:500] + "..."

        diff_text = generate_diff(old_content, new_content, _display_path(file_obj))
        return f"✅ 已删除 '{_display_path(file_obj)}' 第 {start_line}-{end_line} 行 (共 {end_line - start_line + 1} 行)。\n```diff\n{diff_text}```"

    except Exception as e:
        return f"❌ 删除失败: {e}"


# ==========================================
# 4. 批量编辑 (多处 find & replace)
# ==========================================
multi_edit_schema = {
    "type": "function",
    "function": {
        "name": "multi_edit",
        "description": (
            "【危险操作】在同一个文件中执行多处 find & replace 编辑。"
            "每个编辑项包含 old_text 和 new_text。默认事务模式：只要有一项失败就不写入。"
            "可通过 allow_partial=true 启用部分成功模式。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件路径"},
                "edits": {
                    "type": "array",
                    "description": "编辑列表，每项包含 old_text 和 new_text",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_text": {"type": "string", "description": "要替换的原文"},
                            "new_text": {"type": "string", "description": "替换后的新文本"}
                        },
                        "required": ["old_text", "new_text"]
                    }
                },
                "allow_partial": {
                    "type": "boolean",
                    "description": "是否允许部分成功。默认 false（事务模式：只要有一处失败就不写入文件）"
                }
            },
            "required": ["filename", "edits"]
        }
    }
}


@register(multi_edit_schema)
def multi_edit(filename: str, edits: list, allow_partial: bool = False):
    """批量编辑：在一个文件中执行多处 find & replace"""
    try:
        file_obj, err = guard_path(filename, must_exist=True, for_write=True)
        if err:
            return err

        if not isinstance(edits, list) or not edits:
            return "❌ edits 必须是非空数组。"

        with open(file_obj, 'r', encoding='utf-8') as f:
            original_content = f.read()

        def _apply_once(content, old_text, new_text):
            if old_text == "":
                return None, "old_text 不能为空"
            count = content.count(old_text)
            if count == 0:
                return None, "未找到匹配文本"
            if count > 1:
                return None, f"找到 {count} 处匹配，请提供更长上下文"
            return content.replace(old_text, new_text, 1), None

        content = original_content
        applied = 0
        errors = []

        for i, edit in enumerate(edits):
            old_text = edit.get("old_text", "")
            new_text = edit.get("new_text", "")
            updated, apply_err = _apply_once(content, old_text, new_text)
            if apply_err:
                msg = f"编辑#{i+1}: {apply_err}"
                if allow_partial:
                    errors.append(msg)
                    continue
                return f"❌ 批量编辑中止（事务模式）：{msg}。未写入任何变更。"

            content = updated
            applied += 1

        if applied == 0:
            return "⚠️ 没有可应用的编辑，文件未修改。"

        create_backup(file_obj)
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(content)

        diff_text = generate_diff(original_content, content, _display_path(file_obj))
        result = f"✅ 批量编辑 '{_display_path(file_obj)}': {applied}/{len(edits)} 项成功。"
        if errors:
            result += "\n⚠️ 跳过: " + "; ".join(errors)
        if diff_text:
            result += f"\n```diff\n{diff_text}```"
        return result

    except Exception as e:
        return f"❌ 批量编辑失败: {e}"
