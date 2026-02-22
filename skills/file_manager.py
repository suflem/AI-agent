# skills/file_manager.py
# 文件管理工具：create_file, delete_file, copy_file, rename_file, get_file_info

import os
import shutil
import time
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj):
    """Prefer workspace-relative paths in outputs for readability."""
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# ==========================================
# 1. 创建文件
# ==========================================
create_file_schema = {
    "type": "function",
    "function": {
        "name": "create_file",
        "description": (
            "【危险操作】创建新文件并写入内容。如果文件已存在则拒绝覆盖（请用 edit_file 或 write_code_file）。"
            "会自动创建所需的父目录。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "新文件路径 (如 src/utils/helper.py)"},
                "content": {"type": "string", "description": "文件内容，留空则创建空文件"}
            },
            "required": ["filepath"]
        }
    }
}


@register(create_file_schema)
def create_file(filepath: str, content: str = ""):
    try:
        path_obj, err = guard_path(filepath, must_exist=False, for_write=True)
        if err:
            return err

        if path_obj.exists():
            return f"❌ 文件已存在: {_display_path(path_obj)}。请用 edit_file 修改或先删除。"

        if not path_obj.parent.exists():
            path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(path_obj, 'w', encoding='utf-8') as f:
            f.write(content)

        size = len(content.encode('utf-8'))
        return f"✅ 已创建文件: {_display_path(path_obj)} ({size} 字节)"

    except Exception as e:
        return f"❌ 创建失败: {e}"


# ==========================================
# 2. 删除文件/目录
# ==========================================
delete_file_schema = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": (
            "【危险操作】删除文件或空目录。非空目录需设置 recursive=true 才能删除。"
            "删除不可撤销，请谨慎使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "要删除的文件或目录路径"},
                "recursive": {"type": "boolean", "description": "是否递归删除非空目录，默认 false"}
            },
            "required": ["filepath"]
        }
    }
}


@register(delete_file_schema)
def delete_file(filepath: str, recursive: bool = False):
    try:
        path_obj, err = guard_path(filepath, must_exist=True, for_write=True)
        if err:
            return err

        if path_obj.is_file():
            size = path_obj.stat().st_size
            path_obj.unlink()
            return f"✅ 已删除文件: {_display_path(path_obj)} ({size} 字节)"

        if path_obj.is_dir():
            if recursive:
                item_count = sum(len(files) for _, _, files in os.walk(path_obj))
                shutil.rmtree(path_obj)
                return f"✅ 已递归删除目录: {_display_path(path_obj)} (含 {item_count} 个文件)"
            else:
                if any(path_obj.iterdir()):
                    return f"❌ 目录非空: {_display_path(path_obj)}。设置 recursive=true 以递归删除。"
                path_obj.rmdir()
                return f"✅ 已删除空目录: {_display_path(path_obj)}"

        return f"❌ 未知路径类型: {_display_path(path_obj)}"
    except Exception as e:
        return f"❌ 删除失败: {e}"


# ==========================================
# 3. 复制文件/目录
# ==========================================
copy_file_schema = {
    "type": "function",
    "function": {
        "name": "copy_file",
        "description": "复制文件或目录到目标位置。如果目标已存在则拒绝覆盖。",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件/目录路径"},
                "destination": {"type": "string", "description": "目标路径"}
            },
            "required": ["source", "destination"]
        }
    }
}


@register(copy_file_schema)
def copy_file(source: str, destination: str):
    try:
        source_obj, err = guard_path(source, must_exist=True, for_write=False)
        if err:
            return err

        destination_obj, err = guard_path(destination, must_exist=False, for_write=True)
        if err:
            return err

        if destination_obj.exists():
            return f"❌ 目标已存在: {_display_path(destination_obj)}"

        if not destination_obj.parent.exists():
            destination_obj.parent.mkdir(parents=True, exist_ok=True)

        if source_obj.is_file():
            shutil.copy2(source_obj, destination_obj)
            size = destination_obj.stat().st_size
            return f"✅ 已复制文件: {_display_path(source_obj)} → {_display_path(destination_obj)} ({size} 字节)"
        elif source_obj.is_dir():
            shutil.copytree(source_obj, destination_obj)
            return f"✅ 已复制目录: {_display_path(source_obj)} → {_display_path(destination_obj)}"
        else:
            return f"❌ 不支持的路径类型"
    except Exception as e:
        return f"❌ 复制失败: {e}"


# ==========================================
# 4. 重命名/移动文件
# ==========================================
rename_file_schema = {
    "type": "function",
    "function": {
        "name": "rename_file",
        "description": "【危险操作】重命名或移动文件/目录。目标路径不能已存在。",
        "parameters": {
            "type": "object",
            "properties": {
                "old_path": {"type": "string", "description": "原路径"},
                "new_path": {"type": "string", "description": "新路径"}
            },
            "required": ["old_path", "new_path"]
        }
    }
}


@register(rename_file_schema)
def rename_file(old_path: str, new_path: str):
    try:
        old_obj, err = guard_path(old_path, must_exist=True, for_write=True)
        if err:
            return err

        new_obj, err = guard_path(new_path, must_exist=False, for_write=True)
        if err:
            return err

        if new_obj.exists():
            return f"❌ 目标已存在: {_display_path(new_obj)}"

        if not new_obj.parent.exists():
            new_obj.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(old_obj), str(new_obj))
        return f"✅ 已移动: {_display_path(old_obj)} → {_display_path(new_obj)}"
    except Exception as e:
        return f"❌ 移动失败: {e}"


# ==========================================
# 5. 获取文件信息
# ==========================================
get_file_info_schema = {
    "type": "function",
    "function": {
        "name": "get_file_info",
        "description": "获取文件或目录的详细信息：大小、修改时间、行数、编码等。",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "文件或目录路径"}
            },
            "required": ["filepath"]
        }
    }
}


@register(get_file_info_schema)
def get_file_info(filepath: str):
    try:
        path_obj, err = guard_path(filepath, must_exist=True, for_write=False)
        if err:
            return err

        stat = path_obj.stat()
        info = {
            "路径": str(path_obj),
            "类型": "目录" if path_obj.is_dir() else "文件",
            "大小": _format_size(stat.st_size),
            "修改时间": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "创建时间": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime)),
        }

        if path_obj.is_file():
            ext = path_obj.suffix.lower()
            info["扩展名"] = ext or "(无)"

            # 尝试获取行数
            try:
                with open(path_obj, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                info["行数"] = str(line_count)
            except (UnicodeDecodeError, PermissionError):
                info["行数"] = "(二进制或不可读)"

        elif path_obj.is_dir():
            file_count = 0
            dir_count = 0
            total_size = 0
            for root, dirs, files in os.walk(path_obj):
                dir_count += len(dirs)
                file_count += len(files)
                for f in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            info["文件数"] = str(file_count)
            info["子目录数"] = str(dir_count)
            info["总大小"] = _format_size(total_size)

        lines = [f"📋 文件信息: {_display_path(path_obj)}"]
        for k, v in info.items():
            lines.append(f"  {k}: {v}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ 获取信息失败: {e}"


def _format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
