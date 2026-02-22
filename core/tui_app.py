from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import threading
import time
from typing import Any

from rich.console import Group
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

from .agent_runner import AgentRunner, list_saved_chat_sessions
from .config import list_providers
from .theme_registry import get_active_theme_name, get_theme, list_theme_names


@dataclass
class _RuntimePayload:
    event_type: str
    payload: dict[str, Any]


class RuntimeRelay:
    def __init__(self, app: "AgentTUIApp"):
        self.app = app

    def handle(self, event: Any) -> None:
        payload = _RuntimePayload(event_type=str(event.type), payload=dict(event.payload or {}))
        app_thread_id = getattr(self.app, "_thread_id", None)
        if app_thread_id == threading.get_ident():
            self.app.consume_runtime_event(payload)
            return
        self.app.call_from_thread(self.app.consume_runtime_event, payload)


try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.events import Key
    from textual.suggester import SuggestFromList
    from textual.widgets import Footer, Header, Input, ProgressBar, RichLog, Static
    try:
        from textual.widgets import TextArea
    except Exception:  # pragma: no cover - version compatibility
        TextArea = None
    try:
        # textual>=8 re-exports `work` from the package root.
        from textual import work
    except Exception:  # pragma: no cover - version compatibility
        from textual.worker import work
except ImportError as e:  # pragma: no cover - runtime-only import path
    raise RuntimeError(
        f"❌ TUI 依赖导入失败: {e}. 请确认在当前解释器执行: python -m pip install -U textual"
    ) from e


class AgentTUIApp(App):
    TITLE = "AI Agent TUI"
    SUB_TITLE = "OpenCode-style terminal workspace"
    LOGO_LINES = [
        "    ╭─────────────────────────────────╮",
        "    │   ___    ____   ___              │",
        "    │  /   |  /  _/  /   |  ____ ___  │",
        "    │ / /| |  / /   / /| | / __ `/ _ \\ │",
        "    │/ ___ |_/ /   / ___ |/ /_/ /  __/ │",
        "    │/_/ |_/___/  /_/  |_|\\__, /\\___/  │",
        "    │                    /____/ nt     │",
        "    ╰─────────────────────────────────╯",
    ]
    CSS = """
    Screen {
        layout: vertical;
        background: #050910;
        color: #D9E6FF;
    }
    #main {
        height: 1fr;
        layout: horizontal;
    }
    #chat-pane {
        width: 1fr;
        border: heavy #2A6FA8;
        margin: 0 0 0 1;
        background: #0A1220;
        padding: 0;
    }
    #flow_text {
        padding: 0 1;
        height: 1;
        color: #BFE8FF;
        text-style: bold;
        background: #0D1628;
    }
    #flow_loader {
        padding: 0 1;
        height: 1;
        background: #0D1628;
        border-bottom: hkey #1A2D48;
    }
    #live_stream {
        height: auto;
        max-height: 12;
        border-bottom: hkey #1A2D48;
        padding: 0 1;
        background: #0E1A2E;
        display: none;
    }
    #chat_log {
        height: 1fr;
        color: #E4EEFF;
        padding: 0 1;
        scrollbar-color: #2A6FA8;
        scrollbar-color-hover: #3BB4F2;
        scrollbar-color-active: #5CC8FF;
    }
    #side-pane {
        width: 36;
        border: heavy #1E3A5C;
        margin: 0 1 0 0;
        background: #080E18;
        padding: 0;
    }
    #session_info {
        padding: 1 1 0 1;
        color: #D0DDFF;
        border-bottom: hkey #1A2D48;
    }
    #usage_info {
        padding: 1 1 0 1;
        color: #D0DDFF;
        border-bottom: hkey #1A2D48;
    }
    #stage_info {
        padding: 1 1;
        color: #D0DDFF;
    }
    #command_drawer {
        width: 0;
        border: heavy #2A6FA8;
        margin: 0 1 0 0;
        padding: 0 1;
        background: #0A1323;
        color: #DFF5FF;
    }
    #progress {
        margin: 0 1;
        color: #35BDF0;
    }
    #prompt_input {
        dock: bottom;
        margin: 0 1 0 1;
        height: 3;
        background: #0C1424;
        color: #EAF4FF;
        border: heavy #2A6FA8;
    }
    #status_bar {
        dock: bottom;
        height: 1;
        margin: 0 1;
        padding: 0 1;
        color: #8EA7C7;
        background: #080E18;
        border-top: hkey #1A2D48;
    }
    #slash_panel {
        dock: bottom;
        margin: 0 1;
        border: heavy #2A6FA8;
        background: #0C1628;
        color: #DDEEFF;
        padding: 0 1;
        max-height: 12;
        display: none;
    }
    #dialog_overlay {
        layer: overlay;
        width: 100%;
        height: 100%;
        display: none;
        align-horizontal: center;
        align-vertical: middle;
        background: rgba(2, 6, 14, 0.82);
    }
    #dialog_panel {
        width: 72%;
        max-height: 76%;
        border: heavy #3BB4F2;
        background: #0A1326;
        color: #E4EEFF;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+c", "cancel_stream", "Cancel"),
        Binding("ctrl+p", "toggle_commands", "Commands"),
        Binding("ctrl+b", "toggle_compact", "Compact"),
        Binding("ctrl+h", "show_sessions", "Sessions"),
        Binding("ctrl+e", "expand_tool_result", "Expand Tool"),
        Binding("ctrl+r", "expand_reasoning", "Reasoning"),
        Binding("escape", "close_dialog", "Close Dialog"),
        Binding("ctrl+enter", "submit_prompt", "Submit"),
        Binding("ctrl+up", "history_prev", "Prev"),
        Binding("ctrl+down", "history_next", "Next"),
    ]

    def __init__(self, *, compact: bool = False):
        super().__init__()
        self.runner = AgentRunner(auto_approve_risky=True)
        self._assistant_buffer = ""
        self._reasoning_buffer = ""
        self._live_mode = ""
        self._timeline: list[Any] = []
        self._last_stream_paint_at = 0.0

        self._flow_active = False
        self._flow_label = "idle"
        self._flow_detail = ""
        self._flow_phase = 0

        self._drawer_open = False
        self._drawer_width = 0
        self._drawer_target_width = 0
        self._drawer_max_width = 44
        self._drawer_step = 4
        self._use_textarea = TextArea is not None
        self._input_history: list[str] = []
        self._history_index = -1
        self._usage_target = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0}
        self._usage_display = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0}
        self._slash_panel_visible = False
        self._slash_items: list[str] = []
        self._slash_selected = 0
        self._slash_max_rows = 8
        self._last_prompt_text = ""
        self._recent_slash_commands: list[str] = []
        self._hot_slash_commands = [
            "/help",
            "/sessions",
            "/new",
            "/themes",
            "/stats",
            "/build balanced",
            "/approve on",
        ]
        self._collapsed_tool_results: dict[int, tuple[str, bool]] = {}
        self._last_collapsed_tool_index: int = -1
        self._reasoning_started_at = 0.0
        self._last_reasoning_full = ""
        self._compact_mode = bool(compact)
        self._theme_name = get_active_theme_name("tui")
        self._theme = get_theme(self._theme_name) or {}
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0
        self._scanner_pos = 0
        self._scanner_dir = 1
        self._dialog_stack: list[tuple[str, str]] = []
        self._status_mcp = os.getenv("AI_MCP_STATUS", "offline")
        self._status_lsp = os.getenv("AI_LSP_STATUS", "idle")
        self._app_version = os.getenv("AI_AGENT_VERSION", "v1.0")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="chat-pane"):
                yield Static(id="flow_text")
                yield Static(id="flow_loader")
                yield Static(id="live_stream")
                yield RichLog(id="chat_log", markup=True, wrap=True, auto_scroll=True)
            with Vertical(id="side-pane"):
                yield Static(id="session_info")
                yield ProgressBar(total=100, show_percentage=False, id="progress")
                yield Static(id="stage_info")
                yield Static(id="usage_info")
            yield Static(id="command_drawer")
        yield Static(id="slash_panel")
        if self._use_textarea:
            assert TextArea is not None
            yield TextArea("", id="prompt_input")
        else:
            yield Input(placeholder="输入消息或 / 命令，Tab 可补全", id="prompt_input")
        yield Static(id="status_bar")
        with Vertical(id="dialog_overlay"):
            yield Static(id="dialog_panel")
        yield Footer()

    def on_mount(self) -> None:
        self.runner.on(RuntimeRelay(self).handle)
        self.runner.resume_history(resume=True)
        self._apply_theme(force=True)
        self._render_messages_from_runner()
        self._refresh_side()
        self._refresh_flow_visuals()
        self._refresh_status_bar()
        self._refresh_input_suggester()
        self._render_command_drawer()
        self._refresh_slash_panel(force=True)
        self.set_interval(0.08, self._tick_ui)
        self._apply_compact_layout()
        self._focus_prompt()

    def _apply_compact_layout(self) -> None:
        side = self.query_one("#side-pane", Vertical)
        side.display = not self._compact_mode
        if self._compact_mode:
            self._drawer_open = False
            self._drawer_target_width = 0
            self._drawer_width = 0
            self._render_command_drawer()

    def _theme_tui(self) -> dict[str, str]:
        raw = self._theme.get("tui") if isinstance(self._theme, dict) else {}
        if not isinstance(raw, dict):
            raw = {}
        return {
            "screen_bg": str(raw.get("screen_bg", "#060A12")),
            "chat_bg": str(raw.get("chat_bg", "#0B1220")),
            "side_bg": str(raw.get("side_bg", "#091019")),
            "drawer_bg": str(raw.get("drawer_bg", "#0A1323")),
            "live_bg": str(raw.get("live_bg", "#0F192B")),
            "panel_primary": str(raw.get("panel_primary", "#3BB4F2")),
            "panel_secondary": str(raw.get("panel_secondary", "#2A4E7B")),
            "panel_muted": str(raw.get("panel_muted", "#1D314C")),
            "text_primary": str(raw.get("text_primary", "#E4EEFF")),
            "text_soft": str(raw.get("text_soft", "#D0DDFF")),
            "text_dim": str(raw.get("text_dim", "#8EA7C7")),
            "accent_a": str(raw.get("accent_a", "#35BDF0")),
            "accent_b": str(raw.get("accent_b", "#7DD3FC")),
            "accent_warn": str(raw.get("accent_warn", "#F59E0B")),
            "accent_good": str(raw.get("accent_good", "#34D399")),
        }

    def _apply_theme(self, force: bool = False) -> None:
        active = get_theme(self._theme_name) or {}
        if not active:
            return
        if (not force) and active == self._theme:
            return
        self._theme = active
        t = self._theme_tui()
        self.styles.background = t["screen_bg"]

        chat = self.query_one("#chat-pane", Vertical)
        chat.styles.background = t["chat_bg"]
        chat.styles.border = ("heavy", t["panel_primary"])

        side = self.query_one("#side-pane", Vertical)
        side.styles.background = t["side_bg"]
        side.styles.border = ("heavy", t["panel_secondary"])

        drawer = self.query_one("#command_drawer", Static)
        drawer.styles.background = t["drawer_bg"]
        drawer.styles.border = ("heavy", t["panel_primary"])

        live = self.query_one("#live_stream", Static)
        live.styles.background = t["live_bg"]
        live.styles.border_bottom = ("hkey", t["panel_muted"])

        flow_loader = self.query_one("#flow_loader", Static)
        flow_loader.styles.border_bottom = ("hkey", t["panel_muted"])
        flow_text = self.query_one("#flow_text", Static)
        flow_text.styles.color = t["text_soft"]
        flow_text.styles.background = t["side_bg"]
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.styles.color = t["text_primary"]
        progress = self.query_one("#progress", ProgressBar)
        progress.styles.color = t["accent_a"]

        prompt = self.query_one("#prompt_input")
        prompt.styles.background = t["drawer_bg"]
        prompt.styles.color = t["text_primary"]
        prompt.styles.border = ("heavy", t["panel_secondary"])

        slash = self.query_one("#slash_panel", Static)
        slash.styles.background = t["chat_bg"]
        slash.styles.border = ("heavy", t["panel_secondary"])

        status_bar = self.query_one("#status_bar", Static)
        status_bar.styles.background = t["side_bg"]
        status_bar.styles.border_top = ("hkey", t["panel_muted"])
        status_bar.styles.color = t["text_dim"]

        panel = self.query_one("#dialog_panel", Static)
        panel.styles.background = t["chat_bg"]
        panel.styles.border = ("heavy", t["panel_primary"])

    def _scanner_text(self, width: int = 22) -> Text:
        t = self._theme_tui()
        out = Text()
        for i in range(width):
            dist = abs(i - self._scanner_pos)
            if dist == 0:
                out.append("━", style=f"bold {t['accent_warn']}")
            elif dist == 1:
                out.append("━", style=f"bold {t['accent_b']}")
            elif dist == 2:
                out.append("━", style=t["accent_a"])
            elif dist == 3:
                out.append("━", style=t["panel_secondary"])
            else:
                out.append("━", style=t["panel_muted"])
        return out

    def _refresh_status_bar(self) -> None:
        t = self._theme_tui()
        bar = self.query_one("#status_bar", Static)
        spinner = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
        cwd = str(Path.cwd())
        cwd_short = cwd if len(cwd) <= 30 else ("..." + cwd[-27:])
        scanner = self._scanner_text(20)

        status = Text()
        status.append(f"{spinner} ", style=f"bold {t['accent_a']}")
        status.append(cwd_short, style=t["text_dim"])
        status.append("  ", style="dim")

        # MCP status dot
        if self._status_mcp == "online":
            status.append("● ", style=t["accent_good"])
            status.append("mcp ", style="dim")
        else:
            status.append("○ ", style=t["text_dim"])
            status.append("mcp ", style="dim")

        # LSP status dot
        if self._status_lsp == "ready":
            status.append("● ", style=t["accent_good"])
            status.append("lsp ", style="dim")
        else:
            status.append("○ ", style=t["text_dim"])
            status.append("lsp ", style="dim")

        status.append(" ", style="dim")
        status.append(f"{self._theme_name}", style=t["accent_b"])
        status.append("  ", style="dim")
        status.append(f"{self._app_version}", style=t["text_dim"])
        status.append("  ", style="dim")
        status.append_text(scanner)
        bar.update(status)

    def _dialog_is_open(self) -> bool:
        return len(self._dialog_stack) > 0

    def _render_dialog(self) -> None:
        overlay = self.query_one("#dialog_overlay", Vertical)
        panel = self.query_one("#dialog_panel", Static)
        if not self._dialog_stack:
            overlay.display = False
            panel.update("")
            return
        t = self._theme_tui()
        title, body = self._dialog_stack[-1]
        overlay.display = True
        header = Text()
        header.append(f" {title} ", style=f"bold black on {t['accent_a']}")
        footer = Text()
        footer.append("\n")
        footer.append(" Esc ", style="bold black on bright_black")
        footer.append(" close", style="dim")
        from rich.console import Group as RGroup
        panel.update(RGroup(header, Text(), Text(body), footer))

    def _push_dialog(self, title: str, body: str) -> None:
        self._dialog_stack.append((title, body))
        self._render_dialog()

    def _pop_dialog(self) -> None:
        if self._dialog_stack:
            self._dialog_stack.pop()
        self._render_dialog()

    def _focus_prompt(self) -> None:
        widget = self.query_one("#prompt_input")
        widget.focus()

    def _chat_write(self, text: str | Text) -> None:
        if not text:
            return
        self.query_one("#chat_log", RichLog).write(text)

    def _rerender_chat_log(self) -> None:
        log = self.query_one("#chat_log", RichLog)
        log.clear()
        for item in self._timeline:
            log.write(item)

    def _timeline_append(self, renderable: Any) -> int:
        idx = len(self._timeline)
        self._timeline.append(renderable)
        self._chat_write(renderable)
        return idx

    def _timeline_divider(self, label: str = "") -> None:
        t = self._theme_tui()
        ts = datetime.now().strftime("%H:%M:%S")
        divider = Text()
        divider.append("  ", style=t["panel_muted"])
        divider.append("─" * 16, style=t["panel_muted"])
        divider.append(f" {ts}", style=t["text_dim"])
        if label:
            divider.append(f" · {label} ", style=t["accent_b"])
        divider.append("─" * 16, style=t["panel_muted"])
        self._timeline_append(divider)

    def _timeline_append_message(self, role: str, renderable: Any) -> int:
        self._timeline_divider(role)
        return self._timeline_append(renderable)

    def _timeline_replace(self, idx: int, renderable: Any) -> None:
        if idx < 0 or idx >= len(self._timeline):
            return
        self._timeline[idx] = renderable
        self._rerender_chat_log()

    def _build_logo_renderable(self) -> Text:
        t = self._theme_tui()
        gradient = [t["accent_a"], t["accent_b"], t["text_soft"], t["accent_b"], t["accent_a"], t["text_soft"], t["accent_b"], t["accent_a"]]
        logo = Text()
        for i, line in enumerate(self.LOGO_LINES):
            color = gradient[i % len(gradient)]
            logo.append(line + "\n", style=f"bold {color}")
        return logo

    def _render_messages_from_runner(self) -> None:
        self._timeline = []
        self._collapsed_tool_results = {}
        self._last_collapsed_tool_index = -1

        self._timeline_append(self._build_logo_renderable())
        self._timeline_append("")

        # Session info line
        info = Text()
        info.append("session ", style="dim")
        info.append(f"{self.runner.chat_session_id}", style="cyan")
        info.append("  provider ", style="dim")
        info.append(f"{self.runner.provider_name}", style="magenta")
        info.append("  model ", style="dim")
        info.append(f"{self.runner.model_name}", style="bright_cyan")
        info.append("  build ", style="dim")
        info.append(f"{self.runner.build_mode}", style="yellow")
        info.append("  theme ", style="dim")
        info.append(f"{self._theme_name}", style="bright_blue")
        self._timeline_append(info)

        # Keybindings bar
        keys = Text()
        for label, key in [("Clear", "^L"), ("Cancel", "^C"), ("Commands", "^P"), ("Sessions", "^H"), ("Reasoning", "^R"), ("Compact", "^B")]:
            keys.append(f" {key} ", style="bold black on bright_black")
            keys.append(f" {label}  ", style="dim")
        self._timeline_append(keys)
        self._timeline_append("")

        for msg in self.runner.messages:
            role = str(msg.get("role", ""))
            content = str(msg.get("content", "") or "").strip()
            if role == "user" and content:
                badge = Text()
                badge.append(" YOU ", style="bold black on yellow")
                badge.append(f"  {content}", style="white")
                self._timeline_append_message("you", badge)
            elif role == "assistant" and content:
                badge = Text()
                badge.append(" ASSISTANT ", style="bold black on cyan")
                self._timeline_append_message("assistant", Group(badge, Text(), Markdown(content)))
            elif role == "tool":
                name = str(msg.get("name", "tool"))
                text = content[:500] + ("... (truncated)" if len(content) > 500 else "")
                badge = Text()
                badge.append(" TOOL ", style="bold black on bright_magenta")
                badge.append(f"  {name}", style="bright_magenta")
                self._timeline_append_message(f"tool[{name}]", Group(badge, Text(), Text(text, style="dim")))
        self._rerender_chat_log()
        self._clear_live_stream()

    def _refresh_side(self) -> None:
        t = self._theme_tui()
        stats = self.runner.runtime.get_stats()
        session = self.query_one("#session_info", Static)
        usage = self.query_one("#usage_info", Static)
        stage = self.query_one("#stage_info", Static)
        progress = self.query_one("#progress", ProgressBar)

        self._usage_target["prompt"] = int(stats.get("prompt_tokens", 0) or 0)
        self._usage_target["completion"] = int(stats.get("completion_tokens", 0) or 0)
        self._usage_target["total"] = int(stats.get("total_tokens", 0) or 0)
        self._usage_target["cost"] = float(stats.get("total_cost_usd", 0.0) or 0.0)

        pct = 0
        if self.runner.runtime.max_steps > 0:
            pct = int(min(100, max(0, round((self.runner.runtime.agent_steps / self.runner.runtime.max_steps) * 100))))
        progress.update(progress=pct)

        # Session panel with structured layout
        sess_text = Text()
        sess_text.append("SESSION\n", style=f"bold {t['accent_a']}")
        sess_text.append("id       ", style="dim")
        sess_text.append(f"{stats.get('session_id', '')[:14]}\n", style=t["text_soft"])
        sess_text.append("provider ", style="dim")
        sess_text.append(f"{self.runner.provider_name}\n", style="magenta")
        sess_text.append("model    ", style="dim")
        sess_text.append(f"{self.runner.model_name}\n", style=t["accent_a"])
        sess_text.append("build    ", style="dim")
        sess_text.append(f"{self.runner.build_mode}\n", style="yellow")
        sess_text.append("turn ", style="dim")
        sess_text.append(f"{stats.get('turns', 0)}", style="white")
        sess_text.append("  step ", style="dim")
        sess_text.append(f"{stats.get('steps', 0)}", style="white")
        sess_text.append("  tool ", style="dim")
        sess_text.append(f"{stats.get('tool_calls', 0)}", style="white")
        failures = stats.get("tool_failures", 0)
        if failures:
            sess_text.append("  err ", style="dim")
            sess_text.append(f"{failures}", style="bold red")
        session.update(sess_text)

        # Usage panel with visual counters
        usage_text = Text()
        usage_text.append("USAGE\n", style=f"bold {t['accent_a']}")
        usage_text.append("prompt   ", style="dim")
        usage_text.append(f"{self._usage_display['prompt']}\n", style=t["accent_b"])
        usage_text.append("compl    ", style="dim")
        usage_text.append(f"{self._usage_display['completion']}\n", style=t["accent_good"])
        usage_text.append("total    ", style="dim")
        usage_text.append(f"{self._usage_display['total']}\n", style="bold white")
        usage_text.append("cost     ", style="dim")
        usage_text.append(f"${self._usage_display['cost']:.4f}", style=t["accent_warn"])
        usage.update(usage_text)

        # Stage with spinner
        spin = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
        stage_text = Text()
        stage_text.append("STAGE\n", style=f"bold {t['accent_a']}")
        stage_text.append(f"{spin} ", style=f"bold {t['accent_a']}")
        stage_text.append(f"{self._flow_label}", style=t["text_soft"])
        if self._flow_detail:
            stage_text.append(f"\n  {self._flow_detail}", style="dim")
        stage.update(stage_text)

    def _set_live_stream(self, renderable: Any) -> None:
        widget = self.query_one("#live_stream", Static)
        widget.display = True
        widget.update(renderable)

    def _clear_live_stream(self) -> None:
        widget = self.query_one("#live_stream", Static)
        widget.update("")
        widget.display = False

    def _flush_stream_preview(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_stream_paint_at < 0.10:
            return
        self._last_stream_paint_at = now
        t = self._theme_tui()

        cursor = "▍" if (self._flow_phase % 6 < 3) else " "
        if self._live_mode == "reasoning":
            # Show last ~600 chars of reasoning for preview
            preview = self._reasoning_buffer[-600:] if len(self._reasoning_buffer) > 600 else self._reasoning_buffer
            header = Text()
            header.append(" THINKING ", style="bold black on bright_black")
            elapsed = time.monotonic() - self._reasoning_started_at
            header.append(f"  {elapsed:.1f}s  {len(self._reasoning_buffer)} chars", style="dim")
            self._set_live_stream(
                Group(
                    header,
                    Text(preview + cursor, style="dim"),
                )
            )
            return
        if self._live_mode == "assistant":
            # Show last ~800 chars of assistant stream
            preview = self._assistant_buffer[-800:] if len(self._assistant_buffer) > 800 else self._assistant_buffer
            header = Text()
            header.append(" ASSISTANT ", style=f"bold black on {t['accent_a']}")
            header.append(f"  streaming  {len(self._assistant_buffer)} chars", style="dim")
            self._set_live_stream(
                Group(
                    header,
                    Markdown(preview + cursor),
                )
            )
            return
        self._clear_live_stream()

    def _refresh_flow_visuals(self) -> None:
        t = self._theme_tui()
        text_widget = self.query_one("#flow_text", Static)
        bar_widget = self.query_one("#flow_loader", Static)

        steps = int(self.runner.runtime.agent_steps)
        max_steps = max(1, int(self.runner.runtime.max_steps))
        pct = int(min(100, max(0, round((steps / max_steps) * 100))))
        spinner = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]

        # Flow text with animated gradient
        title = Text()
        title.append(f"{spinner} ", style=f"bold {t['accent_a']}")
        if self._flow_active:
            title.append("FLOW", style=f"bold {t['accent_a']}")
        else:
            title.append("IDLE", style=f"dim {t['text_dim']}")
        title.append("  ", style="dim")

        # Animate the label text with shifting gradient
        label_text = f"{self._flow_label}"
        gradient = [t["accent_a"], t["accent_b"], t["text_soft"], t["accent_b"]]
        for i, ch in enumerate(label_text):
            if ch.isspace():
                title.append(ch)
            else:
                color = gradient[(i + self._flow_phase) % len(gradient)]
                title.append(ch, style=f"bold {color}")

        if self._flow_detail:
            title.append(f"  {self._flow_detail}", style=t["text_dim"])
        title.append(f"  [{steps}/{max_steps}]", style=t["text_dim"])
        text_widget.update(title)

        # Progress bar with smooth gradient fill
        width = 40
        filled = int(round((steps / max_steps) * width))
        bar = Text()
        fill_colors = [t["accent_a"], t["accent_b"], t["text_soft"], t["accent_b"], t["accent_a"]]
        for i in range(width):
            if i < filled:
                color = fill_colors[(i + self._flow_phase) % len(fill_colors)]
                bar.append("━", style=f"bold {color}")
            elif i == filled and self._flow_active:
                bar.append("╸", style=f"bold {t['accent_warn']}")
            else:
                bar.append("━", style=t["panel_muted"])

        # Scanner overlay when active
        if self._flow_active:
            scan = self._scanner_pos % width
            if scan < width:
                bar.stylize(f"bold {t['accent_warn']}", scan, min(width, scan + 1))
            if scan + 1 < width:
                bar.stylize(t["accent_b"], scan + 1, min(width, scan + 2))

        bar.append(f" {pct:>3d}%", style=t["text_dim"])
        bar_widget.update(bar)

    def _normalize_stage(self, label: str, detail: str) -> tuple[str, str]:
        raw = (label or "").strip()
        det = (detail or "").strip()
        if "准备" in raw:
            return "connecting...", det or "building context"
        if "模型推理" in raw:
            return "thinking...", det or "reasoning"
        if "继续推理" in raw:
            return "thinking...", det or "continue"
        if "工具执行" in raw:
            return "running tool...", det or "executing"
        if raw.lower() in {"idle", "thinking", "streaming"}:
            return raw.lower() + "...", det
        return raw or "thinking...", det

    def _summarize_tool_args(self, args: Any) -> str:
        if not isinstance(args, dict):
            return ""
        for key in ("filename", "path", "cwd", "target", "url"):
            value = str(args.get(key, "")).strip()
            if value:
                return value[:80]
        cmd = str(args.get("command", "")).strip()
        if cmd:
            return cmd[:80]
        query = str(args.get("query", "")).strip()
        if query:
            return query[:80]
        return ""

    def _append_tool_result(self, rendered: str, *, is_diff: bool = False) -> None:
        t = self._theme_tui()
        lines = rendered.splitlines()
        if len(lines) <= 10:
            if is_diff:
                self._timeline_append(Syntax(rendered, "diff", line_numbers=True))
            else:
                result_text = Text()
                result_text.append(" RESULT ", style=f"bold black on {t['accent_a']}")
                self._timeline_append(result_text)
                self._timeline_append(Text(rendered, style=t["text_soft"]))
            return

        preview = "\n".join(lines[:8])
        header = Text()
        if is_diff:
            header.append(" DIFF ", style=f"bold black on {t['accent_a']}")
        else:
            header.append(" RESULT ", style=f"bold black on {t['accent_a']}")
        header.append(f"  {len(lines)} lines", style="dim")
        header.append("  Ctrl+E expand", style="dim italic")

        collapsed_group = Group(
            header,
            Text(preview, style="dim"),
            Text("  ...", style=t["panel_muted"]),
        )
        idx = self._timeline_append(collapsed_group)
        self._collapsed_tool_results[idx] = (rendered, is_diff)
        self._last_collapsed_tool_index = idx

    def _animate_int(self, key: str) -> None:
        target = int(self._usage_target[key])
        current = int(self._usage_display[key])
        if current == target:
            return
        delta = target - current
        step = max(1, int(abs(delta) * 0.25))
        self._usage_display[key] = current + (step if delta > 0 else -step)
        if (delta > 0 and self._usage_display[key] > target) or (delta < 0 and self._usage_display[key] < target):
            self._usage_display[key] = target

    def _animate_usage_numbers(self) -> None:
        self._animate_int("prompt")
        self._animate_int("completion")
        self._animate_int("total")
        cost_target = float(self._usage_target["cost"])
        cost_current = float(self._usage_display["cost"])
        if abs(cost_target - cost_current) < 0.00001:
            self._usage_display["cost"] = cost_target
        else:
            # Exponential easing for smooth UI counter motion.
            self._usage_display["cost"] = cost_current + (cost_target - cost_current) * 0.24

    def _build_suggestions(self) -> list[str]:
        base = list(self.runner.slash_commands())
        extra = [
            "/build fast",
            "/build balanced",
            "/build deep",
            "/approve on",
            "/approve off",
            "/themes",
            f"/theme {self._theme_name}",
            "/doctor",
            f"/model {self.runner.model_name}",
        ]
        for p in list_providers():
            extra.append(f"/provider {p}")
        for theme_name in list_theme_names():
            extra.append(f"/theme {theme_name}")
        for item in list_saved_chat_sessions(limit=30):
            sid = str(item.get("session_id", "")).strip()
            if sid:
                extra.append(f"/session {sid}")

        seen: set[str] = set()
        ordered: list[str] = []
        for cmd in self._recent_slash_commands + self._hot_slash_commands + base + extra:
            c = cmd.strip()
            if not c or c in seen:
                continue
            seen.add(c)
            ordered.append(c)
        return ordered

    def _refresh_input_suggester(self) -> None:
        suggestions = self._build_suggestions()
        widget = self.query_one("#prompt_input")
        if isinstance(widget, Input):
            widget.suggester = SuggestFromList(suggestions, case_sensitive=False)
        elif self._use_textarea:
            # TextArea doesn't have built-in suggester; keep suggestions for command drawer.
            return

    def _extract_prompt_command(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if not text:
            return ""
        first_line = text.splitlines()[-1].strip()
        if not first_line.startswith("/"):
            return ""
        return first_line

    def _matching_slash_items(self, command_text: str) -> list[str]:
        if not command_text.startswith("/"):
            return []
        all_items = self._build_suggestions()
        q = command_text.lower()
        if q == "/":
            return all_items[: self._slash_max_rows]
        starts = [item for item in all_items if item.lower().startswith(q)]
        if starts:
            return starts[: self._slash_max_rows]
        fuzzy = [item for item in all_items if q in item.lower()]
        return fuzzy[: self._slash_max_rows]

    def _render_slash_panel(self) -> None:
        panel = self.query_one("#slash_panel", Static)
        if not self._slash_panel_visible or not self._slash_items:
            panel.display = False
            panel.update("")
            return

        t = self._theme_tui()
        panel.display = True
        header = Text()
        header.append(" / ", style=f"bold black on {t['accent_a']}")
        header.append("  Command Palette", style=f"bold {t['accent_a']}")
        header.append("  Tab fill  ↑↓ select  Enter submit", style="dim")

        lines_text = Text()
        for i, item in enumerate(self._slash_items):
            if i > 0:
                lines_text.append("\n")
            if i == self._slash_selected:
                lines_text.append(f"  ▸ {item}", style=f"bold black on {t['accent_b']}")
            else:
                lines_text.append(f"    {item}", style=t["accent_a"])

        from rich.console import Group as RGroup
        panel.update(RGroup(header, lines_text))

    def _refresh_slash_panel(self, force: bool = False) -> None:
        prompt = self._prompt_get_value()
        if not force and prompt == self._last_prompt_text:
            return
        self._last_prompt_text = prompt

        cmd = self._extract_prompt_command(prompt)
        items = self._matching_slash_items(cmd)
        self._slash_items = items
        self._slash_panel_visible = bool(cmd) and bool(items)
        if self._slash_items:
            self._slash_selected = min(self._slash_selected, len(self._slash_items) - 1)
        else:
            self._slash_selected = 0
        self._render_slash_panel()

    def _move_slash_selection(self, delta: int) -> None:
        if not self._slash_panel_visible or not self._slash_items:
            return
        self._slash_selected = (self._slash_selected + delta) % len(self._slash_items)
        self._render_slash_panel()

    def _apply_slash_selection(self) -> bool:
        if not self._slash_panel_visible or not self._slash_items:
            return False
        chosen = self._slash_items[self._slash_selected]
        self._prompt_set_value(chosen)
        self._refresh_slash_panel(force=True)
        return True

    def _remember_recent_slash(self, raw_text: str) -> None:
        cmd = self._extract_prompt_command(raw_text).strip()
        if not cmd:
            return
        self._recent_slash_commands = [c for c in self._recent_slash_commands if c != cmd]
        self._recent_slash_commands.insert(0, cmd)
        self._recent_slash_commands = self._recent_slash_commands[:16]

    def _command_drawer_content(self) -> str:
        lines = ["[b]Commands[/b]", ""]
        desc = {
            "/help": "查看命令帮助",
            "/provider [name]": "切换 provider",
            "/providers": "列出 provider",
            "/model [name]": "切换模型",
            "/build [fast|balanced|deep]": "切换构建模式",
            "/approve [on|off]": "风险操作自动审批",
            "/sessions": "查看会话列表",
            "/session [id]": "切换会话",
            "/new": "创建新会话",
            "/themes": "列出主题",
            "/theme [name]": "切换主题",
            "/doctor [provider]": "诊断 API Key 和 .env",
            "/stats": "显示统计",
            "/clear": "清屏",
            "/exit": "退出",
        }
        for cmd in self.runner.slash_commands():
            lines.append(f"[cyan]{cmd}[/cyan]  [dim]{desc.get(cmd, '')}[/dim]")

        lines.append("")
        lines.append("[b]Quick Fill[/b]")
        lines.append("[dim]/build fast | /build deep[/dim]")
        lines.append("[dim]/approve on | /approve off[/dim]")
        lines.append(f"[dim]/theme {self._theme_name}[/dim]")
        lines.append("[dim]/themes[/dim]")
        lines.append("[dim]/doctor[/dim]")
        lines.append(f"[dim]/provider {self.runner.provider_name}[/dim]")
        lines.append(f"[dim]/model {self.runner.model_name}[/dim]")

        sessions = list_saved_chat_sessions(limit=6)
        if sessions:
            lines.append("")
            lines.append("[b]Recent Session IDs[/b]")
            for s in sessions:
                sid = str(s.get("session_id", ""))
                lines.append(f"[dim]/session {sid}[/dim]")

        if self._recent_slash_commands:
            lines.append("")
            lines.append("[b]Recent Commands[/b]")
            for cmd in self._recent_slash_commands[:6]:
                lines.append(f"[dim]{cmd}[/dim]")
        return "\n".join(lines)

    def _render_command_drawer(self) -> None:
        drawer = self.query_one("#command_drawer", Static)
        showing = self._drawer_width > 0 or self._drawer_target_width > 0
        drawer.display = showing
        drawer.styles.width = self._drawer_width
        if not showing:
            drawer.update("")
            return
        if self._drawer_width <= 4:
            drawer.update("[dim]...[/dim]")
            return
        drawer.update(self._command_drawer_content())

    def _animate_drawer_step(self) -> None:
        if self._drawer_width == self._drawer_target_width:
            return
        if self._drawer_width < self._drawer_target_width:
            self._drawer_width = min(self._drawer_target_width, self._drawer_width + self._drawer_step)
        else:
            self._drawer_width = max(self._drawer_target_width, self._drawer_width - self._drawer_step)
        self._render_command_drawer()

    def _tick_ui(self) -> None:
        self._flow_phase = (self._flow_phase + 1) % 1000
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
        if self._scanner_pos <= 0:
            self._scanner_dir = 1
        elif self._scanner_pos >= 19:
            self._scanner_dir = -1
        self._scanner_pos += self._scanner_dir
        self._refresh_flow_visuals()
        self._refresh_status_bar()
        self._animate_drawer_step()
        self._animate_usage_numbers()
        self._refresh_slash_panel()
        if self._live_mode:
            self._flush_stream_preview()
        self._refresh_side()

    def consume_runtime_event(self, item: _RuntimePayload) -> None:
        event_type = item.event_type
        payload = item.payload

        if event_type == "turn.user":
            badge = Text()
            badge.append(" YOU ", style="bold black on yellow")
            badge.append(f"  {payload.get('text', '')}", style="white")
            self._timeline_append_message("you", badge)
        elif event_type == "status.stage":
            self._flow_active = True
            self._flow_label, self._flow_detail = self._normalize_stage(
                str(payload.get("label", "thinking")),
                str(payload.get("detail", "")),
            )
        elif event_type == "status.clear":
            self._flow_active = False
            self._flow_label = "idle"
            self._flow_detail = ""
        elif event_type == "assistant.reasoning.start":
            self._live_mode = "reasoning"
            self._reasoning_buffer = ""
            self._reasoning_started_at = time.monotonic()
            self._flush_stream_preview(force=True)
        elif event_type == "assistant.reasoning.token":
            self._reasoning_buffer += str(payload.get("token", ""))
            self._flush_stream_preview()
        elif event_type == "assistant.reasoning.end":
            if self._reasoning_buffer:
                duration = max(0.0, time.monotonic() - self._reasoning_started_at)
                chars = len(self._reasoning_buffer)
                self._last_reasoning_full = self._reasoning_buffer
                info = Text()
                info.append(" THINKING ", style="bold black on bright_black")
                info.append(f"  {duration:.1f}s  {chars} chars  ", style="dim")
                info.append("Ctrl+R to expand", style="dim italic")
                self._timeline_append(info)
            self._reasoning_buffer = ""
            self._live_mode = ""
            self._flush_stream_preview(force=True)
        elif event_type == "assistant.stream.start":
            self._live_mode = "assistant"
            self._assistant_buffer = ""
            self._flow_label, self._flow_detail = "writing...", "streaming response"
            self._flush_stream_preview(force=True)
        elif event_type == "assistant.stream.token":
            self._assistant_buffer += str(payload.get("token", ""))
            self._flush_stream_preview()
        elif event_type == "assistant.stream.end":
            badge = Text()
            badge.append(" ASSISTANT ", style="bold black on cyan")
            self._timeline_append_message(
                "assistant",
                Group(badge, Text(), Markdown(self._assistant_buffer or "")),
            )
            self._assistant_buffer = ""
            self._live_mode = ""
            self._flush_stream_preview(force=True)
        elif event_type == "system.message":
            sys_text = Text()
            sys_text.append("  │ ", style="bright_black")
            sys_text.append(str(payload.get("text", "")), style="dim")
            self._timeline_append(sys_text)
        elif event_type == "tool.call":
            risky = bool(payload.get("risky"))
            self._flow_active = True
            self._flow_label = "running tool..."
            self._flow_detail = str(payload.get("name", "tool"))
            tool_name = str(payload.get("name", ""))
            summary = self._summarize_tool_args(payload.get("args"))

            badge = Text()
            if risky:
                badge.append(" RISK ", style="bold white on red")
            else:
                badge.append(" TOOL ", style="bold black on bright_magenta")
            badge.append(f"  {tool_name}", style="bold bright_magenta")
            if summary:
                badge.append(f"  {summary}", style="dim bright_magenta")
            self._timeline_append_message("tool", badge)
        elif event_type == "tool.result":
            rendered = str(payload.get("result", ""))
            elapsed = float(payload.get("elapsed_ms", 0.0) or 0.0)
            self._flow_active = True
            self._flow_label = "tool done..."
            self._flow_detail = f"{elapsed:.0f}ms"
            elapsed_text = Text()
            elapsed_text.append("  │ ", style="bright_black")
            elapsed_text.append(f"completed in {elapsed:.0f}ms", style="dim")
            self._timeline_append(elapsed_text)
            lines = rendered.splitlines()
            is_diff = len(lines) >= 2 and lines[0].startswith("---") and lines[1].startswith("+++")
            self._append_tool_result(rendered, is_diff=is_diff)
        elif event_type == "tool.plan":
            self._flow_active = True
            self._flow_label = "planning tools..."
            count = int(payload.get("count", 0) or 0)
            plan_text = Text()
            plan_text.append("  │ ", style="bright_black")
            plan_text.append(f"planning {count} tool call{'s' if count != 1 else ''}", style="dim cyan")
            self._timeline_append(plan_text)
        elif event_type in {"session.switched", "runtime.provider.changed", "runtime.model.changed", "runtime.mode.changed", "runtime.theme.changed"}:
            self._refresh_input_suggester()
            if event_type == "session.switched":
                sid = str(payload.get("session_id", ""))
                self._timeline_append_message("session", f"[green]session switched[/green] {sid}")
                self._render_messages_from_runner()
            elif event_type == "runtime.theme.changed":
                self._theme_name = str(payload.get("theme", "")).strip() or self._theme_name
                self._apply_theme(force=True)
                self._timeline_append(f"[dim]theme switched: {self._theme_name}[/dim]")

        self._refresh_side()
        self._refresh_flow_visuals()
        self._refresh_status_bar()
        self._render_command_drawer()

    @work(thread=True, exclusive=True)
    def _run_user_turn(self, text: str) -> None:
        result = self.runner.handle_input(text)
        self.call_from_thread(self._after_turn, result)

    def _after_turn(self, result: dict[str, Any]) -> None:
        kind = result.get("kind")
        if kind == "command":
            action = result.get("action")
            if action == "help":
                self._timeline_append("[b]/ Commands[/b]\n" + "\n".join(result.get("commands") or self.runner.slash_commands()))
            elif action == "themes":
                lines = result.get("themes") or []
                if lines:
                    self._push_dialog("Themes", "\n".join(lines))
            elif action == "theme_changed":
                theme = str(result.get("theme", "")).strip()
                if theme:
                    self._theme_name = theme
                    self._apply_theme(force=True)
                    self._refresh_status_bar()
            elif action == "doctor":
                lines = result.get("lines") or []
                if lines:
                    self._push_dialog("Env Doctor", "\n".join(lines))
            elif action == "clear":
                self._render_messages_from_runner()
            elif action == "sessions":
                lines = result.get("sessions") or []
                if lines:
                    self._push_dialog("Saved Sessions", "\n".join(lines) + "\n\n[dim]使用 /session <id> 切换，/new 创建新会话[/dim]")
            elif action == "session_switched":
                self._render_messages_from_runner()
                self._refresh_input_suggester()
            elif action == "exit":
                self.exit()
        elif kind == "exit":
            self.exit()
        self._refresh_side()
        self._refresh_flow_visuals()
        self._render_command_drawer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if self._slash_panel_visible and self._slash_items:
            self._apply_slash_selection()
            text = self._prompt_get_value().strip()
        event.input.value = ""
        if not text:
            return
        self._remember_recent_slash(text)
        self._refresh_input_suggester()
        self._input_history.append(text)
        self._history_index = len(self._input_history)
        self._run_user_turn(text)

    def on_key(self, event: Key) -> None:
        if event.key == "escape" and self._dialog_is_open():
            self.action_close_dialog()
            event.prevent_default()
            return
        if self._slash_panel_visible:
            if event.key in {"up", "ctrl+p"}:
                self._move_slash_selection(-1)
                event.prevent_default()
                return
            if event.key in {"down", "ctrl+n"}:
                self._move_slash_selection(1)
                event.prevent_default()
                return
            if event.key == "enter" and self._use_textarea:
                self.action_submit_prompt()
                event.prevent_default()
                return
            if event.key == "tab":
                if self._apply_slash_selection():
                    event.prevent_default()
                    return
        if not self._use_textarea:
            return
        if event.key == "ctrl+enter":
            self.action_submit_prompt()
            event.prevent_default()

    def _prompt_get_value(self) -> str:
        widget = self.query_one("#prompt_input")
        if isinstance(widget, Input):
            return widget.value
        if self._use_textarea:
            return str(getattr(widget, "text", ""))
        return ""

    def _prompt_set_value(self, text: str) -> None:
        widget = self.query_one("#prompt_input")
        if isinstance(widget, Input):
            widget.value = text
            return
        if self._use_textarea:
            if hasattr(widget, "load_text"):
                widget.load_text(text)
            else:
                setattr(widget, "text", text)

    def action_submit_prompt(self) -> None:
        if self._slash_panel_visible and self._slash_items:
            self._apply_slash_selection()
        text = self._prompt_get_value().strip()
        self._prompt_set_value("")
        if not text:
            return
        self._remember_recent_slash(text)
        self._refresh_input_suggester()
        self._input_history.append(text)
        self._history_index = len(self._input_history)
        self._run_user_turn(text)

    def action_history_prev(self) -> None:
        if not self._input_history:
            return
        self._history_index = max(0, self._history_index - 1)
        self._prompt_set_value(self._input_history[self._history_index])

    def action_history_next(self) -> None:
        if not self._input_history:
            return
        self._history_index = min(len(self._input_history), self._history_index + 1)
        if self._history_index >= len(self._input_history):
            self._prompt_set_value("")
            return
        self._prompt_set_value(self._input_history[self._history_index])

    def action_clear_chat(self) -> None:
        self._render_messages_from_runner()
        self._refresh_side()
        self._render_command_drawer()

    def action_cancel_stream(self) -> None:
        self.runner.request_cancel()
        self._timeline_append("[dim]• cancel requested[/dim]")

    def action_expand_tool_result(self) -> None:
        idx = self._last_collapsed_tool_index
        if idx < 0:
            self._timeline_append("[dim]no collapsed tool result[/dim]")
            return
        packed = self._collapsed_tool_results.get(idx)
        if not packed:
            self._timeline_append("[dim]no collapsed tool result[/dim]")
            return
        full, is_diff = packed
        if is_diff:
            self._timeline_replace(idx, Syntax(full, "diff", line_numbers=True))
        else:
            self._timeline_replace(idx, "[blue]tool result[/blue]\n" + full)
        self._collapsed_tool_results.pop(idx, None)
        self._last_collapsed_tool_index = -1

    def action_toggle_commands(self) -> None:
        if self._compact_mode:
            self._timeline_append("[dim]compact 模式下命令抽屉不可见（Ctrl+B 退出 compact）[/dim]")
            return
        self._drawer_open = not self._drawer_open
        self._drawer_target_width = self._drawer_max_width if self._drawer_open else 0
        self._render_command_drawer()

    def action_toggle_compact(self) -> None:
        self._compact_mode = not self._compact_mode
        self._apply_compact_layout()
        msg = "compact mode: on" if self._compact_mode else "compact mode: off"
        self._timeline_append(f"[dim]{msg}[/dim]")
        self._refresh_status_bar()

    def action_expand_reasoning(self) -> None:
        if not self._last_reasoning_full.strip():
            self._timeline_append("[dim]no reasoning details[/dim]")
            return
        self._timeline_append_message(
            "reasoning",
            Group(Text("thinking details", style="dim"), Markdown(self._last_reasoning_full)),
        )

    def action_close_dialog(self) -> None:
        self._pop_dialog()

    def action_show_sessions(self) -> None:
        sessions = list_saved_chat_sessions(limit=12)
        if not sessions:
            self._timeline_append("[yellow]未找到会话记录[/yellow]")
            return
        lines = ["[b]Saved Sessions[/b]"]
        for s in sessions:
            when = s.get("updated_at") or "-"
            lines.append(
                f"{s['session_id']} | {s.get('provider', '-')}/{s.get('model', '-')} | {s.get('message_count', 0)} msg | {when}"
            )
        lines.append("[dim]输入 /session <id> 切换；输入 /new 新建会话[/dim]")
        self._push_dialog("Saved Sessions", "\n".join(lines))
