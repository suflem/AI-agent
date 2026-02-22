import os
from .registry import register

# === 定义说明书 ===
find_file_schema = {
    "type": "function",
    "function": {
        "name": "find_file",
        "description": "在项目中搜索文件的具体路径。当你找不到某个文件，或者不知道文件在哪个目录下时，必须先调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要查找的文件名 (例如 test1.py)"
                },
                "search_path": {
                    "type": "string",
                    "description": "搜索起始路径 (默认为当前目录 . )"
                }
            },
            "required": ["filename"]
        }
    }
}


# === 注册并实现 ===
@register(find_file_schema)
def find_file(filename: str, search_path: str = "."):
    """
    递归搜索文件，返回所有匹配的路径
    """
    results = []

    # 定义要忽略的目录，防止搜索时间过长或搜到库文件
    IGNORE_DIRS = {'.git', '__pycache__', 'venv', '.idea', '.vscode', 'node_modules'}

    print(f"🔍 正在 '{search_path}' 下搜索 '{filename}'...")

    for root, dirs, files in os.walk(search_path):
        # 1. 修改 dirs 列表，原地移除忽略目录 (这样 os.walk 就不会进去了)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        # 2. 检查文件是否存在
        if filename in files:
            # 获取相对路径，方便阅读
            full_path = os.path.join(root, filename)
            results.append(full_path)

    if not results:
        return f"❌ 未找到文件: {filename}"

    if len(results) == 1:
        return f"✅ 找到 1 个文件: {results[0]}"

    # 如果找到多个同名文件，全部列出来
    return f"✅ 找到 {len(results)} 个同名文件:\n" + "\n".join(results)