import ast
import json
import os
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .registry import register

SKILLS_DIR = Path(__file__).resolve().parent
SKILLS_INIT = SKILLS_DIR / "__init__.py"
CONFIG_FILE = SKILLS_DIR.parent / "core" / "config.py"

TYPE_MAP = {
    "string": ("str", "string"),
    "integer": ("int", "integer"),
    "number": ("float", "number"),
    "boolean": ("bool", "boolean"),
    "object": ("dict", "object"),
    "array": ("list", "array"),
}


def _safe_identifier(raw: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", (raw or "").strip())
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        return ""
    if value[0].isdigit():
        value = f"tool_{value}"
    return value.lower()


def _safe_module_name(raw: str) -> str:
    base = (raw or "").strip().replace(".py", "")
    return _safe_identifier(base)


def _default_for_type(type_name: str):
    if type_name == "string":
        return ""
    if type_name == "integer":
        return 0
    if type_name == "number":
        return 0.0
    if type_name == "boolean":
        return False
    if type_name == "object":
        return {}
    if type_name == "array":
        return []
    return ""


def _py_literal(value: Any) -> str:
    return repr(value)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalize_params(params: Any) -> Tuple[List[Dict[str, Any]], str]:
    if params is None:
        return [], ""

    if isinstance(params, str):
        raw = params.strip()
        if not raw:
            return [], ""
        try:
            parsed = json.loads(raw)
        except Exception as e:
            return [], f"❌ params 不是合法 JSON: {e}"
    else:
        parsed = params

    if not isinstance(parsed, list):
        return [], "❌ params 必须是数组，每项形如 {name,type,description,required,default}"

    norm: List[Dict[str, Any]] = []
    seen = set()
    for idx, item in enumerate(parsed, 1):
        if not isinstance(item, dict):
            return [], f"❌ params 第 {idx} 项必须是对象"

        name = _safe_identifier(str(item.get("name", "")))
        if not name:
            return [], f"❌ params 第 {idx} 项 name 非法"
        if name in seen:
            return [], f"❌ params 中 name 重复: {name}"
        seen.add(name)

        raw_type = str(item.get("type", "string")).strip().lower()
        if raw_type not in TYPE_MAP:
            return [], f"❌ params 第 {idx} 项 type 不支持: {raw_type}"

        required = _as_bool(item.get("required", False))
        has_default = "default" in item
        default_value = item.get("default", _default_for_type(raw_type))
        description = str(item.get("description", "")).strip() or f"{name} parameter"

        if required:
            has_default = False

        norm.append(
            {
                "name": name,
                "type": raw_type,
                "description": description,
                "required": required,
                "has_default": has_default,
                "default": default_value,
            }
        )

    return norm, ""


def _build_signature(params: List[Dict[str, Any]]) -> str:
    chunks = []
    for p in params:
        py_type, _ = TYPE_MAP[p["type"]]
        if p["required"]:
            chunks.append(f'{p["name"]}: {py_type}')
        elif p["has_default"]:
            chunks.append(f'{p["name"]}: {py_type} = {_py_literal(p["default"])}')
        else:
            chunks.append(f'{p["name"]}: {py_type} = {_py_literal(_default_for_type(p["type"]))}')
    return ", ".join(chunks)


def _build_schema_dict(tool_name: str, description: str, params: List[Dict[str, Any]]) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    required: List[str] = []
    for p in params:
        _, json_type = TYPE_MAP[p["type"]]
        props[p["name"]] = {"type": json_type, "description": p["description"]}
        if p["required"]:
            required.append(p["name"])

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


def _default_function_body(tool_name: str, params: List[Dict[str, Any]]) -> str:
    names = [p["name"] for p in params]
    payload_expr = "{" + ", ".join([f'"{n}": {n}' for n in names]) + "}"
    return (
        f"payload = {payload_expr}\n"
        f'return "✅ {tool_name} executed.\\n" + json.dumps(payload, ensure_ascii=False, indent=2)'
    )


def _strip_markdown_code_block(text: str) -> str:
    data = (text or "").strip()
    if data.startswith("```"):
        lines = data.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        data = "\n".join(lines).strip()
    return data


def _validate_ai_body(body: str, signature: str) -> Tuple[bool, str]:
    trial = f"def _tmp({signature}):\n" + textwrap.indent(body.strip() or "return ''", "    ")
    try:
        ast.parse(trial)
        return True, ""
    except Exception as e:
        return False, str(e)


def _generate_ai_body(
    tool_name: str,
    description: str,
    params: List[Dict[str, Any]],
    signature: str,
    implementation_hint: str,
) -> Tuple[str, str]:
    fallback = _default_function_body(tool_name, params)
    api_key = os.getenv("KIMI_API_KEY", "").strip()
    if not api_key:
        return fallback, "fallback:no_api_key"

    try:
        from openai import OpenAI
    except Exception:
        return fallback, "fallback:missing_openai_sdk"

    try:
        base_url = os.getenv("KIMI_BASE_URL", "").strip() or "https://api.moonshot.cn/v1"
        model = os.getenv("KIMI_MODEL", "").strip() or "moonshot-v1-32k"
        client = OpenAI(api_key=api_key, base_url=base_url)

        prompt = {
            "tool_name": tool_name,
            "description": description,
            "params": params,
            "implementation_hint": implementation_hint or "",
            "constraints": [
                "return must be a string",
                "do not use network or filesystem by default",
                "no function definition, only function body",
                "keep code deterministic and concise",
            ],
        }

        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate Python function bodies for tool scaffolds. "
                        "Output ONLY code body, no markdown."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            max_tokens=800,
        )
        content = (resp.choices[0].message.content or "").strip()
        body = _strip_markdown_code_block(content)
        ok, err = _validate_ai_body(body, signature)
        if not ok or not body:
            return fallback, f"fallback:invalid_ai_body:{err}"
        if "return" not in body:
            body += '\nreturn "✅ executed"'
        return body, "ai"
    except Exception as e:
        return fallback, f"fallback:ai_error:{e}"


def _render_skill_code(
    module_name: str,
    tool_name: str,
    description: str,
    params: List[Dict[str, Any]],
    use_ai_completion: bool,
    implementation_hint: str,
) -> Tuple[str, str]:
    signature = _build_signature(params)
    schema_dict = _build_schema_dict(tool_name, description, params)
    schema_literal = json.dumps(schema_dict, ensure_ascii=False, indent=4)

    if use_ai_completion:
        body, body_source = _generate_ai_body(
            tool_name=tool_name,
            description=description,
            params=params,
            signature=signature,
            implementation_hint=implementation_hint,
        )
    else:
        body = _default_function_body(tool_name, params)
        body_source = "template"

    func_signature = signature if signature else ""
    code = f'''import json
from .registry import register

{tool_name}_schema = {schema_literal}


@register({tool_name}_schema)
def {tool_name}({func_signature}):
    """Auto-generated skill scaffold from Skill Studio."""
    try:
{textwrap.indent(body, "        ")}
    except Exception as e:
        return f"❌ {tool_name} failed: {{e}}"
'''
    return code, body_source


def _ensure_import_in_skills_init(module_name: str) -> Tuple[bool, str]:
    if not SKILLS_INIT.exists():
        return False, "❌ skills/__init__.py 不存在"
    import_line = f"from skills import {module_name}"
    text = SKILLS_INIT.read_text(encoding="utf-8")
    if import_line in text:
        return True, "already_imported"
    patched = text.rstrip() + f"\n{import_line}\n"
    SKILLS_INIT.write_text(patched, encoding="utf-8")
    return True, "import_added"


def _ensure_risky_tool(tool_name: str) -> Tuple[bool, str]:
    if not CONFIG_FILE.exists():
        return False, "❌ core/config.py 不存在"
    text = CONFIG_FILE.read_text(encoding="utf-8")
    if f'"{tool_name}"' in text or f"'{tool_name}'" in text:
        return True, "already_risky"

    marker = "RISKY_TOOLS = {"
    idx = text.find(marker)
    if idx < 0:
        return False, "❌ 未找到 RISKY_TOOLS 定义"

    insert_at = text.find("}", idx)
    if insert_at < 0:
        return False, "❌ RISKY_TOOLS 结构异常"

    patched = text[:insert_at] + f'    "{tool_name}",\n' + text[insert_at:]
    CONFIG_FILE.write_text(patched, encoding="utf-8")
    return True, "risky_added"


preview_schema = {
    "type": "function",
    "function": {
        "name": "skill_scaffold_preview",
        "description": "Generate a normalized Python skill scaffold preview from visual parameters, without writing files.",
        "parameters": {
            "type": "object",
            "properties": {
                "module_name": {"type": "string", "description": "Target module filename in skills/ (without .py)"},
                "tool_name": {"type": "string", "description": "Tool function name"},
                "description": {"type": "string", "description": "Tool description for schema"},
                "params": {"type": "array", "description": "List of parameter specs"},
                "use_ai_completion": {"type": "boolean", "description": "Let backend AI propose function body"},
                "implementation_hint": {"type": "string", "description": "Optional implementation behavior hint"},
            },
            "required": ["module_name", "tool_name", "description"],
        },
    },
}


@register(preview_schema)
def skill_scaffold_preview(
    module_name: str,
    tool_name: str,
    description: str,
    params=None,
    use_ai_completion: bool = True,
    implementation_hint: str = "",
):
    module_name = _safe_module_name(module_name)
    tool_name = _safe_identifier(tool_name)
    if not module_name:
        return "❌ module_name 非法"
    if not tool_name:
        return "❌ tool_name 非法"
    if not (description or "").strip():
        return "❌ description 不能为空"

    normalized, err = _normalize_params(params)
    if err:
        return err

    code, source = _render_skill_code(
        module_name=module_name,
        tool_name=tool_name,
        description=description.strip(),
        params=normalized,
        use_ai_completion=_as_bool(use_ai_completion, True),
        implementation_hint=implementation_hint or "",
    )
    return (
        f"🧩 Skill Scaffold Preview\n"
        f"module: skills/{module_name}.py\n"
        f"tool: {tool_name}\n"
        f"body_source: {source}\n\n"
        f"{code}"
    )


create_schema = {
    "type": "function",
    "function": {
        "name": "skill_scaffold_create",
        "description": (
            "Create a normalized skill module from visual parameters. "
            "Can auto-register import in skills/__init__.py and optionally mark as risky tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "module_name": {"type": "string", "description": "Target module filename in skills/ (without .py)"},
                "tool_name": {"type": "string", "description": "Tool function name"},
                "description": {"type": "string", "description": "Tool description for schema"},
                "params": {"type": "array", "description": "List of parameter specs"},
                "use_ai_completion": {"type": "boolean", "description": "Let backend AI propose function body"},
                "implementation_hint": {"type": "string", "description": "Optional implementation behavior hint"},
                "auto_register_import": {"type": "boolean", "description": "Auto add import to skills/__init__.py"},
                "mark_risky": {"type": "boolean", "description": "Auto add tool to core/config.py RISKY_TOOLS"},
                "overwrite": {"type": "boolean", "description": "Overwrite existing file if true"},
            },
            "required": ["module_name", "tool_name", "description"],
        },
    },
}


@register(create_schema)
def skill_scaffold_create(
    module_name: str,
    tool_name: str,
    description: str,
    params=None,
    use_ai_completion: bool = True,
    implementation_hint: str = "",
    auto_register_import: bool = True,
    mark_risky: bool = False,
    overwrite: bool = False,
):
    module_name = _safe_module_name(module_name)
    tool_name = _safe_identifier(tool_name)
    if not module_name:
        return "❌ module_name 非法"
    if not tool_name:
        return "❌ tool_name 非法"
    if not (description or "").strip():
        return "❌ description 不能为空"

    normalized, err = _normalize_params(params)
    if err:
        return err

    code, source = _render_skill_code(
        module_name=module_name,
        tool_name=tool_name,
        description=description.strip(),
        params=normalized,
        use_ai_completion=_as_bool(use_ai_completion, True),
        implementation_hint=implementation_hint or "",
    )

    target_file = SKILLS_DIR / f"{module_name}.py"
    if target_file.exists() and not _as_bool(overwrite, False):
        return f"❌ 文件已存在: skills/{module_name}.py。若确认覆盖，请将 overwrite 设为 true。"

    target_file.write_text(code, encoding="utf-8")
    notes = [
        f"✅ 已生成: skills/{module_name}.py",
        f"tool: {tool_name}",
        f"body_source: {source}",
    ]

    if _as_bool(auto_register_import, True):
        ok, msg = _ensure_import_in_skills_init(module_name)
        notes.append(f"skills/__init__.py: {msg}" if ok else msg)
    else:
        notes.append("skills/__init__.py: skipped")

    if _as_bool(mark_risky, False):
        ok, msg = _ensure_risky_tool(tool_name)
        notes.append(f"core/config.py: {msg}" if ok else msg)
    else:
        notes.append("core/config.py: risky skip")

    notes.append("💡 若新增了 import，请重启进程以重新加载技能注册。")
    return "\n".join(notes)
