# skills/__init__.py
# 自动发现并加载所有 skill 模块

import importlib
import pkgutil
from pathlib import Path

from skills.registry import registry

# 不参与自动加载的模块（内部基础设施）
_SKIP_MODULES = {"registry", "path_safety", "__init__"}

# 自动扫描 skills/ 目录下所有 .py 文件并导入
# 导入时会触发 @registry.register 装饰器完成注册
_pkg_dir = str(Path(__file__).resolve().parent)
for _finder, _name, _ispkg in pkgutil.iter_modules([_pkg_dir]):
    if _name.startswith("_") or _name in _SKIP_MODULES:
        continue
    try:
        importlib.import_module(f"skills.{_name}")
    except Exception as _e:
        import sys
        print(f"⚠️  跳过加载 skills/{_name}: {_e}", file=sys.stderr)

# 方便外部调用，供 engine.py 使用
tools_schema = registry.tools_schema
available_functions = registry.executable_functions
