from __future__ import annotations

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent Textual TUI")
    parser.add_argument("--compact", action="store_true", help="紧凑布局（隐藏右侧信息栏）")
    args = parser.parse_args()
    try:
        from core.tui_app import AgentTUIApp
    except Exception as e:
        print(f"TUI 启动失败: {e}")
        raise SystemExit(1)
    AgentTUIApp(compact=args.compact).run()
