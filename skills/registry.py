# skills/registry.py

class SkillRegistry:
    def __init__(self):
        self.tools_schema = [] 
        self.executable_functions = {}

    def register(self, schema):
        """(高级版) 原生注册方式，适合需要精细控制参数类型的高级开发者"""
        def decorator(func):
            self.executable_functions[func.__name__] = func
            # 确保函数名一致
            schema["function"]["name"] = func.__name__
            self.tools_schema.append(schema)
            return func
        return decorator

    def register_simple(self, meta_info):
        """
        (简易版) 适配 PAPS 规范的注册器
        自动将简单的字典转换为 OpenAI 复杂的 JSON Schema

        meta_info 格式:
          name: str          — 工具名
          description: str   — 工具描述
          args: dict         — 参数定义，支持两种写法:
            简写: {"query": "搜索关键词"}                    → 默认 string, required
            详写: {"query": {"desc": "搜索关键词", "type": "string", "required": True, "default": ""}}
                  type 可选: string / integer / number / boolean / array / object
                  required 默认 True; 提供 default 时自动变为 optional
        """
        # 类型映射
        _TYPE_MAP = {
            "string": "string", "str": "string",
            "integer": "integer", "int": "integer",
            "number": "number", "float": "number",
            "boolean": "boolean", "bool": "boolean",
            "array": "array", "list": "array",
            "object": "object", "dict": "object",
        }

        def decorator(func):
            properties = {}
            required = []

            for arg_name, arg_spec in meta_info.get("args", {}).items():
                # 简写: 值就是描述字符串
                if isinstance(arg_spec, str):
                    properties[arg_name] = {"type": "string", "description": arg_spec}
                    required.append(arg_name)
                    continue

                # 详写: 值是 dict
                desc = arg_spec.get("desc", arg_spec.get("description", arg_name))
                json_type = _TYPE_MAP.get(str(arg_spec.get("type", "string")).lower(), "string")
                prop = {"type": json_type, "description": desc}

                # enum 支持
                if "enum" in arg_spec:
                    prop["enum"] = arg_spec["enum"]

                # items 支持 (array 子类型)
                if json_type == "array" and "items" in arg_spec:
                    prop["items"] = arg_spec["items"]

                properties[arg_name] = prop

                # required 判定: 显式 required=False 或提供了 default 则为可选
                is_required = arg_spec.get("required", "default" not in arg_spec)
                if is_required:
                    required.append(arg_name)

            openai_schema = {
                "type": "function",
                "function": {
                    "name": meta_info["name"],
                    "description": meta_info["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }

            self.executable_functions[meta_info["name"]] = func
            self.tools_schema.append(openai_schema)
            return func
        return decorator

# 初始化注册器
registry = SkillRegistry()

# 导出两个装饰器，方便不同水平的开发者使用
register = registry.register           # 给高手用
register_simple = registry.register_simple # 给小白用