# core/ui.py
# Terminal UI layer — OpenCode-grade visual polish

import json
import difflib
import time
from typing import Any
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from rich.live import Live
from rich.align import Align

console = Console()
_status = None
_assistant_stream_open = False
_reasoning_stream_open = False
_live: Live | None = None
_live_buffer = ""

# ── branding ──────────────────────────────────────────────────────────

_LOGO = r"""
     ╭─────────────────────────────────────╮
     │    ___    ____   ___                 │
     │   /   |  /  _/  /   |  ____ _ ___   │
     │  / /| |  / /   / /| | / __ `// _ \  │
     │ / ___ |_/ /   / ___ |/ /_/ //  __/  │
     │/_/  |_/___/  /_/  |_|\__, / \___/   │
     │                     /____/ nt        │
     ╰─────────────────────────────────────╯
"""

_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_FLOW_FRAMES = ("▰▱▱▱", "▰▰▱▱", "▰▰▰▱", "▰▰▰▰", "▱▰▰▰", "▱▱▰▰", "▱▱▱▰", "▱▱▱▱")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _classify_text(text: str) -> tuple[str, str]:
    lower = text.lower()
    if any(token in lower for token in ("error", "failed", "traceback", "异常", "错误")):
        return "red", "ERROR"
    if any(token in lower for token in ("warn", "warning", "警告")):
        return "yellow", "WARN"
    if any(token in lower for token in ("ok", "success", "done", "通过", "成功")):
        return "green", "OK"
    return "cyan", "RESULT"


def _progress_bar(progress: float, width: int = 20) -> Text:
    pct = min(1.0, max(0.0, float(progress or 0.0)))
    filled = int(round(width * pct))
    bar = Text()
    for i in range(width):
        if i < filled:
            bar.append("━", style="bold bright_cyan")
        elif i == filled:
            bar.append("╸", style="bright_cyan")
        else:
            bar.append("━", style="bright_black")
    return bar


def _spinner() -> str:
    idx = int(time.time() * 10) % len(_SPINNER_FRAMES)
    return _SPINNER_FRAMES[idx]


def _flow_bar() -> str:
    idx = int(time.time() * 3) % len(_FLOW_FRAMES)
    return _FLOW_FRAMES[idx]


# ── welcome ───────────────────────────────────────────────────────────

def print_welcome(
    skill_count: int,
    model_name: str = "",
    build_mode: str = "balanced",
    provider_name: str = "moonshot",
):
    # Logo with gradient
    logo_text = Text()
    gradient = ["bright_cyan", "cyan", "blue", "bright_blue", "cyan", "bright_cyan"]
    for i, line in enumerate(_LOGO.strip().splitlines()):
        color = gradient[i % len(gradient)]
        logo_text.append(line + "\n", style=color)

    # Info grid
    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim", min_width=10)
    info.add_column()
    info.add_row("provider", f"[bold magenta]{provider_name}[/bold magenta]")
    info.add_row("model", f"[bold cyan]{model_name or 'default'}[/bold cyan]")
    info.add_row("build", f"[bold yellow]{build_mode}[/bold yellow]")
    info.add_row("skills", f"[bold green]{skill_count}[/bold green] loaded")
    info.add_row("", "")
    info.add_row("", "[dim]type [bold]/help[/bold] for commands · [bold]Ctrl+C[/bold] to exit[/dim]")

    inner = Table.grid(expand=True)
    inner.add_column(ratio=5)
    inner.add_column(ratio=4)
    inner.add_row(logo_text, info)

    console.print(
        Panel(
            inner,
            border_style="bright_blue",
            box=box.HEAVY,
            padding=(0, 1),
        )
    )
    console.print()


# ── slash help ────────────────────────────────────────────────────────

def print_slash_help(commands: list[str] | None = None):
    rows = commands or [
        "/help", "/provider [name]", "/providers", "/model [name]",
        "/build [fast|balanced|deep]", "/approve [on|off]",
        "/sessions", "/session [id]", "/new",
        "/themes", "/theme [name]", "/doctor [provider]",
        "/stats", "/clear", "/exit",
    ]
    descriptions = {
        "/help": "查看命令帮助",
        "/provider [name]": "查看或切换 provider",
        "/providers": "列出可用 provider",
        "/model [name]": "查看或切换模型",
        "/build [fast|balanced|deep]": "查看或切换构建模式",
        "/approve [on|off]": "风险工具自动审批开关",
        "/sessions": "显示最近会话摘要",
        "/session [id]": "切换到指定会话",
        "/new": "创建并切换到新会话",
        "/themes": "列出可用 UI 主题",
        "/theme [name]": "切换 UI 主题",
        "/doctor [provider]": "诊断 API Key / .env 加载状态",
        "/stats": "显示当前会话统计",
        "/clear": "清屏并重画首页",
        "/exit": "退出程序",
    }
    table = Table(
        box=box.SIMPLE_HEAD,
        show_lines=False,
        border_style="bright_black",
        header_style="bold bright_cyan",
        row_styles=["", "dim"],
    )
    table.add_column("Command", style="cyan", min_width=28)
    table.add_column("Description", style="white")
    for cmd in rows:
        table.add_row(cmd, descriptions.get(cmd, ""))
    console.print(
        Panel(
            table,
            title="[bold bright_cyan]/ Commands[/bold bright_cyan]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


# ── messages ──────────────────────────────────────────────────────────

def print_user(text: str):
    if not text:
        return
    console.print()
    label = Text()
    label.append(" YOU ", style="bold black on yellow")
    label.append(f"  {text}", style="white")
    console.print(
        Panel(
            label,
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def print_bot(text):
    if not text:
        return
    console.print()
    header = Text()
    header.append(" ASSISTANT ", style="bold black on cyan")
    console.print(header)
    console.print(
        Panel(
            Markdown(text),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def print_system(text):
    console.print(f"  [dim bright_black]│[/dim bright_black] [dim]{text}[/dim]")


def clear_screen():
    console.clear()


# ── runtime meter ─────────────────────────────────────────────────────

def print_runtime_meter(stats: dict[str, Any], progress: float = 0.0):
    session = str(stats.get("session_id", ""))[:14]
    turns = stats.get("turns", 0)
    steps = stats.get("steps", 0)
    tools = stats.get("tool_calls", 0)
    failures = stats.get("tool_failures", 0)
    prompt_tokens = stats.get("prompt_tokens", 0)
    completion_tokens = stats.get("completion_tokens", 0)
    total_tokens = stats.get("total_tokens", 0)
    cost = float(stats.get("total_cost_usd", 0.0) or 0.0)
    uptime = stats.get("uptime_s", 0)

    bar = _progress_bar(progress)
    pct = int(min(100, max(0, round(progress * 100))))
    spin = _spinner()

    line = Text()
    line.append(f"  {spin} ", style="bold bright_cyan")
    line.append_text(bar)
    line.append(f" {pct:>3}%", style="dim")
    line.append("  │ ", style="bright_black")
    line.append(f"{session}", style="cyan")
    line.append("  │ ", style="bright_black")
    line.append(f"turn ", style="dim")
    line.append(f"{turns}", style="white")
    line.append(f"  step ", style="dim")
    line.append(f"{steps}", style="white")
    line.append(f"  tool ", style="dim")
    line.append(f"{tools}", style="white")
    if failures:
        line.append(f"  err ", style="dim")
        line.append(f"{failures}", style="bold red")
    line.append("  │ ", style="bright_black")
    line.append(f"tok ", style="dim")
    line.append(f"{prompt_tokens}", style="bright_blue")
    line.append("/", style="dim")
    line.append(f"{completion_tokens}", style="green")
    line.append(f"({total_tokens})", style="bold white")
    line.append(f"  ${cost:.5f}", style="yellow")
    line.append(f"  {uptime}s", style="dim")

    console.print(line)


# ── tool execution ────────────────────────────────────────────────────

def print_tool_exec(func_name: str, args: dict | None = None, risky: bool = False):
    console.print()
    header = Text()
    if risky:
        header.append(" RISK ", style="bold white on red")
    else:
        header.append(" TOOL ", style="bold black on bright_magenta")
    header.append(f"  {func_name}", style="bold bright_magenta")

    # Show key arg summary
    if args:
        summary_parts = []
        for key in ("filename", "path", "command", "query", "url", "cwd"):
            val = str(args.get(key, "")).strip()
            if val:
                short = val if len(val) <= 60 else val[:57] + "..."
                summary_parts.append(f"{key}={short}")
        if summary_parts:
            header.append("  ", style="dim")
            header.append(" ".join(summary_parts[:2]), style="dim bright_magenta")

    console.print(header)


def print_tool_result(text):
    display = _as_text(text)
    color, status = _classify_text(display)

    lines = display.splitlines()

    # Diff rendering
    if len(lines) >= 2 and lines[0].startswith("---") and lines[1].startswith("+++"):
        console.print(
            Panel(
                Syntax(display, "diff", theme="monokai", line_numbers=True),
                title=f"[bold {color}]DIFF[/bold {color}]",
                border_style=color,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
        return

    # JSON rendering
    if display.strip().startswith("{") or display.strip().startswith("["):
        try:
            pretty = json.dumps(json.loads(display), ensure_ascii=False, indent=2)
            console.print(
                Panel(
                    Syntax(pretty, "json", theme="monokai", line_numbers=False),
                    title=f"[bold {color}]{status}[/bold {color}]",
                    border_style=color,
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )
            return
        except Exception:
            pass

    # Truncate long output
    if len(display) > 1400:
        display = display[:1400] + "\n[dim]... (truncated)[/dim]"

    # Status badge
    badge = Text()
    if status == "ERROR":
        badge.append(f" {status} ", style="bold white on red")
    elif status == "WARN":
        badge.append(f" {status} ", style="bold black on yellow")
    elif status == "OK":
        badge.append(f" {status} ", style="bold black on green")
    else:
        badge.append(f" {status} ", style="bold black on cyan")

    console.print(
        Panel(
            Group(badge, Text(), Text(display)),
            border_style=color,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


# ── thinking / streaming ─────────────────────────────────────────────

def print_thinking(label: str = "thinking", detail: str = "", progress: float = 0.0):
    global _status
    pct = int(min(100, max(0, round(progress * 100))))
    spin = _spinner()
    flow = _flow_bar()

    message = Text()
    message.append(f"{spin} ", style="bold bright_cyan")
    message.append(f"{label}", style="bold cyan")
    if detail:
        message.append(f" · {detail}", style="dim")
    message.append(f"  {flow}  {pct}%", style="dim bright_cyan")

    if _status is None:
        _status = console.status(message, spinner="dots", spinner_style="bright_cyan")
        _status.start()
    else:
        _status.update(message)


def clear_thinking():
    global _status
    if _status is not None:
        _status.stop()
        _status = None


def start_assistant_stream(model_name: str = ""):
    global _assistant_stream_open, _live, _live_buffer
    if _assistant_stream_open:
        return
    end_reasoning_stream()
    _live_buffer = ""

    console.print()
    header = Text()
    header.append(" ASSISTANT ", style="bold black on cyan")
    if model_name:
        header.append(f"  {model_name}", style="dim cyan")
    header.append("  [dim](streaming)[/dim]")
    console.print(header)

    _assistant_stream_open = True
    _live = Live(
        Text("▍", style="bright_cyan"),
        console=console,
        refresh_per_second=15,
        vertical_overflow="visible",
    )
    _live.start()


def stream_token(token: str):
    global _live_buffer
    if not _assistant_stream_open:
        start_assistant_stream()
    _live_buffer += token
    if _live is not None:
        display = Text(_live_buffer)
        display.append("▍", style="bright_cyan")
        _live.update(display)


def stream_end():
    global _assistant_stream_open, _live, _live_buffer
    if _live is not None:
        _live.update(Markdown(_live_buffer))
        _live.stop()
        _live = None
    _live_buffer = ""
    _assistant_stream_open = False


def start_reasoning_stream():
    global _reasoning_stream_open
    if _reasoning_stream_open:
        return
    console.print()
    header = Text()
    header.append(" THINKING ", style="bold black on bright_black")
    console.print(header)
    console.print("[dim]", end="")
    _reasoning_stream_open = True


def stream_reasoning_token(token: str):
    if not _reasoning_stream_open:
        start_reasoning_stream()
    console.print(token, end="", highlight=False, style="dim")


def end_reasoning_stream():
    global _reasoning_stream_open
    if _reasoning_stream_open:
        console.print("[/dim]")
        console.print()
    _reasoning_stream_open = False


# ── session / input ───────────────────────────────────────────────────

def ask_resume_chat(msg_count: int) -> bool:
    console.print()
    console.print(
        Panel(
            f"[dim]检测到上次对话 ([bold]{msg_count}[/bold] 条消息)[/dim]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    choice = console.input("[bold bright_cyan]恢复上次对话？[/bold bright_cyan] [dim]\\[y/n]:[/dim] ").lower()
    return choice in ("y", "")


def get_user_input(prompt="\n[bold yellow]you ›[/bold yellow] "):
    try:
        return console.input(prompt)
    except KeyboardInterrupt:
        return "exit"
    except EOFError:
        return "exit"


def get_multiline_input(prompt_text):
    if prompt_text:
        console.print(prompt_text)
    console.print("[dim](输入完成后按 Ctrl+Z (Windows) 或 Ctrl+D (Mac) 并回车结束)[/dim]")
    contents = []
    try:
        while True:
            line = input()
            contents.append(line)
    except EOFError:
        pass
    return "\n".join(contents)


# ── approval ──────────────────────────────────────────────────────────

def _show_edit_diff(args):
    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")
    diff = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="")
    diff_text = "\n".join(diff)
    console.print(Syntax(diff_text, "diff", theme="monokai", line_numbers=True))


def ask_for_approval(func_name, args):
    """
    处理高风险操作的审批流程
    返回: (should_execute, tool_result_if_rejected, modified_args)
    """
    console.print()

    # Build info display
    if func_name == "edit_file":
        filename = args.get("filename", "未知")
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")
        info_text = (
            f"[bold]file[/bold]    {filename}\n"
            f"[bold]change[/bold]  {len(old_text)} chars → {len(new_text)} chars\n"
            "[dim]press [bold]v[/bold] to view diff[/dim]"
        )
    elif func_name == "write_code_file":
        filename = args.get("filename", "未知")
        content = args.get("content", "")
        info_text = f"[bold]file[/bold]    {filename}\n[bold]size[/bold]    {len(content)} chars"
    elif func_name == "run_command":
        cmd = args.get("command", "")
        cwd = args.get("cwd", ".")
        info_text = f"[bold]cmd[/bold]     {cmd}\n[bold]cwd[/bold]     {cwd}"
    else:
        info_text = f"[bold]args[/bold]\n{json.dumps(args, ensure_ascii=False, indent=2)}"

    # Action bar
    actions = Text()
    actions.append("\n")
    actions.append(" y ", style="bold black on green")
    actions.append(" approve  ", style="dim")
    actions.append(" n ", style="bold black on red")
    actions.append(" reject  ", style="dim")
    actions.append(" v ", style="bold black on cyan")
    actions.append(" view  ", style="dim")
    actions.append(" r ", style="bold black on yellow")
    actions.append(" rewrite  ", style="dim")
    actions.append(" m ", style="bold black on magenta")
    actions.append(" manual", style="dim")

    console.print(
        Panel(
            Group(Text(info_text), actions),
            title=f"[bold red]Approval Required · {func_name}[/bold red]",
            border_style="red",
            box=box.HEAVY,
            padding=(0, 1),
        )
    )

    while True:
        choice = console.input("[bold bright_red]›[/bold bright_red] ").lower()

        if choice == "v":
            if func_name == "edit_file":
                _show_edit_diff(args)
            elif func_name == "write_code_file":
                content = args.get("content", "")
                filename = args.get("filename", "")
                ext = filename.rsplit(".", 1)[-1] if "." in filename else "text"
                console.print(Syntax(content, ext, theme="monokai", line_numbers=True))
            else:
                console.print_json(json.dumps(args, ensure_ascii=False))
            continue

        if choice in ("y", ""):
            console.print("[bold green]  approved[/bold green]")
            return True, None, args

        if choice == "n":
            console.print("[bold red]  rejected[/bold red]")
            return False, "用户拒绝了该操作。", None

        if choice == "r":
            feedback = console.input("[bold yellow]feedback:[/bold yellow] ")
            return False, f"用户拒绝。反馈: '{feedback}'。请重试。", None

        if choice == "m":
            console.print("[bold magenta]manual edit mode[/bold magenta]")
            if func_name == "write_code_file":
                console.print("请粘贴代码:")
                new_content = get_multiline_input("")
                if new_content.strip():
                    args["content"] = new_content
                    return True, None, args
            else:
                new_json = console.input("输入新 JSON 参数: ")
                if new_json.strip():
                    try:
                        args = json.loads(new_json)
                        return True, None, args
                    except Exception:
                        console.print("[red]JSON 格式错误[/red]")
            return False, "用户取消手动输入", None

        console.print("[dim]invalid choice[/dim]")
