from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


@dataclass
class SessionSummary:
    session_id: str
    provider: str = ""
    model: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    events: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    reason: str = ""


def _iter_records(log_path: str):
    if not os.path.exists(log_path):
        return
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except Exception:
                continue


def summarize_sessions(log_path: str = "data/runtime_events.jsonl", limit: int = 0) -> list[SessionSummary]:
    sessions: dict[str, SessionSummary] = {}
    for rec in _iter_records(log_path):
        sid = str(rec.get("session_id") or "")
        if not sid:
            continue
        info = sessions.get(sid)
        if not info:
            info = SessionSummary(session_id=sid, started_at=float(rec.get("at") or 0.0))
            sessions[sid] = info

        info.events += 1
        info.started_at = min(info.started_at or float(rec.get("at") or 0.0), float(rec.get("at") or 0.0))
        info.finished_at = max(info.finished_at, float(rec.get("at") or 0.0))

        event = str(rec.get("event") or "")
        payload = rec.get("payload") or {}
        stats = rec.get("stats") or {}

        if event == "runtime.started":
            info.provider = str(payload.get("provider") or info.provider)
            info.model = str(payload.get("model") or info.model)
        elif event == "runtime.finished":
            info.reason = str(payload.get("reason") or info.reason)
            s = payload.get("stats") or {}
            if isinstance(s, dict):
                info.tool_calls = int(s.get("tool_calls") or info.tool_calls)
                info.tool_failures = int(s.get("tool_failures") or info.tool_failures)

        if info.tool_calls == 0 and isinstance(stats, dict):
            info.tool_calls = max(info.tool_calls, int(stats.get("tool_calls") or 0))
            info.tool_failures = max(info.tool_failures, int(stats.get("tool_failures") or 0))

    ordered = sorted(sessions.values(), key=lambda s: s.started_at, reverse=True)
    if limit > 0:
        return ordered[:limit]
    return ordered


def list_sessions(log_path: str = "data/runtime_events.jsonl", limit: int = 20) -> int:
    sessions = summarize_sessions(log_path)
    if not sessions:
        console.print("[yellow]未找到 runtime 会话日志。[/yellow]")
        return 1

    table = Table(title=f"Runtime Sessions ({min(limit, len(sessions))}/{len(sessions)})")
    table.add_column("Session", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model", style="magenta")
    table.add_column("Started")
    table.add_column("Duration", justify="right")
    table.add_column("Events", justify="right")
    table.add_column("Tools", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Reason")

    for item in sessions[:limit]:
        started = datetime.fromtimestamp(item.started_at).strftime("%m-%d %H:%M:%S") if item.started_at else "-"
        duration = max(0.0, item.finished_at - item.started_at)
        table.add_row(
            item.session_id,
            item.provider or "-",
            item.model or "-",
            started,
            f"{duration:.1f}s",
            str(item.events),
            str(item.tool_calls),
            str(item.tool_failures),
            item.reason or "-",
        )

    console.print(table)
    return 0


def replay_session(
    session_id: str | None = None,
    *,
    log_path: str = "data/runtime_events.jsonl",
    speed: float = 0.0,
    max_events: int = 500,
) -> int:
    records = list(_iter_records(log_path) or [])
    if not records:
        console.print("[yellow]未找到 runtime 会话日志。[/yellow]")
        return 1

    if not session_id or session_id == "latest":
        candidates = summarize_sessions(log_path)
        if not candidates:
            console.print("[yellow]没有可回放的会话。[/yellow]")
            return 1
        session_id = candidates[0].session_id

    chosen = [r for r in records if str(r.get("session_id") or "") == session_id]
    if not chosen:
        console.print(f"[red]未找到会话: {session_id}[/red]")
        return 1

    chosen.sort(key=lambda r: float(r.get("at") or 0.0))
    if max_events > 0 and len(chosen) > max_events:
        start_floor = max(0, len(chosen) - max_events * 3)
        start_idx = len(chosen) - max_events
        boundaries = {"turn.user", "assistant.stream.start", "tool.call", "runtime.started", "system.message"}
        for i in range(start_idx, start_floor - 1, -1):
            if str(chosen[i].get("event") or "") in boundaries:
                start_idx = i
                break
        candidate = chosen[start_idx:]
        while candidate and str(candidate[0].get("event") or "") in {"assistant.stream.token", "assistant.stream.end"}:
            candidate = candidate[1:]
        chosen = candidate
        console.print(f"[yellow]会话事件过多，已截断回放（{len(chosen)} 条）。[/yellow]")

    console.print(Panel(f"Replay Session: [bold cyan]{session_id}[/bold cyan]\nEvents: {len(chosen)}", border_style="cyan"))

    streaming = False
    for rec in chosen:
        event = str(rec.get("event") or "")
        payload = rec.get("payload") or {}

        if event == "turn.user":
            text = str(payload.get("text") or "")
            console.print(Panel(Text(text), title="[bold yellow]User[/bold yellow]", border_style="yellow"))
        elif event == "assistant.stream.start":
            console.print("\n[bold cyan]assistant[/bold cyan] [dim](replay stream)[/dim]")
            streaming = True
        elif event == "assistant.stream.token":
            console.print(str(payload.get("token") or ""), end="", highlight=False)
        elif event == "assistant.stream.end":
            if streaming:
                console.print()
            streaming = False
        elif event == "tool.call":
            name = str(payload.get("name") or "")
            risky = "RISK" if payload.get("risky") else "SAFE"
            console.print(f"[magenta]tool[/magenta] [{risky}] {name}")
        elif event == "tool.result":
            result = payload.get("result")
            text = str(result)
            if len(text) > 400:
                text = text[:400] + "... (truncated)"
            border = "green" if payload.get("success") else "red"
            console.print(Panel(Text(text), title="Tool Result", border_style=border))
        elif event == "system.message":
            console.print(f"[dim]• {payload.get('text', '')}[/dim]")
        elif event == "runtime.finished":
            stats = payload.get("stats") or {}
            console.print(
                Panel(
                    f"reason={payload.get('reason', '-')}\n"
                    f"turns={stats.get('turns', 0)} steps={stats.get('steps', 0)} "
                    f"tools={stats.get('tool_calls', 0)} errors={stats.get('tool_failures', 0)}",
                    title="[bold]Replay Summary[/bold]",
                    border_style="bright_blue",
                )
            )

        if speed > 0:
            time.sleep(min(speed, 0.5))

    return 0
