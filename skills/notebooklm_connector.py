# skills/notebooklm_connector.py
# NotebookLM 兼容层：先用本地 KB + 外部模型实现 sync/ask/digest 接口

import os
import re
import json
import time
import hashlib
import urllib.parse

from .registry import register
from .path_safety import guard_path

NOTEBOOKLM_STATE_REL = "data/notebooklm/notebooks.json"
NOTEBOOKLM_CACHE_REL = "data/notebooklm/cache"
NOTEBOOKLM_API_KEY_ENV = "NOTEBOOKLM_API_KEY"
NOTEBOOKLM_BASE_URL_ENV = "NOTEBOOKLM_BASE_URL"


notebooklm_connector_schema = {
    "type": "function",
    "function": {
        "name": "notebooklm_connector",
        "description": (
            "NotebookLM 兼容接口。支持 sync_sources / ask / digest / status。"
            "当前使用本地知识库 + 外部模型作为替代实现，并预留官方 API 变量位置。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: sync_sources(同步源), ask(提问), digest(摘要), status(状态)",
                },
                "notebook_id": {
                    "type": "string",
                    "description": "笔记本 ID（字母/数字/_/-，默认 default）",
                },
                "notebook_name": {
                    "type": "string",
                    "description": "笔记本名称（sync_sources 时可选）",
                },
                "local_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本地文件/目录路径列表（sync_sources）",
                },
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "网页来源 URL 列表（sync_sources）",
                },
                "question": {
                    "type": "string",
                    "description": "提问内容（ask）",
                },
                "digest_type": {
                    "type": "string",
                    "description": "摘要类型: briefing/highlights/analysis（digest）",
                },
                "provider": {
                    "type": "string",
                    "description": "外部模型提供商（默认 kimi）",
                },
                "top_k": {
                    "type": "integer",
                    "description": "检索片段条数（默认 6）",
                },
            },
            "required": ["action"],
        },
    },
}


def _normalize_notebook_id(notebook_id: str):
    value = (notebook_id or "default").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", value):
        return None, "❌ notebook_id 只允许小写字母、数字、下划线和短横线，长度 1-64"
    return value, None


def _validate_source_url(url: str):
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "❌ URL 解析失败"

    if parsed.scheme not in ("http", "https"):
        return "❌ 仅支持 http/https URL"

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "❌ URL 缺少主机名"

    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return "❌ 安全拦截：不允许使用本机地址作为来源"

    return None


def _load_state():
    state_obj, err = guard_path(NOTEBOOKLM_STATE_REL, must_exist=False, for_write=True)
    if err:
        raise RuntimeError(err)

    if not state_obj.parent.exists():
        state_obj.parent.mkdir(parents=True, exist_ok=True)

    if state_obj.exists():
        with open(state_obj, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {"notebooks": {}}


def _save_state(state):
    state_obj, err = guard_path(NOTEBOOKLM_STATE_REL, must_exist=False, for_write=True)
    if err:
        raise RuntimeError(err)

    if not state_obj.parent.exists():
        state_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(state_obj, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _cache_file_for_url(notebook_id: str, url: str):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    rel = f"{NOTEBOOKLM_CACHE_REL}/{notebook_id}/{digest}.txt"
    cache_obj, err = guard_path(rel, must_exist=False, for_write=True)
    if err:
        raise RuntimeError(err)

    if not cache_obj.parent.exists():
        cache_obj.parent.mkdir(parents=True, exist_ok=True)

    return cache_obj


def _merge_sources(existing, incoming):
    source_map = {}

    for item in existing:
        key = item.get("source_url") or item.get("path")
        if key:
            source_map[key] = item

    for item in incoming:
        key = item.get("source_url") or item.get("path")
        if key:
            source_map[key] = item

    return sorted(source_map.values(), key=lambda x: (x.get("type", ""), x.get("path", ""), x.get("source_url", "")))


@register(notebooklm_connector_schema)
def notebooklm_connector(
    action: str,
    notebook_id: str = "default",
    notebook_name: str = "",
    local_paths: list = None,
    urls: list = None,
    question: str = "",
    digest_type: str = "briefing",
    provider: str = "kimi",
    top_k: int = 6,
):
    try:
        action = (action or "").strip().lower()
        notebook_id, notebook_id_err = _normalize_notebook_id(notebook_id)
        if notebook_id_err:
            return notebook_id_err

        local_paths = local_paths or []
        urls = urls or []
        if not isinstance(local_paths, list):
            return "❌ local_paths 必须是数组"
        if not isinstance(urls, list):
            return "❌ urls 必须是数组"

        state = _load_state()
        notebooks = state.setdefault("notebooks", {})

        if action == "status":
            if not notebooks:
                return (
                    "📓 NotebookLM 兼容层状态：暂无笔记本。\n"
                    f"API Key 变量: {NOTEBOOKLM_API_KEY_ENV}\n"
                    f"Base URL 变量: {NOTEBOOKLM_BASE_URL_ENV}"
                )

            lines = ["📓 NotebookLM 兼容层状态:\n"]
            for nid in sorted(notebooks.keys()):
                nb = notebooks[nid]
                lines.append(f"  - {nid} ({nb.get('name', nid)})")
                lines.append(f"    来源数: {len(nb.get('sources', []))}")
                lines.append(f"    更新时间: {nb.get('updated_at', '-')}")

            lines.append("")
            lines.append(f"💡 预留官方 API 变量: {NOTEBOOKLM_API_KEY_ENV}, {NOTEBOOKLM_BASE_URL_ENV}")
            return "\n".join(lines)

        if action == "sync_sources":
            notebook = notebooks.setdefault(notebook_id, {})
            notebook["name"] = (notebook_name or notebook.get("name") or notebook_id).strip()
            notebook.setdefault("sources", [])

            incoming_sources = []
            errors = []

            for p in local_paths:
                p_obj, err = guard_path(str(p), must_exist=True, for_write=False)
                if err:
                    errors.append(f"本地路径 {p}: {err}")
                    continue

                incoming_sources.append({
                    "type": "local",
                    "path": str(p_obj),
                    "added_at": time.strftime("%Y-%m-%d %H:%M"),
                })

            if urls:
                from .web_tools import fetch_url

            for url in urls:
                url = str(url).strip()
                url_err = _validate_source_url(url)
                if url_err:
                    errors.append(f"URL {url}: {url_err}")
                    continue

                fetched = fetch_url(url=url, max_length=18000)
                if not isinstance(fetched, str) or fetched.startswith("❌"):
                    errors.append(f"URL {url}: 拉取失败 -> {fetched}")
                    continue

                try:
                    cache_file = _cache_file_for_url(notebook_id, url)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(fetched)

                    incoming_sources.append({
                        "type": "url_cache",
                        "path": str(cache_file),
                        "source_url": url,
                        "added_at": time.strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception as e:
                    errors.append(f"URL {url}: 缓存失败 -> {e}")

            if not incoming_sources and not notebook.get("sources"):
                return "❌ 没有可同步的有效来源"

            notebook["sources"] = _merge_sources(notebook.get("sources", []), incoming_sources)
            notebook["updated_at"] = time.strftime("%Y-%m-%d %H:%M")

            kb_name = f"notebooklm_{notebook_id}"
            kb_results = []
            kb_errors = []

            from .knowledge_tools import kb_build

            for source in notebook.get("sources", []):
                source_path = source.get("path", "")
                if not source_path:
                    continue
                result = kb_build(kb_name=kb_name, source_path=source_path, chunk_size=700)
                if isinstance(result, str) and result.startswith("✅"):
                    kb_results.append(source_path)
                else:
                    kb_errors.append(f"{source_path}: {result}")

            _save_state(state)

            lines = [
                f"✅ Notebook '{notebook_id}' 已同步。",
                f"  名称: {notebook.get('name', notebook_id)}",
                f"  来源总数: {len(notebook.get('sources', []))}",
                f"  本次新增来源: {len(incoming_sources)}",
                f"  KB 同步成功: {len(kb_results)}",
            ]
            if errors:
                lines.append(f"  ⚠️ 来源异常: {len(errors)}")
                lines.extend([f"    - {e}" for e in errors[:8]])
            if kb_errors:
                lines.append(f"  ⚠️ KB 同步异常: {len(kb_errors)}")
                lines.extend([f"    - {e}" for e in kb_errors[:8]])

            lines.append(f"  兼容 KB 名称: {kb_name}")
            lines.append(f"  预留官方 API 变量: {NOTEBOOKLM_API_KEY_ENV}, {NOTEBOOKLM_BASE_URL_ENV}")
            return "\n".join(lines)

        if action == "ask":
            if not question.strip():
                return "❌ question 不能为空"

            notebook = notebooks.get(notebook_id)
            if not notebook:
                return f"❌ notebook 不存在: {notebook_id}。请先 sync_sources"

            top_k = max(1, min(int(top_k) if top_k else 6, 12))
            kb_name = f"notebooklm_{notebook_id}"

            from .knowledge_tools import kb_query

            context = kb_query(kb_name=kb_name, query=question, top_k=top_k)
            if isinstance(context, str) and context.startswith("❌"):
                return f"⚠️ 检索失败，请先同步来源。\n{context}"

            from .external_ai import call_ai

            answer = call_ai(
                prompt=(
                    f"Notebook 名称: {notebook.get('name', notebook_id)}\n"
                    f"用户问题: {question}\n\n"
                    f"以下是检索到的相关片段:\n{context}\n\n"
                    "请基于片段回答：先给结论，再给证据点；若证据不足要明确说明。"
                ),
                provider=provider,
                system_prompt="你是 NotebookLM 风格助手，回答需可追溯到给定片段。",
                temperature=0.3,
                max_tokens=4096,
            )
            return f"📓 Notebook Ask ({notebook_id})\n{answer}"

        if action == "digest":
            notebook = notebooks.get(notebook_id)
            if not notebook:
                return f"❌ notebook 不存在: {notebook_id}。请先 sync_sources"

            top_k = max(1, min(int(top_k) if top_k else 6, 12))
            kb_name = f"notebooklm_{notebook_id}"

            from .knowledge_tools import kb_query

            query = "请提取关键主题、核心事实、风险点与后续行动"
            context = kb_query(kb_name=kb_name, query=query, top_k=top_k)
            if isinstance(context, str) and context.startswith("❌"):
                return f"⚠️ 检索失败，请先同步来源。\n{context}"

            prompts = {
                "briefing": "生成简洁摘要（3-5 条）。",
                "highlights": "提取最重要的 5 个亮点并说明原因。",
                "analysis": "做结构化分析：主题、证据、风险、建议行动。",
            }
            digest_instruction = prompts.get((digest_type or "briefing").lower(), prompts["briefing"])

            from .external_ai import call_ai

            digest = call_ai(
                prompt=(
                    f"Notebook 名称: {notebook.get('name', notebook_id)}\n"
                    f"任务: {digest_instruction}\n\n"
                    f"检索片段:\n{context}"
                ),
                provider=provider,
                system_prompt="你是 NotebookLM 风格摘要助手，必须基于给定片段输出。",
                temperature=0.4,
                max_tokens=4096,
            )
            return f"📓 Notebook Digest ({notebook_id})\n{digest}"

        return "❌ 未知 action。支持: sync_sources, ask, digest, status"

    except Exception as e:
        return f"❌ notebooklm_connector 执行失败: {e}"
