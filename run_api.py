"""Start API server for frontend integration."""

import argparse
import subprocess
import sys
from pathlib import Path


def _find_project_venv_python() -> Path | None:
    root = Path(__file__).resolve().parent
    if sys.platform.startswith("win"):
        candidate = root / "venv" / "Scripts" / "python.exe"
    else:
        candidate = root / "venv" / "bin" / "python"
    return candidate if candidate.exists() else None


def _relaunch_with_venv() -> bool:
    venv_python = _find_project_venv_python()
    if not venv_python:
        return False
    if Path(sys.executable).resolve() == venv_python.resolve():
        return False

    print("⚠️ 当前解释器缺少 uvicorn，正在切换到项目 venv 重新启动...", flush=True)
    cmd = [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run modular API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        if _relaunch_with_venv():
            return
        print("❌ 缺少 uvicorn，请先安装依赖后重试：")
        print("   1) venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        print("   2) venv\\Scripts\\python.exe run_api.py --host 127.0.0.1 --port 8000")
        raise SystemExit(1)

    uvicorn.run("api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
