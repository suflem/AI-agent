# skills/social_tools.py
# 社交信息流处理模块 (OpenClaw-like)
# 支持 RSS 订阅、内容聚合、信息流摘要、社交平台 API 接口

import os
import json
import re
import time
import socket
import ipaddress
import urllib.parse
from datetime import datetime
from email.utils import parsedate_to_datetime
from .registry import register
from .path_safety import guard_path

SOCIAL_DATA_DIR = "data/social"


def _ensure_social_dir():
    dir_obj, err = guard_path(SOCIAL_DATA_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not dir_obj.exists():
        dir_obj.mkdir(parents=True, exist_ok=True)
    return dir_obj


def _guarded_social_file(filename):
    dir_obj = _ensure_social_dir()
    file_obj, err = guard_path(str(dir_obj / filename), must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    return file_obj


def _load_connector_meta():
    meta_obj = _guarded_social_file("social_config.json")
    if meta_obj.exists():
        with open(meta_obj, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 兼容旧格式：移除任何明文 api_key 字段
        changed = False
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, dict) and "api_key" in value:
                    value.pop("api_key", None)
                    changed = True
                elif not isinstance(value, dict):
                    data[key] = {"configured_at": "", "api_key_env": ""}
                    changed = True

            if changed:
                _save_connector_meta(data)
            return data

        return {}
    return {}


def _save_connector_meta(meta):
    meta_obj = _guarded_social_file("social_config.json")
    with open(meta_obj, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _get_platform_api_key(platform: str, runtime_key: str = ""):
    info = SOCIAL_PLATFORMS.get(platform)
    if not info:
        return ""
    if runtime_key:
        return runtime_key.strip()
    return os.getenv(info["api_key_env"], "").strip()


def _validate_public_http_url(url: str):
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "❌ URL 解析失败"

    if parsed.scheme not in ("http", "https"):
        return "❌ 仅支持 http/https 的 RSS URL"

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "❌ URL 缺少主机名"

    blocked_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if host in blocked_hosts:
        return "❌ 安全拦截：禁止访问本机地址"

    try:
        resolved = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except Exception:
        return "❌ 无法解析目标主机"

    for item in resolved:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"❌ 安全拦截：禁止访问内网/保留地址 ({ip})"

    return None


# ==========================================
# 1. RSS 订阅管理与内容抓取
# ==========================================
rss_manage_schema = {
    "type": "function",
    "function": {
        "name": "rss_manage",
        "description": (
            "管理 RSS/Atom 订阅源。支持添加、删除、列出订阅源，以及抓取最新内容。"
            "适合跟踪博客、新闻、技术社区更新等。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: add(添加订阅), remove(删除), list(列出), fetch(抓取内容), fetch_all(抓取全部)"
                },
                "url": {"type": "string", "description": "RSS 源 URL (add/fetch 时使用)"},
                "name": {"type": "string", "description": "订阅源名称 (add 时使用)"},
                "category": {"type": "string", "description": "分类标签 (如 'tech', 'news')"},
                "max_items": {"type": "integer", "description": "最大返回条目数，默认 10"}
            },
            "required": ["action"]
        }
    }
}


def _load_feeds():
    feeds_obj = _guarded_social_file("rss_feeds.json")
    if feeds_obj.exists():
        with open(feeds_obj, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_feeds(feeds):
    feeds_obj = _guarded_social_file("rss_feeds.json")
    with open(feeds_obj, 'w', encoding='utf-8') as f:
        json.dump(feeds, f, ensure_ascii=False, indent=2)


def _parse_rss(xml_text: str, max_items: int = 10):
    """简易 RSS/Atom 解析器（无依赖）"""
    items = []

    # 尝试 RSS 2.0 格式
    item_blocks = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if not item_blocks:
        # 尝试 Atom 格式
        item_blocks = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

    for block in item_blocks[:max_items]:
        title = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
        link = re.search(r'<link[^>]*(?:href=["\']([^"\']+)["\'])?[^>]*>(.*?)</link>', block, re.DOTALL)
        desc = re.search(r'<description[^>]*>(.*?)</description>', block, re.DOTALL)
        if not desc:
            desc = re.search(r'<summary[^>]*>(.*?)</summary>', block, re.DOTALL)
        pub_date = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', block, re.DOTALL)
        if not pub_date:
            pub_date = re.search(r'<updated[^>]*>(.*?)</updated>', block, re.DOTALL)

        item = {
            "title": _clean_html(title.group(1)) if title else "(无标题)",
            "link": "",
            "description": "",
            "date": pub_date.group(1).strip() if pub_date else ""
        }

        if link:
            item["link"] = link.group(1) or _clean_html(link.group(2))

        if desc:
            d = _clean_html(desc.group(1))
            item["description"] = d[:200] + "..." if len(d) > 200 else d

        items.append(item)

    return items


def _clean_html(text: str) -> str:
    """清理 HTML 标签和 CDATA"""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    return text.strip()


def _fetch_rss(url: str, max_items: int = 10):
    """抓取并解析 RSS"""
    import urllib.request
    url_err = _validate_public_http_url(url)
    if url_err:
        raise ValueError(url_err)

    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; AIAssistant/1.0)'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_text = resp.read().decode('utf-8', errors='ignore')
    return _parse_rss(xml_text, max_items)


@register(rss_manage_schema)
def rss_manage(action: str, url: str = "", name: str = "",
               category: str = "", max_items: int = 10):
    """RSS 订阅管理"""
    try:
        feeds = _load_feeds()
        max_items = min(int(max_items) if max_items else 10, 30)

        if action == "add":
            if not url:
                return "❌ 请提供 RSS 源 URL"
            url_err = _validate_public_http_url(url)
            if url_err:
                return url_err
            # 检查是否重复
            for f in feeds:
                if f["url"] == url:
                    return f"⚠️ 已存在相同订阅: {f['name']}"
            feed_name = name or url
            feeds.append({
                "url": url,
                "name": feed_name,
                "category": category,
                "added": time.strftime("%Y-%m-%d %H:%M")
            })
            _save_feeds(feeds)
            return f"✅ 已添加 RSS 订阅: {feed_name}"

        elif action == "remove":
            if not url and not name:
                return "❌ 请提供 URL 或名称"
            before = len(feeds)
            feeds = [f for f in feeds if f["url"] != url and f["name"] != name]
            if len(feeds) == before:
                return "❌ 未找到匹配的订阅"
            _save_feeds(feeds)
            return "✅ 已删除订阅"

        elif action == "list":
            if not feeds:
                return "📡 暂无 RSS 订阅"
            lines = ["📡 RSS 订阅列表:\n"]
            for i, f in enumerate(feeds):
                cat = f" [{f['category']}]" if f.get('category') else ""
                lines.append(f"  {i+1}. {f['name']}{cat}")
                lines.append(f"     🔗 {f['url']}")
            return "\n".join(lines)

        elif action == "fetch":
            if not url:
                return "❌ 请提供 RSS 源 URL"
            url_err = _validate_public_http_url(url)
            if url_err:
                return url_err
            items = _fetch_rss(url, max_items)
            if not items:
                return f"⚠️ 未获取到内容: {url}"
            lines = [f"📰 RSS 内容 ({len(items)} 条):\n"]
            for i, item in enumerate(items):
                lines.append(f"  {i+1}. **{item['title']}**")
                if item['date']:
                    lines.append(f"     📅 {item['date']}")
                if item['link']:
                    lines.append(f"     🔗 {item['link']}")
                if item['description']:
                    lines.append(f"     {item['description']}")
                lines.append("")
            return "\n".join(lines)

        elif action == "fetch_all":
            if not feeds:
                return "📡 暂无订阅源"
            all_items = []
            errors = []
            for f in feeds:
                try:
                    items = _fetch_rss(f["url"], max_items=5)
                    for item in items:
                        item["source"] = f["name"]
                        item["category"] = f.get("category", "")
                    all_items.extend(items)
                except Exception as e:
                    errors.append(f"{f['name']}: {e}")

            if not all_items:
                err_msg = ("\n失败: " + "; ".join(errors)) if errors else ""
                return f"⚠️ 未获取到任何内容{err_msg}"

            lines = [f"📰 信息流汇总 ({len(all_items)} 条，来自 {len(feeds)} 个源):\n"]
            for i, item in enumerate(all_items[:max_items]):
                cat = f" [{item['category']}]" if item.get('category') else ""
                lines.append(f"  {i+1}. [{item['source']}]{cat} **{item['title']}**")
                if item['link']:
                    lines.append(f"     🔗 {item['link']}")
                if item['description']:
                    lines.append(f"     {item['description']}")
                lines.append("")

            if errors:
                lines.append(f"⚠️ {len(errors)} 个源抓取失败")
            return "\n".join(lines)

        else:
            return f"❌ 未知操作: {action}。支持: add, remove, list, fetch, fetch_all"

    except Exception as e:
        return f"❌ RSS 管理失败: {e}"


# ==========================================
# 2. 信息流 AI 摘要
# ==========================================
feed_digest_schema = {
    "type": "function",
    "function": {
        "name": "feed_digest",
        "description": (
            "对信息流内容进行 AI 智能摘要。先抓取所有 RSS 订阅的最新内容，"
            "然后用 AI 生成每日信息简报/摘要。类似 OpenClaw 的信息流处理。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "只处理指定分类，留空处理全部"},
                "digest_type": {
                    "type": "string",
                    "description": "摘要类型: 'briefing'(每日简报), 'highlights'(精选), 'analysis'(深度分析)"
                },
                "max_items": {"type": "integer", "description": "纳入摘要的最大条目数，默认 20"}
            },
            "required": []
        }
    }
}


@register(feed_digest_schema)
def feed_digest(category: str = "", digest_type: str = "briefing", max_items: int = 20):
    """信息流 AI 摘要"""
    try:
        feeds = _load_feeds()
        if not feeds:
            return "📡 暂无订阅源，请先使用 rss_manage 添加订阅。"

        max_items = min(int(max_items) if max_items else 20, 50)

        # 筛选分类
        if category:
            feeds = [f for f in feeds if f.get("category", "").lower() == category.lower()]
            if not feeds:
                return f"⚠️ 没有 '{category}' 分类的订阅源"

        # 抓取内容
        all_items = []
        for f in feeds:
            try:
                items = _fetch_rss(f["url"], max_items=8)
                for item in items:
                    item["source"] = f["name"]
                all_items.extend(items)
            except Exception:
                continue

        if not all_items:
            return "⚠️ 未获取到任何内容"

        # 构建内容文本
        content_lines = []
        for i, item in enumerate(all_items[:max_items]):
            content_lines.append(f"{i+1}. [{item['source']}] {item['title']}")
            if item.get('description'):
                content_lines.append(f"   {item['description']}")
        content_text = "\n".join(content_lines)

        type_prompts = {
            "briefing": "生成一份简洁的每日信息简报，按话题归类，每个话题 2-3 句话概括。",
            "highlights": "挑选最有价值的 5 条信息，详细介绍每条的内容和重要性。",
            "analysis": "对信息流中的主要趋势和热点进行深度分析，给出观察和见解。"
        }
        prompt = type_prompts.get(digest_type, type_prompts["briefing"])

        from .external_ai import call_ai
        result = call_ai(
            prompt=f"以下是今日信息流内容 ({len(all_items)} 条)，请{prompt}\n\n---\n{content_text}",
            provider="kimi",
            system_prompt="你是信息分析师。根据 RSS 信息流生成摘要，保持客观准确，不编造信息。",
            temperature=0.5,
            max_tokens=4096
        )

        date_str = time.strftime("%Y-%m-%d")
        cat_str = f" [{category}]" if category else ""
        return f"📰 {date_str} 信息流摘要{cat_str}:\n{result}"

    except Exception as e:
        return f"❌ 信息流摘要生成失败: {e}"


# ==========================================
# 3. 社交平台连接器 (接口预留)
# ==========================================
social_connector_schema = {
    "type": "function",
    "function": {
        "name": "social_connector",
        "description": (
            "社交平台 API 连接器 (接口预留)。"
            "支持配置和管理社交平台 API 连接：微博、Twitter/X、微信公众号、Telegram 等。"
            "当前为接口框架，需要配置对应平台的 API Key 后使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: config(配置平台), list(列出已配置平台), test(测试连接), fetch(获取内容)"
                },
                "platform": {
                    "type": "string",
                    "description": "平台名: weibo, twitter, wechat_mp, telegram, github, reddit"
                },
                "api_key": {"type": "string", "description": "平台 API Key (config 时使用)"},
                "query": {"type": "string", "description": "查询参数 (fetch 时使用)"}
            },
            "required": ["action"]
        }
    }
}

# 支持的社交平台配置模板
SOCIAL_PLATFORMS = {
    "weibo": {
        "name": "微博",
        "api_key_env": "WEIBO_API_KEY",
        "base_url": "https://api.weibo.com/2",
        "endpoints": {"timeline": "/statuses/home_timeline.json", "search": "/search/topics.json"}
    },
    "twitter": {
        "name": "Twitter/X",
        "api_key_env": "TWITTER_BEARER_TOKEN",
        "base_url": "https://api.twitter.com/2",
        "endpoints": {"timeline": "/tweets/search/recent", "user": "/users/by/username"}
    },
    "wechat_mp": {
        "name": "微信公众号",
        "api_key_env": "WECHAT_MP_TOKEN",
        "base_url": "https://api.weixin.qq.com/cgi-bin",
        "endpoints": {"articles": "/material/batchget_material"}
    },
    "telegram": {
        "name": "Telegram",
        "api_key_env": "TELEGRAM_BOT_TOKEN",
        "base_url": "https://api.telegram.org",
        "endpoints": {"updates": "/getUpdates", "send": "/sendMessage"}
    },
    "github": {
        "name": "GitHub",
        "api_key_env": "GITHUB_TOKEN",
        "base_url": "https://api.github.com",
        "endpoints": {"trending": "/search/repositories", "notifications": "/notifications"}
    },
    "reddit": {
        "name": "Reddit",
        "api_key_env": "REDDIT_CLIENT_SECRET",
        "base_url": "https://oauth.reddit.com",
        "endpoints": {"hot": "/hot.json", "search": "/search.json"}
    }
}


@register(social_connector_schema)
def social_connector(action: str, platform: str = "", api_key: str = "", query: str = ""):
    """社交平台连接器"""
    try:
        _ensure_social_dir()
        meta = _load_connector_meta()

        if action == "list":
            lines = ["🌐 社交平台连接器状态:\n"]
            for key, info in SOCIAL_PLATFORMS.items():
                env_key = os.getenv(info["api_key_env"], "").strip()
                configured = bool(env_key)
                has_meta = key in meta
                status = "✅ 已配置" if configured else "⬜ 未配置"
                lines.append(f"  {status} {info['name']} ({key})")
                lines.append(f"       环境变量: {info['api_key_env']}")
                if has_meta and not configured:
                    lines.append("       ⚠️ 已记录配置但缺少环境变量")
            lines.append("\n💡 配置方法: 在 .env 中添加对应 API Key；工具不会把 Key 写入本地文件。")
            return "\n".join(lines)

        elif action == "config":
            if not platform:
                return "❌ 请提供 platform"
            if platform not in SOCIAL_PLATFORMS:
                return f"❌ 不支持的平台: {platform}。支持: {', '.join(SOCIAL_PLATFORMS.keys())}"

            info = SOCIAL_PLATFORMS[platform]
            runtime_note = ""
            if api_key:
                os.environ[info["api_key_env"]] = api_key
                runtime_note = "\n⚠️ 已写入当前进程环境变量（临时），重启后会失效。"

            meta[platform] = {
                "configured_at": time.strftime("%Y-%m-%d %H:%M"),
                "api_key_env": info["api_key_env"],
            }
            _save_connector_meta(meta)
            return (
                f"✅ 已记录 {info['name']} 平台配置（不保存明文 API Key）。"
                f"\n请在 .env 中设置: {info['api_key_env']}=..."
                f"{runtime_note}"
            )

        elif action == "test":
            if not platform:
                return "❌ 请提供 platform"
            if platform not in SOCIAL_PLATFORMS:
                return f"❌ 不支持的平台: {platform}"

            info = SOCIAL_PLATFORMS[platform]
            key = _get_platform_api_key(platform, api_key)
            if not key:
                return f"❌ {info['name']} 未配置 API Key"
            return f"✅ {info['name']} API Key 已配置 (长度: {len(key)})\n⚠️ 具体连通性测试需要网络请求，请使用 fetch 操作验证。"

        elif action == "fetch":
            if not platform:
                return "❌ 请提供 platform"
            if platform not in SOCIAL_PLATFORMS:
                return f"❌ 不支持的平台: {platform}"

            info = SOCIAL_PLATFORMS[platform]
            key = _get_platform_api_key(platform, api_key)
            if not key:
                return f"❌ {info['name']} 未配置 API Key。请先配置。"

            # GitHub 特殊处理 (最常用)
            if platform == "github":
                return _fetch_github(key, query)

            return (
                f"⚠️ {info['name']} 内容获取接口开发中。\n"
                f"  API 端点: {info['base_url']}\n"
                f"  可用端点: {json.dumps(info['endpoints'], ensure_ascii=False)}\n"
                f"  💡 可通过 fetch_url 直接访问 API 端点获取数据。"
            )

        else:
            return f"❌ 未知操作: {action}。支持: config, list, test, fetch"

    except Exception as e:
        return f"❌ 社交连接器失败: {e}"


# ==========================================
# 4. 统一信息流处理管道
# fetch -> dedupe -> sort -> summarize -> taskify
# ==========================================
infoflow_pipeline_schema = {
    "type": "function",
    "function": {
        "name": "infoflow_pipeline",
        "description": (
            "统一处理信息流：抓取 RSS、去重、排序、AI 摘要，并可选生成待办任务。"
            "适合每日信息摄取和行动化。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "分类过滤，留空表示全部"},
                "max_items": {"type": "integer", "description": "处理后的最大条数，默认 20"},
                "per_feed_limit": {"type": "integer", "description": "每个订阅源抓取条数，默认 8"},
                "digest_type": {
                    "type": "string",
                    "description": "摘要类型: briefing/highlights/analysis，默认 briefing"
                },
                "taskify": {"type": "boolean", "description": "是否生成任务建议，默认 true"},
                "create_todos": {"type": "boolean", "description": "是否写入待办列表，默认 false"},
                "task_limit": {"type": "integer", "description": "最多生成任务数，默认 5"}
            },
            "required": []
        }
    }
}


def _item_time_score(item):
    date_text = (item.get("date") or "").strip()
    if not date_text:
        return 0.0

    try:
        return parsedate_to_datetime(date_text).timestamp()
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_text, fmt).timestamp()
        except Exception:
            continue

    return 0.0


def _item_dedupe_key(item):
    link = (item.get("link") or "").strip().lower()
    if link:
        return f"link:{link}"
    title = re.sub(r"\s+", " ", (item.get("title") or "").strip().lower())
    source = (item.get("source") or "").strip().lower()
    return f"title:{source}:{title}"


def _heuristic_tasks(items, limit: int):
    tasks = []
    seen = set()
    for item in items:
        title = (item.get("title") or "").strip()
        source = (item.get("source") or "").strip()
        if not title:
            continue

        task = f"阅读并跟进: {title}"
        if source:
            task += f" [{source}]"

        if task in seen:
            continue
        seen.add(task)
        tasks.append(task)
        if len(tasks) >= limit:
            break
    return tasks


@register(infoflow_pipeline_schema)
def infoflow_pipeline(
    category: str = "",
    max_items: int = 20,
    per_feed_limit: int = 8,
    digest_type: str = "briefing",
    taskify: bool = True,
    create_todos: bool = False,
    task_limit: int = 5,
):
    try:
        feeds = _load_feeds()
        if not feeds:
            return "📡 暂无订阅源，请先使用 rss_manage 添加订阅。"

        max_items = max(1, min(int(max_items) if max_items else 20, 50))
        per_feed_limit = max(1, min(int(per_feed_limit) if per_feed_limit else 8, 20))
        task_limit = max(1, min(int(task_limit) if task_limit else 5, 20))

        if category:
            feeds = [f for f in feeds if f.get("category", "").lower() == category.lower()]
            if not feeds:
                return f"⚠️ 没有 '{category}' 分类的订阅源"

        all_items = []
        fetch_errors = []
        for feed in feeds:
            try:
                items = _fetch_rss(feed["url"], max_items=per_feed_limit)
                for item in items:
                    item["source"] = feed["name"]
                    item["category"] = feed.get("category", "")
                all_items.extend(items)
            except Exception as e:
                fetch_errors.append(f"{feed['name']}: {e}")

        if not all_items:
            err_msg = "；".join(fetch_errors) if fetch_errors else "未知错误"
            return f"⚠️ 未获取到任何内容。{err_msg}"

        # dedupe: 对同一 key 仅保留较新的条目
        deduped = {}
        for item in all_items:
            key = _item_dedupe_key(item)
            if key not in deduped:
                deduped[key] = item
                continue
            if _item_time_score(item) >= _item_time_score(deduped[key]):
                deduped[key] = item

        sorted_items = sorted(deduped.values(), key=_item_time_score, reverse=True)
        selected = sorted_items[:max_items]

        content_lines = []
        for i, item in enumerate(selected):
            content_lines.append(f"{i+1}. [{item.get('source', '')}] {item.get('title', '')}")
            if item.get("description"):
                content_lines.append(f"   {item['description']}")
            if item.get("link"):
                content_lines.append(f"   链接: {item['link']}")
            if item.get("date"):
                content_lines.append(f"   时间: {item['date']}")
        content_text = "\n".join(content_lines)

        type_prompts = {
            "briefing": "生成一份简洁的每日信息简报，按话题归类，每个话题 2-3 句话概括。",
            "highlights": "挑选最有价值的 5 条信息，详细介绍每条的内容和重要性。",
            "analysis": "对信息流中的主要趋势和热点进行深度分析，给出观察和见解。",
        }
        digest_prompt = type_prompts.get((digest_type or "briefing").lower(), type_prompts["briefing"])

        from .external_ai import call_ai
        digest_result = call_ai(
            prompt=f"以下是今日信息流内容，请{digest_prompt}\n\n---\n{content_text}",
            provider="kimi",
            system_prompt="你是信息分析师。根据输入内容生成摘要，不要编造。",
            temperature=0.4,
            max_tokens=4096,
        )

        lines = [
            f"🧠 信息流处理完成：原始 {len(all_items)} 条 → 去重后 {len(deduped)} 条 → 输出 {len(selected)} 条。",
            "",
            "📰 摘要：",
            digest_result,
            "",
            "📌 头条预览：",
        ]

        for i, item in enumerate(selected[:min(len(selected), 10)]):
            lines.append(f"  {i+1}. [{item.get('source', '')}] {item.get('title', '')}")

        if fetch_errors:
            lines.append("")
            lines.append(f"⚠️ 抓取失败 {len(fetch_errors)} 个源：")
            lines.extend([f"  - {x}" for x in fetch_errors[:8]])

        if taskify:
            tasks = _heuristic_tasks(selected, task_limit)
            lines.append("")
            lines.append("✅ 任务建议：")
            for i, task in enumerate(tasks):
                lines.append(f"  {i+1}. {task}")

            if create_todos and tasks:
                from .daily_tools import todo_manage

                created = 0
                todo_errors = []
                for task in tasks:
                    resp = todo_manage(
                        action="add",
                        content=task,
                        priority="medium",
                        category=category or "信息流",
                    )
                    if isinstance(resp, str) and resp.startswith("✅"):
                        created += 1
                    else:
                        todo_errors.append(str(resp))

                lines.append(f"\n🗂️ 已写入待办: {created}/{len(tasks)}")
                if todo_errors:
                    lines.append("⚠️ 待办写入异常：")
                    lines.extend([f"  - {e}" for e in todo_errors[:5]])

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 信息流处理失败: {e}"


def _fetch_github(token: str, query: str = ""):
    """GitHub API 数据获取"""
    try:
        import urllib.request
        import urllib.parse

        if query:
            # 搜索仓库
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&per_page=10"
        else:
            # 获取通知
            url = "https://api.github.com/notifications?per_page=10"

        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-Assistant"
        })

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if query:
            items = data.get("items", [])
            if not items:
                return f"🔍 GitHub 未找到相关仓库: {query}"
            lines = [f"🔍 GitHub 搜索 '{query}' ({data.get('total_count', 0)} 结果):\n"]
            for r in items[:10]:
                stars = r.get("stargazers_count", 0)
                desc = r.get("description", "") or ""
                lines.append(f"  ⭐ {stars:,} {r['full_name']}")
                if desc:
                    lines.append(f"       {desc[:80]}")
                lines.append(f"       🔗 {r['html_url']}")
            return "\n".join(lines)
        else:
            if not data:
                return "📬 GitHub 暂无未读通知"
            lines = [f"📬 GitHub 通知 ({len(data)} 条):\n"]
            for n in data[:10]:
                subject = n.get("subject", {})
                lines.append(f"  [{n.get('reason', '')}] {subject.get('title', '')}")
                lines.append(f"       {subject.get('type', '')} - {n.get('repository', {}).get('full_name', '')}")
            return "\n".join(lines)

    except Exception as e:
        return f"❌ GitHub API 请求失败: {e}"


# ==========================================
# 5. 微信公众号 RSS 桥接
# ==========================================
WECHAT_RSS_BRIDGES = {
    "werss": {
        "name": "WeRSS",
        "url_template": "https://werss.app/api/v1/feeds/{account_id}.xml",
        "api_key_env": "WERSS_API_KEY",
        "help_url": "https://werss.app",
        "description": "付费服务，稳定可靠",
    },
    "feeddd": {
        "name": "Feeddd",
        "url_template": "https://feeddd.org/feeds/{account_id}",
        "api_key_env": "",
        "help_url": "https://feeddd.org",
        "description": "免费社区项目",
    },
    "wechat2rss": {
        "name": "WeChat2RSS",
        "url_template": "https://wechat2rss.xlab.app/feed/{account_id}.xml",
        "api_key_env": "WECHAT2RSS_TOKEN",
        "help_url": "https://wechat2rss.xlab.app",
        "description": "开源项目，可自建",
    },
    "custom": {
        "name": "自定义 RSS 源",
        "url_template": "{custom_url}",
        "api_key_env": "",
        "help_url": "",
        "description": "自行提供完整 RSS URL",
    },
}

wechat_bridge_schema = {
    "type": "function",
    "function": {
        "name": "wechat_bridge",
        "description": (
            "微信公众号 RSS 桥接工具。通过第三方 RSS 服务订阅微信公众号文章，"
            "无需微信 API 或客户端自动化，安全无封号风险。"
            "支持: subscribe(订阅), list(列出), fetch(抓取), bridges(查看服务商)"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: subscribe(订阅公众号), unsubscribe(取消), list(列出), fetch(抓取), fetch_all(全部抓取), bridges(服务商列表)",
                },
                "account_name": {"type": "string", "description": "公众号名称（subscribe/unsubscribe 时使用）"},
                "account_id": {
                    "type": "string",
                    "description": "公众号 ID 或微信号（用于生成 RSS URL，各桥接服务定义不同）",
                },
                "bridge": {
                    "type": "string",
                    "description": "RSS 桥接服务: werss/feeddd/wechat2rss/custom，默认 feeddd",
                },
                "custom_url": {"type": "string", "description": "自定义 RSS URL（bridge=custom 时使用）"},
                "max_items": {"type": "integer", "description": "最大抓取条目数，默认 10"},
            },
            "required": ["action"],
        },
    },
}


def _load_wechat_subs():
    subs_obj = _guarded_social_file("wechat_subs.json")
    if subs_obj.exists():
        with open(subs_obj, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def _save_wechat_subs(subs):
    subs_obj = _guarded_social_file("wechat_subs.json")
    with open(subs_obj, 'w', encoding='utf-8') as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def _build_wechat_rss_url(bridge: str, account_id: str, custom_url: str = ""):
    """Build the RSS URL from bridge template."""
    bridge_info = WECHAT_RSS_BRIDGES.get(bridge)
    if not bridge_info:
        return None, f"❌ 未知桥接服务: {bridge}。可选: {', '.join(WECHAT_RSS_BRIDGES.keys())}"

    if bridge == "custom":
        if not custom_url:
            return None, "❌ bridge=custom 时必须提供 custom_url"
        url = bridge_info["url_template"].format(custom_url=custom_url)
    else:
        if not account_id:
            return None, "❌ 请提供 account_id (公众号 ID 或微信号)"
        url = bridge_info["url_template"].format(account_id=account_id)

    # Append API key if needed
    api_key_env = bridge_info.get("api_key_env", "")
    if api_key_env:
        api_key = os.getenv(api_key_env, "").strip()
        if api_key:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}token={api_key}"

    return url, None


@register(wechat_bridge_schema)
def wechat_bridge(
    action: str,
    account_name: str = "",
    account_id: str = "",
    bridge: str = "feeddd",
    custom_url: str = "",
    max_items: int = 10,
):
    """微信公众号 RSS 桥接"""
    try:
        action = (action or "").strip().lower()
        max_items = max(1, min(int(max_items) if max_items else 10, 30))

        if action == "bridges":
            lines = ["🔌 微信公众号 RSS 桥接服务:\n"]
            for bid, binfo in WECHAT_RSS_BRIDGES.items():
                key_status = ""
                if binfo.get("api_key_env"):
                    has_key = bool(os.getenv(binfo["api_key_env"], "").strip())
                    key_status = " ✅" if has_key else f" ⚠️ 需配置 {binfo['api_key_env']}"
                lines.append(f"  [{bid}] {binfo['name']}{key_status}")
                lines.append(f"    {binfo['description']}")
                if binfo.get("help_url"):
                    lines.append(f"    🔗 {binfo['help_url']}")
                lines.append("")
            lines.append(
                "💡 推荐: feeddd (免费) 或 werss (付费但稳定)。\n"
                "   也可 bridge=custom 直接传入任何 RSS URL。"
            )
            return "\n".join(lines)

        subs = _load_wechat_subs()

        if action == "subscribe":
            if not account_name:
                return "❌ 请提供 account_name (公众号名称)"

            bridge = (bridge or "feeddd").strip().lower()
            rss_url, url_err = _build_wechat_rss_url(bridge, account_id, custom_url)
            if url_err:
                return url_err

            # Check duplicate
            for s in subs:
                if s.get("account_name") == account_name or s.get("rss_url") == rss_url:
                    return f"⚠️ 已订阅: {account_name}"

            sub = {
                "account_name": account_name,
                "account_id": account_id or "",
                "bridge": bridge,
                "rss_url": rss_url,
                "added_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            subs.append(sub)
            _save_wechat_subs(subs)

            # Also add to main RSS feeds for unified pipeline
            feeds = _load_feeds()
            if not any(f["url"] == rss_url for f in feeds):
                feeds.append({
                    "url": rss_url,
                    "name": f"[微信] {account_name}",
                    "category": "wechat",
                    "added": time.strftime("%Y-%m-%d %H:%M"),
                })
                _save_feeds(feeds)

            return (
                f"✅ 已订阅微信公众号: {account_name}\n"
                f"  桥接服务: {WECHAT_RSS_BRIDGES.get(bridge, {}).get('name', bridge)}\n"
                f"  RSS URL: {rss_url}\n"
                f"  💡 已同步到 RSS 订阅，可通过 rss_manage/infoflow_pipeline 统一处理。"
            )

        elif action == "unsubscribe":
            if not account_name:
                return "❌ 请提供 account_name"
            before = len(subs)
            removed_urls = [s["rss_url"] for s in subs if s.get("account_name") == account_name]
            subs = [s for s in subs if s.get("account_name") != account_name]
            if len(subs) == before:
                return f"❌ 未找到订阅: {account_name}"
            _save_wechat_subs(subs)

            # Also remove from main RSS feeds
            if removed_urls:
                feeds = _load_feeds()
                feeds = [f for f in feeds if f["url"] not in removed_urls]
                _save_feeds(feeds)

            return f"✅ 已取消订阅: {account_name}"

        elif action == "list":
            if not subs:
                return (
                    "📱 暂无微信公众号订阅\n"
                    "💡 使用 wechat_bridge(action='bridges') 查看可用桥接服务\n"
                    "   使用 wechat_bridge(action='subscribe', ...) 添加订阅"
                )
            lines = [f"📱 微信公众号订阅 ({len(subs)} 个):\n"]
            for s in subs:
                bridge_name = WECHAT_RSS_BRIDGES.get(s.get("bridge", ""), {}).get("name", s.get("bridge", "?"))
                lines.append(f"  📰 {s['account_name']}")
                lines.append(f"     桥接: {bridge_name}")
                lines.append(f"     RSS: {s['rss_url']}")
                lines.append("")
            return "\n".join(lines)

        elif action == "fetch":
            if not account_name:
                return "❌ 请提供 account_name"
            sub = next((s for s in subs if s.get("account_name") == account_name), None)
            if not sub:
                return f"❌ 未找到订阅: {account_name}"

            url = sub["rss_url"]
            url_err = _validate_public_http_url(url)
            if url_err:
                return url_err

            items = _fetch_rss(url, max_items)
            if not items:
                return f"⚠️ 未抓取到内容: {account_name}\n  RSS: {url}\n  💡 可能桥接服务暂时不可用，请稍后重试。"

            lines = [f"📱 [{account_name}] 最新文章 ({len(items)} 篇):\n"]
            for i, item in enumerate(items):
                lines.append(f"  {i+1}. **{item['title']}**")
                if item.get("date"):
                    lines.append(f"     📅 {item['date']}")
                if item.get("link"):
                    lines.append(f"     🔗 {item['link']}")
                if item.get("description"):
                    lines.append(f"     {item['description']}")
                lines.append("")
            return "\n".join(lines)

        elif action == "fetch_all":
            if not subs:
                return "📱 暂无微信公众号订阅"

            all_items = []
            errors = []
            for s in subs:
                try:
                    url = s["rss_url"]
                    url_err = _validate_public_http_url(url)
                    if url_err:
                        errors.append(f"{s['account_name']}: {url_err}")
                        continue
                    items = _fetch_rss(url, max_items=5)
                    for item in items:
                        item["source"] = f"[微信] {s['account_name']}"
                    all_items.extend(items)
                except Exception as e:
                    errors.append(f"{s['account_name']}: {e}")

            if not all_items:
                err_msg = "; ".join(errors) if errors else "未知错误"
                return f"⚠️ 未抓取到任何微信文章。{err_msg}"

            lines = [f"📱 微信公众号汇总 ({len(all_items)} 篇，来自 {len(subs)} 个号):\n"]
            for i, item in enumerate(all_items[:max_items]):
                lines.append(f"  {i+1}. [{item.get('source', '')}] **{item['title']}**")
                if item.get("link"):
                    lines.append(f"     🔗 {item['link']}")
                if item.get("description"):
                    lines.append(f"     {item['description']}")
                lines.append("")

            if errors:
                lines.append(f"⚠️ {len(errors)} 个号抓取失败: {'; '.join(errors[:5])}")

            return "\n".join(lines)

        else:
            return f"❌ 未知操作: {action}。支持: subscribe, unsubscribe, list, fetch, fetch_all, bridges"

    except Exception as e:
        return f"❌ 微信桥接失败: {e}"
