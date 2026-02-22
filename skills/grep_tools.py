# skills/grep_tools.py
# 代码搜索工具：grep 全文搜索 + tree 目录树视图

import os
import re
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

IGNORE_DIRS = {'.git', '__pycache__', 'venv', '.idea', '.vscode', 'node_modules', 'chroma_db'}


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# ==========================================
# 1. Grep 全文搜索
# ==========================================
grep_schema = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": (
            "在文件中搜索文本内容（类似 grep 命令）。支持正则表达式。"
            "返回匹配的文件名、行号和行内容。适合搜索代码中的函数调用、变量定义、字符串等。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索模式 (支持正则表达式，如 'def run\\(' 或 'import os')"
                },
                "path": {
                    "type": "string",
                    "description": "搜索路径，默认当前目录。可以是文件或目录。"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件名过滤 (glob 模式，如 '*.py' 或 '*.js')，默认搜索所有文本文件"
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写，默认 false"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数，默认 50"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "显示匹配行的前后各多少行上下文，默认 0"
                }
            },
            "required": ["pattern"]
        }
    }
}


# 常见文本文件扩展名
TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.md', '.txt', '.rst', '.xml', '.csv', '.sql', '.sh', '.bat',
    '.env', '.gitignore', '.dockerfile', '.java', '.c', '.cpp', '.h',
    '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.vue', '.svelte',
}


def _is_text_file(filepath):
    """判断是否为文本文件"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return True
    if not ext:
        return True  # 无扩展名的文件尝试读取
    return False


def _match_glob(filename, pattern):
    """简易 glob 匹配"""
    import fnmatch
    return fnmatch.fnmatch(filename, pattern)


@register(grep_schema)
def grep(pattern: str, path: str = ".", file_pattern: str = "",
         case_sensitive: bool = False, max_results: int = 50, context_lines: int = 0):
    """全文搜索"""
    try:
        max_results = min(int(max_results) if max_results else 50, 200)
        context_lines = min(int(context_lines) if context_lines else 0, 5)

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"❌ 正则表达式错误: {e}"

        results = []
        files_searched = 0

        path_obj, err = guard_path(path, must_exist=True, for_write=False)
        if err:
            return err

        # 如果搜索的是单个文件
        if path_obj.is_file():
            files_to_search = [str(path_obj)]
        else:
            files_to_search = []
            for root, dirs, files in os.walk(path_obj):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                for f in files:
                    fp = os.path.join(root, f)
                    if file_pattern and not _match_glob(f, file_pattern):
                        continue
                    if not file_pattern and not _is_text_file(fp):
                        continue
                    files_to_search.append(fp)

        for filepath in files_to_search:
            if len(results) >= max_results:
                break

            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                files_searched += 1

                for i, line in enumerate(lines):
                    if regex.search(line):
                        match_entry = {
                            "file": _display_path(filepath),
                            "line_num": i + 1,
                            "content": line.rstrip()
                        }

                        # 添加上下文
                        if context_lines > 0:
                            ctx_start = max(0, i - context_lines)
                            ctx_end = min(len(lines), i + context_lines + 1)
                            context = []
                            for j in range(ctx_start, ctx_end):
                                prefix = ">" if j == i else " "
                                context.append(f"  {prefix} {j+1:4d}│ {lines[j].rstrip()}")
                            match_entry["context"] = "\n".join(context)

                        results.append(match_entry)
                        if len(results) >= max_results:
                            break

            except (PermissionError, OSError):
                continue

        if not results:
            return f"🔍 未找到匹配: '{pattern}' (已搜索 {files_searched} 个文件)"

        # 格式化输出
        output = [f"🔍 搜索 '{pattern}' → 找到 {len(results)} 处匹配 (搜索了 {files_searched} 个文件):\n"]

        current_file = None
        for r in results:
            if r["file"] != current_file:
                current_file = r["file"]
                output.append(f"📄 {current_file}")

            if "context" in r:
                output.append(r["context"])
            else:
                output.append(f"  {r['line_num']:4d}│ {r['content']}")

        if len(results) >= max_results:
            output.append(f"\n⚠️ 结果已截断，仅显示前 {max_results} 条。")

        return "\n".join(output)
    except Exception as e:
        return f"❌ 搜索失败: {e}"


# ==========================================
# 2. Tree 目录树视图
# ==========================================
tree_schema = {
    "type": "function",
    "function": {
        "name": "tree",
        "description": (
            "以树形结构展示目录层级，类似 tree 命令。"
            "可以帮助快速了解项目结构。支持深度限制和过滤。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径，默认当前目录"},
                "max_depth": {"type": "integer", "description": "最大显示深度，默认 3"},
                "show_files": {"type": "boolean", "description": "是否显示文件，默认 true"},
                "show_hidden": {"type": "boolean", "description": "是否显示隐藏文件/目录，默认 false"},
                "file_pattern": {"type": "string", "description": "文件名过滤 (glob 模式，如 '*.py')"}
            },
            "required": []
        }
    }
}


@register(tree_schema)
def tree(path: str = ".", max_depth: int = 3, show_files: bool = True,
         show_hidden: bool = False, file_pattern: str = ""):
    """树形展示目录结构"""
    try:
        max_depth = min(int(max_depth) if max_depth else 3, 6)

        path_obj, err = guard_path(path, must_exist=True, for_write=False)
        if err:
            return err
        if not path_obj.is_dir():
            return f"❌ 不是有效目录: {_display_path(path_obj)}"

        lines = [f"📁 {_display_path(path_obj)}"]
        stats = {"dirs": 0, "files": 0}

        def _tree_recursive(dir_path, prefix, depth):
            if depth > max_depth:
                return

            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                lines.append(f"{prefix}└── [权限不足]")
                return

            # 分离文件和目录
            dirs = []
            files = []
            for entry in entries:
                if not show_hidden and entry.startswith('.'):
                    continue
                if entry in IGNORE_DIRS:
                    continue

                full = os.path.join(dir_path, entry)
                if os.path.isdir(full):
                    dirs.append(entry)
                elif show_files:
                    if file_pattern:
                        if _match_glob(entry, file_pattern):
                            files.append(entry)
                    else:
                        files.append(entry)

            all_items = [(d, True) for d in dirs] + [(f, False) for f in files]
            total = len(all_items)

            for i, (name, is_dir) in enumerate(all_items):
                is_last = (i == total - 1)
                connector = "└── " if is_last else "├── "
                extension = "    " if is_last else "│   "

                full_path = os.path.join(dir_path, name)

                if is_dir:
                    stats["dirs"] += 1
                    lines.append(f"{prefix}{connector}📁 {name}/")
                    _tree_recursive(full_path, prefix + extension, depth + 1)
                else:
                    stats["files"] += 1
                    size = os.path.getsize(full_path)
                    size_str = _format_size_short(size)
                    lines.append(f"{prefix}{connector}{name} ({size_str})")

        _tree_recursive(str(path_obj), "", 1)
        lines.append(f"\n📊 共 {stats['dirs']} 个目录, {stats['files']} 个文件")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 目录树生成失败: {e}"


def _format_size_short(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f}KB"
    else:
        return f"{size_bytes/1024/1024:.1f}MB"
