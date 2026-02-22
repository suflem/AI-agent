# skills/video_tools.py
# 视频工具：视频信息提取、字幕/转录获取、AI 总结、剪辑接口

import os
import json
import re
import time
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# ==========================================
# 1. 视频信息提取
# ==========================================
video_info_schema = {
    "type": "function",
    "function": {
        "name": "video_info",
        "description": (
            "获取本地视频文件的基本信息（时长、分辨率、编码、大小等）。"
            "需要安装 ffprobe (FFmpeg 套件)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "视频文件路径"}
            },
            "required": ["filepath"]
        }
    }
}


@register(video_info_schema)
def video_info(filepath: str):
    """获取视频文件信息"""
    try:
        file_obj, err = guard_path(filepath, must_exist=True, for_write=False)
        if err:
            return err
        if file_obj.is_dir():
            return f"❌ 请输入视频文件路径，当前是目录: {_display_path(file_obj)}"

        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file_obj)],
            capture_output=True, text=True, timeout=15
        )

        if result.returncode != 0:
            return f"❌ ffprobe 执行失败。请确认已安装 FFmpeg。\n{result.stderr[:300]}"

        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        info_lines = [f"🎬 视频信息: {_display_path(file_obj)}\n"]

        # 格式信息
        duration = float(fmt.get("duration", 0))
        mins, secs = divmod(duration, 60)
        hrs, mins = divmod(mins, 60)
        size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
        bitrate = int(fmt.get("bit_rate", 0)) / 1000

        info_lines.append(f"  时长: {int(hrs):02d}:{int(mins):02d}:{secs:05.2f}")
        info_lines.append(f"  大小: {size_mb:.1f} MB")
        info_lines.append(f"  码率: {bitrate:.0f} kbps")
        info_lines.append(f"  格式: {fmt.get('format_long_name', '未知')}")

        for s in streams:
            codec_type = s.get("codec_type", "")
            if codec_type == "video":
                w = s.get("width", "?")
                h = s.get("height", "?")
                fps = s.get("r_frame_rate", "?")
                codec = s.get("codec_name", "?")
                info_lines.append(f"\n  🖥️ 视频流: {w}x{h}, {fps} fps, {codec}")
            elif codec_type == "audio":
                codec = s.get("codec_name", "?")
                sr = s.get("sample_rate", "?")
                ch = s.get("channels", "?")
                info_lines.append(f"  🔊 音频流: {codec}, {sr} Hz, {ch} 声道")

        return "\n".join(info_lines)

    except FileNotFoundError:
        return "❌ 未找到 ffprobe 命令。请安装 FFmpeg: https://ffmpeg.org/download.html"
    except Exception as e:
        return f"❌ 获取视频信息失败: {e}"


# ==========================================
# 2. 提取视频字幕/转录
# ==========================================
video_transcript_schema = {
    "type": "function",
    "function": {
        "name": "video_transcript",
        "description": (
            "提取视频的字幕或通过 AI 转录音频获取文本。"
            "支持：1) 提取内嵌字幕 (SRT)  2) 读取同名字幕文件  3) 从 YouTube URL 获取字幕。"
            "如需语音转文字，需要安装 whisper (openai-whisper)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "视频文件路径或 YouTube URL"},
                "method": {
                    "type": "string",
                    "description": "提取方法: 'subtitle'(内嵌字幕), 'file'(外部字幕文件), 'whisper'(语音转文字), 'youtube'(YouTube字幕)，默认自动检测"
                },
                "language": {"type": "string", "description": "语言代码 (如 'zh', 'en')，用于 YouTube 字幕和 whisper"}
            },
            "required": ["source"]
        }
    }
}


def _extract_youtube_transcript(url: str, language: str = "zh"):
    """从 YouTube 获取字幕"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # 提取 video ID
        video_id = None
        patterns = [
            r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                video_id = m.group(1)
                break

        if not video_id:
            return f"❌ 无法从 URL 提取 YouTube 视频 ID: {url}"

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # 尝试获取指定语言的字幕
            try:
                transcript = transcript_list.find_transcript([language])
            except Exception:
                # 获取任何可用字幕
                transcript = transcript_list.find_transcript(['en', 'zh-Hans', 'zh', 'ja'])

            entries = transcript.fetch()
            lines = []
            for entry in entries:
                if isinstance(entry, dict):
                    text = entry.get('text', '')
                else:
                    text = getattr(entry, 'text', str(entry))
                text = str(text).strip()
                if text:
                    lines.append(text)
            return "\n".join(lines)

        except Exception as e:
            return f"❌ YouTube 字幕获取失败: {e}"

    except ImportError:
        return "❌ 需要安装 youtube-transcript-api: pip install youtube-transcript-api"


def _extract_subtitle_file(filepath: str):
    """读取同名字幕文件"""
    base = os.path.splitext(filepath)[0]
    for ext in ['.srt', '.vtt', '.ass', '.ssa', '.sub']:
        sub_file = base + ext
        if os.path.exists(sub_file):
            with open(sub_file, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    return None


def _extract_embedded_subtitle(video_path: str):
    """尝试提取内嵌字幕（第一个字幕轨）"""
    import subprocess

    output_path = video_path + ".embedded.srt"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-map", "0:s:0",
        "-f", "srt",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not os.path.exists(output_path):
        return None

    try:
        with open(output_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


@register(video_transcript_schema)
def video_transcript(source: str, method: str = "", language: str = "zh"):
    """提取视频字幕/转录"""
    try:
        method = (method or "").strip().lower()

        # YouTube URL
        if 'youtube.com' in source or 'youtu.be' in source:
            if method and method not in ("youtube",):
                return "⚠️ YouTube 来源仅支持 method='youtube'（或留空自动）"
            text = _extract_youtube_transcript(source, language)
            if text.startswith("❌"):
                return text
            if len(text) > 12000:
                text = text[:12000] + "\n\n... (字幕过长，已截断)"
            return f"📝 YouTube 字幕:\n\n{text}"

        # 本地文件
        source_obj, err = guard_path(source, must_exist=True, for_write=False)
        if err:
            return err
        if source_obj.is_dir():
            return f"❌ 请输入视频文件路径，当前是目录: {_display_path(source_obj)}"

        source_abs = str(source_obj)

        # 尝试读取外部字幕文件
        if method in ("", "file"):
            sub = _extract_subtitle_file(source_abs)
            if sub:
                if len(sub) > 10000:
                    sub = sub[:10000] + "\n\n... (已截断)"
                return f"📝 外部字幕文件内容 [{_display_path(source_obj)}]:\n\n{sub}"

        # 尝试提取内嵌字幕
        if method in ("", "subtitle"):
            embedded = _extract_embedded_subtitle(source_abs)
            if embedded:
                if len(embedded) > 10000:
                    embedded = embedded[:10000] + "\n\n... (已截断)"
                return f"📝 内嵌字幕提取结果 [{_display_path(source_obj)}]:\n\n{embedded}"

        # 使用 whisper 转录
        if method in ("", "whisper"):
            try:
                import subprocess
                # 先提取音频
                audio_path = source_abs + ".temp.wav"
                ffmpeg_result = subprocess.run(
                    ["ffmpeg", "-i", source_abs, "-ar", "16000", "-ac", "1", "-y", audio_path],
                    capture_output=True, text=True, timeout=120
                )

                if ffmpeg_result.returncode != 0:
                    return f"❌ 音频提取失败: {ffmpeg_result.stderr[-300:]}"

                try:
                    import whisper
                    model = whisper.load_model("base")
                    transcribe_kwargs = {}
                    if language:
                        transcribe_kwargs["language"] = language
                    result = model.transcribe(audio_path, **transcribe_kwargs)
                    text = result.get("text", "").strip()
                    if not text:
                        return "⚠️ Whisper 未产出可用文本"
                    if len(text) > 12000:
                        text = text[:12000] + "\n\n... (转录过长，已截断)"
                    return f"🎙️ Whisper 转录结果 [{_display_path(source_obj)}]:\n\n{text}"
                except ImportError:
                    return "❌ 需要安装 openai-whisper: pip install openai-whisper"
                finally:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)

            except FileNotFoundError:
                return "❌ 需要 FFmpeg 来提取音频。请安装 FFmpeg。"

        return f"❌ 无法提取字幕。可尝试 method='file'/'subtitle'/'whisper'，或安装 openai-whisper。"

    except Exception as e:
        return f"❌ 字幕提取失败: {e}"


# ==========================================
# 3. 视频总结
# ==========================================
video_summary_schema = {
    "type": "function",
    "function": {
        "name": "video_summary",
        "description": (
            "对视频内容进行 AI 总结。先提取字幕/转录，然后用 AI 生成摘要。"
            "支持本地视频文件和 YouTube URL。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "视频文件路径或 YouTube URL"},
                "summary_type": {
                    "type": "string",
                    "description": "摘要类型: 'brief'(简要), 'detailed'(详细), 'timeline'(时间线), 'key_points'(要点)"
                },
                "language": {"type": "string", "description": "字幕语言代码，默认 zh"}
            },
            "required": ["source"]
        }
    }
}


@register(video_summary_schema)
def video_summary(source: str, summary_type: str = "detailed", language: str = "zh"):
    """视频 AI 总结"""
    try:
        # 先获取字幕
        transcript = video_transcript(source, language=language)
        if transcript.startswith("❌"):
            return transcript

        # 截取文本用于 AI 总结
        max_text = 12000
        if len(transcript) > max_text:
            transcript = transcript[:max_text] + "\n[后续内容已截断]"

        type_prompts = {
            "brief": "生成 100 字以内的简要总结。",
            "detailed": "生成 500 字左右的详细总结，覆盖主要内容。",
            "timeline": "按时间顺序列出视频的关键节点和内容。",
            "key_points": "提取 5-10 个关键要点，每点一句话。"
        }
        prompt = type_prompts.get(summary_type, type_prompts["detailed"])

        from .external_ai import call_ai
        result = call_ai(
            prompt=f"以下是一段视频的字幕/转录文本，请{prompt}\n\n---\n{transcript}",
            provider="kimi",
            system_prompt="你是视频内容分析师。根据字幕/转录文本准确总结视频内容，不要编造信息。",
            temperature=0.3,
            max_tokens=4096
        )
        return f"🎬 视频总结:\n{result}"

    except Exception as e:
        return f"❌ 视频总结失败: {e}"


# ==========================================
# 4. 视频剪辑 (FFmpeg 接口)
# ==========================================
video_clip_schema = {
    "type": "function",
    "function": {
        "name": "video_clip",
        "description": (
            "【危险操作】使用 FFmpeg 剪辑视频片段。支持裁剪时间段、提取音频、转换格式等。"
            "需要安装 FFmpeg。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入视频文件路径"},
                "output_file": {"type": "string", "description": "输出文件路径"},
                "start_time": {"type": "string", "description": "开始时间 (格式: HH:MM:SS 或秒数)"},
                "end_time": {"type": "string", "description": "结束时间"},
                "extra_args": {"type": "string", "description": "额外的 FFmpeg 参数 (如 '-vf scale=1280:720')"}
            },
            "required": ["input_file", "output_file"]
        }
    }
}


@register(video_clip_schema)
def video_clip(input_file: str, output_file: str, start_time: str = "",
               end_time: str = "", extra_args: str = ""):
    """视频剪辑"""
    try:
        input_obj, err = guard_path(input_file, must_exist=True, for_write=False)
        if err:
            return err
        if input_obj.is_dir():
            return f"❌ 输入必须是文件: {_display_path(input_obj)}"

        output_obj, err = guard_path(output_file, must_exist=False, for_write=True)
        if err:
            return err
        if not output_obj.parent.exists():
            output_obj.parent.mkdir(parents=True, exist_ok=True)

        import subprocess
        cmd = ["ffmpeg", "-i", str(input_obj)]

        if start_time:
            cmd.extend(["-ss", start_time])
        if end_time:
            cmd.extend(["-to", end_time])
        if extra_args:
            # 只允许已知安全的 ffmpeg 参数前缀，防止注入
            ALLOWED_ARG_PREFIXES = (
                "-vf", "-af", "-vcodec", "-acodec", "-b:", "-r", "-s",
                "-crf", "-preset", "-c:", "-an", "-vn", "-ac", "-ar",
                "-filter:", "-map", "-t", "-frames:",
            )
            parts = extra_args.split()
            sanitized = []
            for part in parts:
                if part.startswith("-") and not any(part.startswith(p) for p in ALLOWED_ARG_PREFIXES):
                    return f"❌ 不允许的 FFmpeg 参数: {part}。允许的前缀: {', '.join(ALLOWED_ARG_PREFIXES)}"
                sanitized.append(part)
            cmd.extend(sanitized)

        cmd.extend(["-y", str(output_obj)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return f"❌ FFmpeg 执行失败:\n{result.stderr[-500:]}"

        if output_obj.exists():
            size = output_obj.stat().st_size / (1024 * 1024)
            return f"✅ 视频剪辑完成: {_display_path(output_obj)} ({size:.1f} MB)"
        else:
            return "❌ 输出文件未生成"

    except FileNotFoundError:
        return "❌ 未找到 FFmpeg。请安装: https://ffmpeg.org/download.html"
    except subprocess.TimeoutExpired:
        return "❌ 视频处理超时 (>300秒)"
    except Exception as e:
        return f"❌ 视频剪辑失败: {e}"
