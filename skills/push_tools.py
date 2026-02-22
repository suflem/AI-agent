# skills/push_tools.py
# 消息推送工具：渠道配置、发送通知、提醒到期推送

import json
import os
import time
import urllib.request
from pathlib import Path

from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


NOTIFY_DIR = "data/notifications"
CHANNELS_FILE = "channels.json"
REMINDERS_FILE = "data/reminders.json"


def _display_path(path_obj: Path):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _ensure_notify_dir():
    dir_obj, err = guard_path(NOTIFY_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not dir_obj.exists():
        dir_obj.mkdir(parents=True, exist_ok=True)
    return dir_obj


def _channels_file():
    dir_obj = _ensure_notify_dir()
    file_obj, err = guard_path(str(dir_obj / CHANNELS_FILE), must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    return file_obj


def _load_channels():
    file_obj = _channels_file()
    if file_obj.exists():
        with open(file_obj, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def _save_channels(channels):
    file_obj = _channels_file()
    with open(file_obj, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)


def _safe_name(name: str):
    raw = (name or "").strip()
    if not raw:
        return ""
    allowed = "".join(c for c in raw if c.isalnum() or c in ("_", "-", " "))
    return allowed.strip()[:64]


def _post_json(url: str, payload: dict, timeout: int = 10):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def _send_webhook(config: dict, title: str, content: str):
    url = (config.get("url") or "").strip()
    if not url:
        return False, "缺少 webhook url"
    try:
        code, _ = _post_json(url, {"title": title, "content": content, "ts": time.time()})
        return 200 <= code < 300, f"webhook HTTP {code}"
    except Exception as e:
        return False, f"webhook 失败: {e}"


def _send_telegram(config: dict, title: str, content: str):
    token = (config.get("token") or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = (config.get("chat_id") or "").strip()
    if not token or not chat_id:
        return False, "缺少 telegram token/chat_id"
    text = f"*{title}*\n\n{content}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        code, _ = _post_json(url, payload)
        return 200 <= code < 300, f"telegram HTTP {code}"
    except Exception as e:
        return False, f"telegram 失败: {e}"


def _send_email(config: dict, title: str, content: str):
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    host = (config.get("smtp_host") or os.getenv("SMTP_HOST", "")).strip()
    port = int(config.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
    user = (config.get("smtp_user") or os.getenv("SMTP_USER", "")).strip()
    password = (config.get("smtp_pass") or os.getenv("SMTP_PASS", "")).strip()
    sender = (config.get("from") or os.getenv("SMTP_FROM", user)).strip()
    to_addr = (config.get("to") or "").strip()
    use_ssl = bool(config.get("ssl", False))

    if not (host and user and password and sender and to_addr):
        return False, "缺少 SMTP 配置(host/user/pass/from/to)"

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = sender
    msg["To"] = to_addr

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(user, password)
        server.sendmail(sender, [to_addr], msg.as_string())
        server.quit()
        return True, "email sent"
    except Exception as e:
        return False, f"email 失败: {e}"


def _dispatch_channel(channel: dict, title: str, content: str):
    ctype = (channel.get("type") or "").strip().lower()
    cfg = channel.get("config", {}) if isinstance(channel.get("config", {}), dict) else {}
    if ctype == "console":
        return True, "console ok"
    if ctype == "webhook":
        return _send_webhook(cfg, title, content)
    if ctype == "telegram":
        return _send_telegram(cfg, title, content)
    if ctype == "email":
        return _send_email(cfg, title, content)
    return False, f"不支持的渠道类型: {ctype}"


notify_manage_schema = {
    "type": "function",
    "function": {
        "name": "notify_manage",
        "description": (
            "管理消息推送渠道。支持 console/webhook/telegram/email 四类，"
            "用于提醒、日程和信息流推送。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: upsert/list/remove"},
                "channel_name": {"type": "string", "description": "渠道名称"},
                "channel_type": {"type": "string", "description": "渠道类型: console/webhook/telegram/email"},
                "enabled": {"type": "boolean", "description": "是否启用，默认 true"},
                "config_json": {"type": "string", "description": "配置 JSON，如 webhook 的 {\"url\":\"...\"}"}
            },
            "required": ["action"]
        }
    }
}


@register(notify_manage_schema)
def notify_manage(
    action: str,
    channel_name: str = "",
    channel_type: str = "",
    enabled: bool = True,
    config_json: str = "",
):
    try:
        action = (action or "").strip().lower()
        channels = _load_channels()

        if action == "list":
            if not channels:
                return "📨 暂无推送渠道配置"
            lines = [f"📨 推送渠道 ({len(channels)}):\n"]
            for c in channels:
                status = "✅" if c.get("enabled", True) else "⏸️"
                lines.append(f"  {status} {c.get('name', '?')} ({c.get('type', '?')})")
            lines.append(f"\n配置文件: {_display_path(_channels_file())}")
            return "\n".join(lines)

        if action == "remove":
            cname = _safe_name(channel_name)
            if not cname:
                return "❌ remove 需要 channel_name"
            before = len(channels)
            channels = [c for c in channels if c.get("name", "") != cname]
            if len(channels) == before:
                return f"❌ 未找到渠道: {cname}"
            _save_channels(channels)
            return f"✅ 已删除渠道: {cname}"

        if action == "upsert":
            cname = _safe_name(channel_name)
            ctype = (channel_type or "").strip().lower()
            if not cname or not ctype:
                return "❌ upsert 需要 channel_name 和 channel_type"
            if ctype not in {"console", "webhook", "telegram", "email"}:
                return "❌ channel_type 仅支持: console/webhook/telegram/email"

            cfg = {}
            if config_json.strip():
                try:
                    cfg = json.loads(config_json)
                    if not isinstance(cfg, dict):
                        return "❌ config_json 必须是 JSON 对象"
                except Exception:
                    return "❌ config_json 解析失败"

            now_str = time.strftime("%Y-%m-%d %H:%M")
            found = False
            for c in channels:
                if c.get("name", "") == cname:
                    c["type"] = ctype
                    c["enabled"] = bool(enabled)
                    c["config"] = cfg
                    c["updated_at"] = now_str
                    found = True
                    break
            if not found:
                channels.append({
                    "name": cname,
                    "type": ctype,
                    "enabled": bool(enabled),
                    "config": cfg,
                    "created_at": now_str,
                    "updated_at": now_str,
                })

            _save_channels(channels)
            return f"✅ 已{'更新' if found else '新增'}推送渠道: {cname} ({ctype})"

        return "❌ 未知 action。支持: upsert/list/remove"
    except Exception as e:
        return f"❌ 推送渠道管理失败: {e}"


notify_send_schema = {
    "type": "function",
    "function": {
        "name": "notify_send",
        "description": "发送消息到已配置推送渠道。可指定渠道名，不指定则发送到全部启用渠道。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "消息标题"},
                "content": {"type": "string", "description": "消息正文"},
                "channel_names": {"type": "string", "description": "渠道名列表，逗号分隔"},
            },
            "required": ["title", "content"]
        }
    }
}


@register(notify_send_schema)
def notify_send(title: str, content: str, channel_names: str = ""):
    try:
        channels = _load_channels()
        enabled_channels = [c for c in channels if c.get("enabled", True)]
        if not enabled_channels:
            return "⚠️ 没有可用推送渠道，请先 notify_manage(action='upsert', ...)"

        names = [x.strip() for x in (channel_names or "").split(",") if x.strip()]
        if names:
            selected = [c for c in enabled_channels if c.get("name", "") in set(names)]
        else:
            selected = enabled_channels
        if not selected:
            return "❌ 未匹配到可用渠道"

        results = []
        success = 0
        for ch in selected:
            ok, msg = _dispatch_channel(ch, title, content)
            if ok:
                success += 1
            results.append(f"{'✅' if ok else '❌'} {ch.get('name', '?')}: {msg}")

        return (
            f"📨 推送完成: {success}/{len(selected)}\n"
            + "\n".join(f"  - {x}" for x in results)
        )
    except Exception as e:
        return f"❌ 消息推送失败: {e}"


reminder_push_schema = {
    "type": "function",
    "function": {
        "name": "reminder_push",
        "description": (
            "检查到期提醒并推送到通知渠道。用于把 reminder_manage 的到期结果真正发出去。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_names": {"type": "string", "description": "可选，指定推送渠道名"},
            },
            "required": []
        }
    }
}


@register(reminder_push_schema)
def reminder_push(channel_names: str = ""):
    try:
        reminders_obj, err = guard_path(REMINDERS_FILE, must_exist=False, for_write=True)
        if err:
            return err
        if not reminders_obj.exists():
            return "⏰ 暂无提醒数据"

        with open(reminders_obj, "r", encoding="utf-8") as f:
            reminders = json.load(f)
        if not isinstance(reminders, list):
            return "❌ reminders.json 格式错误"

        now = time.strftime("%Y-%m-%d %H:%M")
        due = [r for r in reminders if not r.get("triggered") and r.get("remind_time", "") <= now]
        if not due:
            return "✅ 暂无到期提醒"

        lines = ["🔔 到期提醒："]
        for r in due:
            r["triggered"] = True
            lines.append(f"- #{r.get('id', '?')} [{r.get('remind_time', '')}] {r.get('content', '')}")

        with open(reminders_obj, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)

        message = "\n".join(lines)
        send_result = notify_send(
            title=f"到期提醒 {len(due)} 条",
            content=message,
            channel_names=channel_names,
        )
        return f"{message}\n\n{send_result}"
    except Exception as e:
        return f"❌ 提醒推送失败: {e}"
