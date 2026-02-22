# run.py
# 启动程序

import argparse
from core.engine import run
from core.runtime_replay import list_sessions, replay_session
from skills import available_functions


def _run_health():
    fn = available_functions.get("runtime_health")
    if not fn:
        print("runtime_health 不可用")
        return 1
    print(fn(level="full"))
    return 0


def _run_smoke():
    fn = available_functions.get("runtime_smoke")
    if not fn:
        print("runtime_smoke 不可用")
        return 1
    print(fn(cleanup=True))
    return 0

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="AI Agent runner")
        parser.add_argument("--health", action="store_true", help="运行稳定性健康检查并退出")
        parser.add_argument("--smoke", action="store_true", help="运行冒烟测试并退出")
        parser.add_argument("--sessions", action="store_true", help="列出 runtime 会话日志")
        parser.add_argument("--replay", nargs="?", const="latest", help="回放指定 session（默认最新）")
        parser.add_argument("--replay-speed", type=float, default=0.0, help="回放节奏秒数（0 为最快）")
        parser.add_argument("--replay-max-events", type=int, default=500, help="单次最多回放事件数（0 表示不限制）")
        parser.add_argument("--tui", action="store_true", help="启动 Textual TUI 模式")
        parser.add_argument("--compact", action="store_true", help="TUI 紧凑布局（隐藏右侧信息栏）")
        args = parser.parse_args()

        if args.health:
            raise SystemExit(_run_health())
        if args.smoke:
            raise SystemExit(_run_smoke())
        if args.sessions:
            raise SystemExit(list_sessions())
        if args.replay is not None:
            raise SystemExit(
                replay_session(
                    args.replay,
                    speed=max(args.replay_speed, 0.0),
                    max_events=max(args.replay_max_events, 0),
                )
            )
        if args.tui:
            try:
                from core.tui_app import AgentTUIApp
            except Exception as e:
                print(f"TUI 启动失败: {e}")
                raise SystemExit(1)
            AgentTUIApp(compact=args.compact).run()
            raise SystemExit(0)

        run()
    except KeyboardInterrupt:
        print("\n👋 Bye!")
