import os
import re
import subprocess
from pathlib import Path

from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT

# ==========================================
# 🛡️ 沙箱安全配置
# ==========================================
# 危险命令关键词黑名单 (匹配命令开头或管道后的命令)
DANGEROUS_COMMANDS = [
    r"\brm\s+(-rf|-r|-f)",      # rm -rf / rm -r
    r"\brmdir\b",                # rmdir
    r"\bformat\b",               # format (Windows)
    r"\bdel\s+/[sqf]",           # del /s /q (Windows)
    r"\brd\s+/s",                # rd /s (Windows)
    r"\bmkfs\b",                 # mkfs (Linux)
    r"\bdd\s+if=",               # dd if= (Linux)
    r"\b:>{1,2}\s*/",            # > /dev/sda etc
    r"\bshutdown\b",             # shutdown
    r"\breboot\b",               # reboot
    r"\breg\s+(delete|add)",     # Windows registry
    r"\bnet\s+user",             # net user (Windows)
    r"\bcurl\b.*\|\s*(bash|sh)", # curl | bash
    r"\bwget\b.*\|\s*(bash|sh)", # wget | bash
]

# 禁止操作的目录 (AI 不应该在这些目录下执行命令)
FORBIDDEN_PATHS = [
    r"C:\\Windows",
    r"C:\\Program Files",
    r"/etc",
    r"/usr",
    r"/boot",
    r"/sys",
]


def _is_command_safe(command: str, cwd_resolved: Path) -> str | None:
    """检查命令是否安全。返回 None 表示安全，返回字符串表示拒绝原因。"""
    cmd_lower = command.lower().strip()

    # 检查危险命令
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, cmd_lower):
            return f"🚫 安全拦截：命令匹配危险模式 `{pattern}`。如确需执行，请手动在终端运行。"

    # 检查禁止目录
    cwd_str = str(cwd_resolved).replace("/", "\\")
    for forbidden in FORBIDDEN_PATHS:
        if cwd_str.lower().startswith(forbidden.lower()):
            return f"🚫 安全拦截：禁止在系统目录 `{forbidden}` 下执行命令。"

    return None


list_dir_schema = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "列出目录内容，帮助你先了解项目结构再进行读写和修改。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要查看的目录路径，默认当前目录。",
                },
                "max_entries": {
                    "type": "integer",
                    "description": "最多返回多少条目，默认 200，最大 1000。",
                },
            },
            "required": [],
        },
    },
}


run_command_schema = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "【危险操作】执行 shell 命令并返回输出。用于运行测试、查看 git 状态、安装依赖等。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令，比如 `git status` 或 `python -m pytest`。",
                },
                "cwd": {
                    "type": "string",
                    "description": "命令执行目录，默认当前目录。",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 60，最大 600。",
                },
            },
            "required": ["command"],
        },
    },
}


def _resolve_path(path: str) -> Path:
    target_obj, err = guard_path(path or ".", must_exist=True, for_write=False)
    if err:
        raise ValueError(err)
    return target_obj


@register(list_dir_schema)
def list_dir(path: str = ".", max_entries: int = 200):
    try:
        target = _resolve_path(path)
        if not target.is_dir():
            return f"❌ 不是目录: {target}"
    except Exception as exc:
        return f"❌ 路径解析失败: {exc}"

    try:
        limit = int(max_entries) if max_entries is not None else 200
    except Exception:
        limit = 200
    limit = max(1, min(limit, 1000))

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except Exception as exc:
        return f"❌ 读取目录失败: {exc}"

    lines = [f"📁 {target}"]
    total = len(entries)
    shown = entries[:limit]
    for item in shown:
        kind = "DIR " if item.is_dir() else "FILE"
        try:
            size = item.stat().st_size if item.is_file() else 0
        except Exception:
            size = 0
        rel_name = item.name + (os.sep if item.is_dir() else "")
        lines.append(f"{kind}\t{size:>8}\t{rel_name}")

    if total > limit:
        lines.append(f"... (已截断，仅显示 {limit}/{total} 条)")
    else:
        lines.append(f"共 {total} 条")

    return "\n".join(lines)


@register(run_command_schema)
def run_command(command: str, cwd: str = ".", timeout_seconds: int = 60):
    if not command or not str(command).strip():
        return "❌ command 不能为空。"

    try:
        workdir = _resolve_path(cwd)
    except Exception as exc:
        return f"❌ cwd 解析失败: {exc}"

    if not workdir.exists() or not workdir.is_dir():
        return f"❌ cwd 无效: {workdir}"

    try:
        workdir.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return f"❌ cwd 越界：仅允许在工作区内执行命令 ({WORKSPACE_ROOT})"

    # 🛡️ 沙箱安全检查
    safety_error = _is_command_safe(command, workdir)
    if safety_error:
        return safety_error

    try:
        timeout = int(timeout_seconds) if timeout_seconds is not None else 60
    except Exception:
        timeout = 60
    timeout = max(1, min(timeout, 600))

    try:
        proc = subprocess.run(
            command,
            cwd=str(workdir),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        return (
            f"⏱️ 命令超时（>{timeout}s）\n"
            f"cwd: {workdir}\n"
            f"command: {command}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    except Exception as exc:
        return f"❌ 命令执行失败: {exc}"

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if not stdout:
        stdout = "(empty)"
    if not stderr:
        stderr = "(empty)"

    max_chars = 10000
    if len(stdout) > max_chars:
        stdout = stdout[:max_chars] + "\n... (stdout truncated)"
    if len(stderr) > max_chars:
        stderr = stderr[:max_chars] + "\n... (stderr truncated)"

    return (
        f"exit_code: {proc.returncode}\n"
        f"cwd: {workdir}\n"
        f"command: {command}\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}"
    )
