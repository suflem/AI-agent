# skills/web_tools.py
# 网络工具：网页抓取、URL 内容提取、网络搜索接口

import os
import re
import json
import html as html_lib
import socket
import ipaddress
import urllib.parse
from pathlib import Path
from .registry import register


# ==========================================
# 1. 抓取网页内容
# ==========================================
fetch_url_schema = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": (
            "抓取指定 URL 的网页内容并提取纯文本。适合阅读文章、文档、API 文档等。"
            "自动去除 HTML 标签，提取主要文本内容。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要抓取的网页 URL"},
                "max_length": {"type": "integer", "description": "返回内容最大字符数，默认 8000"}
            },
            "required": ["url"]
        }
    }
}


def _html_to_text(html: str) -> str:
    """简易 HTML 转纯文本"""
    # 移除 script 和 style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    html = re.sub(r'<[^>]+>', ' ', html)
    # 处理 HTML 实体
    html = html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    html = html.replace('&quot;', '"').replace('&#39;', "'")
    # 合并空白
    html = re.sub(r'\s+', ' ', html).strip()
    # 按段落分行
    html = re.sub(r' {2,}', '\n', html)
    return html


def _validate_outbound_url(url: str):
    """Basic SSRF guard: allow only public http(s) URLs."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "❌ URL 解析失败"

    if parsed.scheme not in ("http", "https"):
        return "❌ 仅支持 http/https URL"

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return "❌ URL 缺少主机名"

    blocked_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if hostname in blocked_hosts:
        return "❌ 出站请求被安全策略拦截：禁止访问本机地址"

    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except Exception:
        return "❌ 无法解析目标主机名"

    for item in resolved:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return f"❌ 出站请求被安全策略拦截：禁止访问内网/保留地址 ({ip})"

    return None


@register(fetch_url_schema)
def fetch_url(url: str, max_length: int = 8000):
    """抓取网页内容"""
    try:
        import urllib.request
        import urllib.error

        url_err = _validate_outbound_url(url)
        if url_err:
            return url_err

        max_length = min(int(max_length) if max_length else 8000, 30000)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get('Content-Type', '')
            charset = 'utf-8'
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].strip()

            raw = response.read()
            try:
                html = raw.decode(charset)
            except (UnicodeDecodeError, LookupError):
                html = raw.decode('utf-8', errors='ignore')

        # 提取标题
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "(无标题)"

        text = _html_to_text(html)

        if len(text) > max_length:
            text = text[:max_length] + f"\n\n... (内容已截断，共 {len(text)} 字符)"

        return f"🌐 [{title}]\n📎 {url}\n\n{text}"

    except urllib.error.HTTPError as e:
        return f"❌ HTTP 错误 {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"❌ 网络错误: {e.reason}"
    except Exception as e:
        return f"❌ 抓取失败: {e}"


# ==========================================
# 2. 网络搜索 (多引擎接口)
# ==========================================
web_search_schema = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "通过搜索引擎搜索信息。支持多个搜索 API: serper (Google), bing, duckduckgo。"
            "需要在 .env 中配置对应的 API Key (SERPER_API_KEY / BING_API_KEY)。"
            "如果没有配置任何搜索 API，将使用 DuckDuckGo 的免费 HTML 搜索。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "engine": {"type": "string", "description": "搜索引擎 (serper/bing/duckduckgo)，默认自动选择"},
                "num_results": {"type": "integer", "description": "返回结果数，默认 5"}
            },
            "required": ["query"]
        }
    }
}


def _get_env_value(key: str) -> str:
    value = (os.getenv(key) or "").strip()
    if value:
        return value

    env_candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for env_path in env_candidates:
        if not env_path.exists():
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    text = line.strip()
                    if not text or text.startswith("#") or "=" not in text:
                        continue
                    k, v = text.split("=", 1)
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def _search_key_status() -> dict[str, bool]:
    return {
        "SERPER_API_KEY": bool(_get_env_value("SERPER_API_KEY")),
        "BING_API_KEY": bool(_get_env_value("BING_API_KEY")),
    }


def _short_error(err: Exception) -> str:
    raw = str(err).replace("\n", " ").strip() or err.__class__.__name__
    if len(raw) > 180:
        return raw[:177] + "..."
    return raw


def _search_serper(query: str, num: int):
    """使用 Serper API (Google Search)"""
    import urllib.request
    api_key = _get_env_value("SERPER_API_KEY")
    if not api_key:
        return None

    data = json.dumps({"q": query, "num": num}).encode()
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=data,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode())

    items = []
    for r in result.get("organic", [])[:num]:
        items.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "snippet": r.get("snippet", "")
        })
    return items


def _search_bing(query: str, num: int):
    """使用 Bing Search API"""
    import urllib.request
    api_key = _get_env_value("BING_API_KEY")
    if not api_key:
        return None

    url = f"https://api.bing.microsoft.com/v7.0/search?q={urllib.parse.quote(query)}&count={num}"
    req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode())

    items = []
    for r in result.get("webPages", {}).get("value", [])[:num]:
        items.append({
            "title": r.get("name", ""),
            "url": r.get("url", ""),
            "snippet": r.get("snippet", "")
        })
    return items


def _search_duckduckgo(query: str, num: int):
    """使用 DuckDuckGo HTML 搜索 (免费，无需 Key)"""
    import urllib.request
    import urllib.parse

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')

    items = []
    # 简易解析 DuckDuckGo HTML 结果
    title_hits = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    snippet_hits = re.findall(
        r'<(?:a|div|span)[^>]*class="result__snippet"[^>]*>(.*?)</(?:a|div|span)>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    for idx, (href, title) in enumerate(title_hits[:num]):
        parsed_href = href.strip()
        if parsed_href.startswith("/l/?"):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(parsed_href).query)
            parsed_href = params.get("uddg", [parsed_href])[0]
        parsed_href = html_lib.unescape(parsed_href)
        title = html_lib.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        snippet_raw = snippet_hits[idx] if idx < len(snippet_hits) else ""
        snippet = html_lib.unescape(re.sub(r"<[^>]+>", "", snippet_raw)).strip()
        items.append({"title": title, "url": parsed_href, "snippet": snippet})

    return items


@register(web_search_schema)
def web_search(query: str, engine: str = "", num_results: int = 5):
    """网络搜索"""
    try:
        num_results = min(int(num_results) if num_results else 5, 15)

        items = None
        used_engine = ""
        attempt_errors: list[str] = []
        missing_key_engines: list[str] = []

        engine_map = {
            "serper": (_search_serper, "Serper (Google)"),
            "bing": (_search_bing, "Bing"),
            "duckduckgo": (_search_duckduckgo, "DuckDuckGo"),
        }

        engine = engine.lower().strip()
        if engine and engine not in engine_map:
            return "❌ 搜索失败: engine 仅支持 serper / bing / duckduckgo"

        ordered_engines = [engine_map[engine]] if engine else [
            engine_map["serper"],
            engine_map["bing"],
            engine_map["duckduckgo"],
        ]

        for try_engine, try_name in ordered_engines:
            try:
                result = try_engine(query, num_results)
            except Exception as e:
                attempt_errors.append(f"{try_name}: {_short_error(e)}")
                continue
            if result is None:
                missing_key_engines.append(try_name)
                continue
            items = result
            used_engine = try_name
            break

        if items is None:
            key_status = _search_key_status()
            has_search_key = key_status["SERPER_API_KEY"] or key_status["BING_API_KEY"]
            lines = []
            if has_search_key:
                lines.append("❌ 搜索失败: 已检测到搜索 Key，但请求未成功。")
                lines.append("请检查 API Key 是否有效，以及网络是否可访问搜索服务。")
            else:
                lines.append("❌ 搜索失败: 当前未检测到搜索 API Key。")
                lines.append("请在项目根目录 `.env` 里配置至少一个：")
                lines.append("  SERPER_API_KEY=你的_serper_key")
                lines.append("  BING_API_KEY=你的_bing_key")
                lines.append("保存后重启进程（`python run.py` 或 `python run_api.py`）。")
            if missing_key_engines:
                lines.append("未配置引擎: " + ", ".join(missing_key_engines))
            if attempt_errors:
                lines.append("最近错误: " + " | ".join(attempt_errors[:2]))
            return "\n".join(lines)

        if not items:
            return f"🔍 搜索 '{query}' 无结果 ({used_engine})"

        lines = [f"🔍 搜索: '{query}' ({used_engine}, {len(items)} 条结果)\n"]
        for i, item in enumerate(items):
            lines.append(f"  {i+1}. **{item['title']}**")
            lines.append(f"     🔗 {item['url']}")
            if item['snippet']:
                lines.append(f"     {item['snippet']}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 搜索失败: {e}"
