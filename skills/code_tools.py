# skills/code_tools.py
from .registry import register  # 导入高级注册器
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)

# 1. 定义严谨的 Schema
write_code_schema = {
    "type": "function",
    "function": {
        "name": "write_code_file",  # 函数名
        "description": "【危险操作】编写或修改代码文件。仅当需要修复 Bug 或创建新功能脚本时使用。会覆盖同名文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "目标文件名，必须包含后缀 (如 skills/test.py)"
                },
                "content": {
                    "type": "string",
                    "description": "完整的代码内容，必须包含 import 和函数定义"
                }
            },
            "required": ["filename", "content"]
        }
    }
}


# 2. 注册并实现
@register(write_code_schema)
def write_code_file(filename, content):
    try:
        file_obj, err = guard_path(filename, must_exist=False, for_write=True)
        if err:
            return err

        if not file_obj.parent.exists():
            file_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ 成功：文件 '{_display_path(file_obj)}' 已写入/覆盖。"
    except Exception as e:
        return f"❌ 写入失败: {e}"
