# skills/code_tools_simple.py

from .registry import register_simple  # 导入简易注册器
from .path_safety import guard_path, WORKSPACE_ROOT

# ==========================================
# 第一部分：身份卡片 (META)
# ==========================================
META = {
    "name": "write_code_simple",
    "description": "写代码工具，当用户让你写一个 Python 脚本时调用",
    "args": {
        "filename": "文件名 (记得带.py后缀)",
        "content": "代码的全部内容"
    }
}


# ==========================================
# 第二部分：执行逻辑 (run函数)
# ==========================================
@register_simple(META)
def run(filename, content):
    try:
        file_obj, err = guard_path(filename, must_exist=False, for_write=True)
        if err:
            return err
        if not file_obj.parent.exists():
            file_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(content)
        try:
            display = str(file_obj.relative_to(WORKSPACE_ROOT))
        except Exception:
            display = str(file_obj)
        return f"✅ (简易版) 文件 {display} 写入成功！"
    except Exception as e:
        return f"❌ 出错了: {e}"