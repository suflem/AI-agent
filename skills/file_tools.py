# skills/file_tools.py
import os
import shutil
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# 定义这个工具的说明书 (Schema)
move_file_schema = {
    "type": "function",
    "function": {
        "name": "move_file_by_ext",
        "description": "移动文件，支持指定源文件夹和目标文件夹",
        "parameters": {
            "type": "object",

            "properties": {
                "extension": {"type": "string", "description": "文件后缀名 (不带点)"},
                "target_folder": {"type": "string", "description": "目标文件夹路径"},
                "source_folder": {"type": "string", "description": "源文件夹路径 (默认当前目录)"}
            },
            "required": ["extension", "target_folder"]
        }
    }
}

# 使用装饰器注册！
@register(move_file_schema)
def move_file_by_ext(extension: str, target_folder: str, source_folder: str = "."):
    try:
        extension = (extension or "").strip().lstrip(".").lower()
        if not extension:
            return "❌ extension 不能为空"

        source_obj, err = guard_path(source_folder or ".", must_exist=True, for_write=False)
        if err:
            return err
        if not source_obj.is_dir():
            return f"❌ 源路径不是目录: {_display_path(source_obj)}"

        target_obj, err = guard_path(target_folder, must_exist=False, for_write=True)
        if err:
            return err
        if not target_obj.exists():
            target_obj.mkdir(parents=True, exist_ok=True)
        elif not target_obj.is_dir():
            return f"❌ 目标路径不是目录: {_display_path(target_obj)}"

        moved = 0
        skipped = 0
        for item in source_obj.iterdir():
            if not item.is_file():
                continue
            if item.suffix.lower() != f".{extension}":
                continue

            dst = target_obj / item.name
            if dst.exists():
                skipped += 1
                continue

            shutil.move(str(item), str(dst))
            moved += 1

        return (
            f"✅ 已移动 {moved} 个 .{extension} 文件"
            f" ({_display_path(source_obj)} → {_display_path(target_obj)})"
            f"；跳过 {skipped} 个同名文件"
        )
    except Exception as e:
        return f"❌ 移动失败: {e}"