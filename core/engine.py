# core/engine.py
# 🏎️ 经典 CLI 入口：复用 AgentRunner，保留现有 run.py 调用方式

from __future__ import annotations

from . import ui
from .agent_runner import AgentRunner, load_chat_history
from .opencode_runtime import RichConsoleHook
from skills import tools_schema


def run():
    runner = AgentRunner(approval_callback=ui.ask_for_approval)
    runner.on(RichConsoleHook(ui, runner.runtime).handle)

    ui.print_welcome(
        len(tools_schema),
        model_name=runner.model_name,
        build_mode=runner.build_mode,
        provider_name=runner.provider_name,
    )
    ui.print_slash_help(runner.slash_commands())

    prev_history = load_chat_history()
    if prev_history and len(prev_history) > 1:
        resume = ui.ask_resume_chat(len(prev_history) - 1)
        runner.resume_history(resume=resume)

    while not runner.should_exit:
        try:
            user_input = ui.get_user_input().strip()
            result = runner.handle_input(user_input)
            if result.get("kind") == "noop":
                continue
            if result.get("kind") == "command":
                action = result.get("action")
                if action == "help":
                    ui.print_slash_help(result.get("commands") or runner.slash_commands())
                elif action == "clear":
                    ui.clear_screen()
                    ui.print_welcome(
                        len(tools_schema),
                        model_name=runner.model_name,
                        build_mode=runner.build_mode,
                        provider_name=runner.provider_name,
                    )
                    ui.print_slash_help(runner.slash_commands())
                elif action == "stats":
                    progress = 0.0
                    if runner.runtime.max_steps > 0:
                        progress = min(1.0, runner.runtime.agent_steps / float(runner.runtime.max_steps))
                    ui.print_runtime_meter(runner.runtime.get_stats(), progress=progress)
                elif action == "doctor":
                    for line in result.get("lines") or []:
                        ui.print_system(line)
                elif action == "themes":
                    ui.print_system("themes:")
                    for line in result.get("themes") or []:
                        ui.print_system(line)
                elif action == "exit":
                    break
            elif result.get("kind") == "exit":
                break
        except KeyboardInterrupt:
            runner.request_cancel()
            runner.runtime.system_message("用户中断")
            if runner.should_exit:
                break
        except Exception as e:
            runner.runtime.system_message(f"异常: {e}")
            runner.runtime.finish("runtime_error")
            break
