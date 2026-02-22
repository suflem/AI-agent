#skill: read_files
import os
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# === 定义说明书 (Schema) ===
read_file_schema = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取文件的具体内容。当你需要分析代码、总结文档、查看日志或修复Bug时，必须先调用此工具读取文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要读取的文件名 (如 test1.py, data/log.txt)"
                }
            },
            "required": ["filename"]
        }
    }
}


# === 注册并实现 ===
@register(read_file_schema)
def read_file(filename: str):
    """
    读取文件内容，带有安全限制和错误处理
    """
    file_obj, err = guard_path(filename, must_exist=True, for_write=False)
    if err:
        return err

    if file_obj.is_dir():
        return f"❌ 错误：'{_display_path(file_obj)}' 是一个文件夹，请使用 list_dir 工具查看。"

    try:
        # 2. 读取文件 (默认使用 utf-8)
        with open(file_obj, 'r', encoding='utf-8') as f:
            content = f.read()

            # 3. 防止 Token 爆炸：限制读取长度
            # 如果文件太大（超过 8000 字符），只返回前 8000 个字，并提示用户
            MAX_CHARS = 8000
            if len(content) > MAX_CHARS:
                return (f"⚠️ 文件内容过长 [{_display_path(file_obj)}] (总长 {len(content)} 字符)，仅显示前 {MAX_CHARS} 个字符：\n"
                        "--------------------------------------------------\n"
                        f"{content[:MAX_CHARS]}\n"
                        "--------------------------------------------------\n"
                        "(内容已截断)")

            return content

    except UnicodeDecodeError:
        return "❌ 读取失败：文件编码不是 UTF-8 (可能是二进制文件或图片)。"
    except Exception as e:
        return f"❌ 读取发生未知错误: {str(e)}"