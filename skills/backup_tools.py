# skills/backup_tools.py
# 编辑备份与撤销系统：每次文件编辑前自动备份，支持查看历史和回滚

import os
import json
import time
import shutil
from pathlib import Path
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

BACKUP_DIR = "data/backups"
BACKUP_INDEX = "data/backups/_index.json"
MAX_BACKUPS_PER_FILE = 10


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _ensure_backup_dir():
    dir_obj, err = guard_path(BACKUP_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not dir_obj.exists():
        dir_obj.mkdir(parents=True, exist_ok=True)
    return dir_obj


def _load_index():
    idx_obj, err = guard_path(BACKUP_INDEX, must_exist=False, for_write=False)
    if err:
        return {}
    if idx_obj and idx_obj.exists():
        try:
            with open(idx_obj, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_index(index):
    idx_obj, err = guard_path(BACKUP_INDEX, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not idx_obj.parent.exists():
        idx_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(idx_obj, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _file_key(file_path: Path) -> str:
    """Generate a stable key for indexing backups by file."""
    try:
        return file_path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except Exception:
        return str(file_path.resolve())


def create_backup(file_path) -> str:
    """Create a backup of file_path before editing. Returns backup path or empty string on failure.
    Called by edit_tools and other write tools before modifying files.
    """
    try:
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists() or not file_path.is_file():
            return ""

        backup_dir = _ensure_backup_dir()
        key = _file_key(file_path)
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Build safe backup filename: flatten path separators
        safe_name = key.replace("/", "__").replace("\\", "__")
        backup_name = f"{safe_name}.{timestamp}.bak"

        backup_obj, err = guard_path(str(backup_dir / backup_name), must_exist=False, for_write=True)
        if err:
            return ""

        shutil.copy2(str(file_path), str(backup_obj))

        # Update index
        index = _load_index()
        entries = index.setdefault(key, [])
        entries.append({
            "backup_file": str(backup_obj.name),
            "timestamp": timestamp,
            "size": file_path.stat().st_size,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Prune old backups
        if len(entries) > MAX_BACKUPS_PER_FILE:
            removed = entries[:-MAX_BACKUPS_PER_FILE]
            entries[:] = entries[-MAX_BACKUPS_PER_FILE:]
            for old in removed:
                old_path = backup_dir / old["backup_file"]
                if old_path.exists():
                    old_path.unlink()

        index[key] = entries
        _save_index(index)
        return str(backup_obj)

    except Exception:
        return ""


# ==========================================
# 1. 查看备份历史
# ==========================================
backup_history_schema = {
    "type": "function",
    "function": {
        "name": "backup_history",
        "description": (
            "查看文件的编辑备份历史。每次通过 edit_file / multi_edit 等工具"
            "修改文件时都会自动创建备份，此工具可以列出指定文件的所有备份版本。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "要查看备份历史的文件路径"},
            },
            "required": ["filepath"],
        },
    },
}


@register(backup_history_schema)
def backup_history(filepath: str):
    """查看文件的备份历史"""
    try:
        file_obj, err = guard_path(filepath, must_exist=False, for_write=False)
        if err:
            return err

        key = _file_key(file_obj)
        index = _load_index()
        entries = index.get(key, [])

        if not entries:
            return f"📂 文件 '{_display_path(file_obj)}' 暂无备份记录"

        lines = [f"📂 文件 '{_display_path(file_obj)}' 的备份历史 ({len(entries)} 个版本):\n"]
        for i, entry in enumerate(reversed(entries)):
            age_label = "最新" if i == 0 else f"#{i+1}"
            size_kb = entry.get("size", 0) / 1024
            lines.append(
                f"  [{age_label}] {entry['created_at']}  "
                f"({size_kb:.1f} KB)  {entry['backup_file']}"
            )

        lines.append(f"\n💡 使用 undo_edit 可以恢复到任意版本。")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 查看备份历史失败: {e}"


# ==========================================
# 2. 撤销编辑 (恢复备份)
# ==========================================
undo_edit_schema = {
    "type": "function",
    "function": {
        "name": "undo_edit",
        "description": (
            "【危险操作】撤销文件编辑，恢复到之前的备份版本。"
            "默认恢复到最近一次备份。可通过 version 指定恢复到第几个历史版本 (1=最新备份)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "要恢复的文件路径"},
                "version": {
                    "type": "integer",
                    "description": "恢复到第几个版本 (1=最新备份, 2=倒数第二个, ...)，默认 1",
                },
            },
            "required": ["filepath"],
        },
    },
}


@register(undo_edit_schema)
def undo_edit(filepath: str, version: int = 1):
    """撤销编辑，恢复备份"""
    try:
        file_obj, err = guard_path(filepath, must_exist=False, for_write=True)
        if err:
            return err

        key = _file_key(file_obj)
        index = _load_index()
        entries = index.get(key, [])

        if not entries:
            return f"❌ 文件 '{_display_path(file_obj)}' 没有可用的备份"

        version = max(1, min(int(version) if version else 1, len(entries)))
        target = entries[-version]

        backup_dir = _ensure_backup_dir()
        backup_file = backup_dir / target["backup_file"]

        if not backup_file.exists():
            return f"❌ 备份文件缺失: {target['backup_file']}"

        # Before restoring, create a backup of the current version (safety net)
        if file_obj.exists():
            create_backup(file_obj)

        shutil.copy2(str(backup_file), str(file_obj))

        return (
            f"✅ 已恢复 '{_display_path(file_obj)}' 到版本 {target['created_at']}\n"
            f"  备份来源: {target['backup_file']}\n"
            f"  原始大小: {target.get('size', '?')} 字节\n"
            f"  💡 恢复前的版本也已自动备份。"
        )

    except Exception as e:
        return f"❌ 撤销失败: {e}"


# ==========================================
# 3. 清理备份
# ==========================================
backup_clean_schema = {
    "type": "function",
    "function": {
        "name": "backup_clean",
        "description": "清理文件备份。可以清理指定文件的备份，或清理所有备份。",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "要清理的文件路径，留空则清理全部"},
                "keep": {"type": "integer", "description": "每个文件保留最近几个备份，默认 3"},
            },
            "required": [],
        },
    },
}


@register(backup_clean_schema)
def backup_clean(filepath: str = "", keep: int = 3):
    """清理备份"""
    try:
        keep = max(0, min(int(keep) if keep else 3, MAX_BACKUPS_PER_FILE))
        backup_dir = _ensure_backup_dir()
        index = _load_index()

        if filepath:
            file_obj, err = guard_path(filepath, must_exist=False, for_write=False)
            if err:
                return err
            key = _file_key(file_obj)
            keys_to_clean = [key] if key in index else []
        else:
            keys_to_clean = list(index.keys())

        if not keys_to_clean:
            return "📂 没有可清理的备份"

        total_removed = 0
        for key in keys_to_clean:
            entries = index.get(key, [])
            if len(entries) <= keep:
                continue
            to_remove = entries[:-keep] if keep > 0 else entries
            for old in to_remove:
                old_path = backup_dir / old["backup_file"]
                if old_path.exists():
                    old_path.unlink()
                    total_removed += 1
            index[key] = entries[-keep:] if keep > 0 else []

        # Remove empty keys
        index = {k: v for k, v in index.items() if v}
        _save_index(index)

        scope = f"文件 '{filepath}'" if filepath else "全部文件"
        return f"✅ 已清理 {scope} 的备份：删除 {total_removed} 个旧版本，每文件保留最近 {keep} 个"

    except Exception as e:
        return f"❌ 清理备份失败: {e}"
