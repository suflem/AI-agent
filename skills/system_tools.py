# skills/system_tools.py
import psutil
from .registry import registry

sys_status_schema = {
    "type": "function",
    "function": {
        "description": "获取当前电脑CPU和内存状态",
        "parameters": {"type": "object", "properties": {}}
    }
}

@registry.register(sys_status_schema)
def get_system_status():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    return f"CPU: {cpu}%, Memory: {mem.percent}%"