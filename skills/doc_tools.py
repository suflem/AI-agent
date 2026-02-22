# skills/doc_tools.py
# 文献阅读与翻译工具：PDF 解析、文档摘要、翻译

import os
from pathlib import Path
from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


def _display_path(path_obj: Path):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


# ==========================================
# 1. 翻译工具
# ==========================================
translate_schema = {
    "type": "function",
    "function": {
        "name": "translate",
        "description": (
            "翻译文本。使用已配置的 AI 模型进行高质量翻译。"
            "支持任意语言之间互译。可指定目标语言和翻译风格。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要翻译的文本"},
                "target_lang": {"type": "string", "description": "目标语言，如 '中文'、'English'、'日本語'，默认中文"},
                "style": {
                    "type": "string",
                    "description": "翻译风格: 'literal'(直译), 'free'(意译), 'academic'(学术), 'casual'(口语化)，默认 free"
                }
            },
            "required": ["text"]
        }
    }
}


@register(translate_schema)
def translate(text: str, target_lang: str = "中文", style: str = "free"):
    """使用 AI 翻译文本"""
    try:
        from .external_ai import call_ai

        style_map = {
            "literal": "逐字逐句直译，保持原文结构",
            "free": "意译，注重通顺自然，符合目标语言的表达习惯",
            "academic": "学术翻译，使用专业术语，保持严谨性",
            "casual": "口语化翻译，通俗易懂"
        }
        style_desc = style_map.get(style, style_map["free"])

        system = f"你是专业翻译。将用户提供的文本翻译为{target_lang}。翻译风格：{style_desc}。只输出翻译结果，不要解释。"

        result = call_ai(
            prompt=text,
            provider="kimi",
            system_prompt=system,
            temperature=0.3,
            max_tokens=8000
        )
        return result

    except Exception as e:
        return f"❌ 翻译失败: {e}"


# ==========================================
# 2. PDF 文本提取
# ==========================================
read_pdf_schema = {
    "type": "function",
    "function": {
        "name": "read_pdf",
        "description": (
            "读取 PDF 文件并提取文本内容。支持学术论文、技术文档等。"
            "需要安装 PyPDF2 库。对于扫描版 PDF 可能无法提取文本。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "PDF 文件路径"},
                "start_page": {"type": "integer", "description": "起始页码 (从1开始)，默认1"},
                "end_page": {"type": "integer", "description": "结束页码，默认读取全部"},
                "max_chars": {"type": "integer", "description": "最大返回字符数，默认 10000"}
            },
            "required": ["filepath"]
        }
    }
}


@register(read_pdf_schema)
def read_pdf(filepath: str, start_page: int = 1, end_page: int = 0, max_chars: int = 10000):
    """读取 PDF 文件"""
    try:
        file_obj, err = guard_path(filepath, must_exist=True, for_write=False)
        if err:
            return err
        if file_obj.is_dir():
            return f"❌ 请输入 PDF 文件路径，当前是目录: {_display_path(file_obj)}"
        if file_obj.suffix.lower() != '.pdf':
            return f"❌ 不是 PDF 文件: {_display_path(file_obj)}"

        try:
            import PyPDF2
        except ImportError:
            return "❌ 需要安装 PyPDF2: pip install PyPDF2"

        max_chars = min(int(max_chars) if max_chars else 10000, 50000)

        with open(file_obj, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)

            start = max(1, int(start_page) if start_page else 1) - 1
            end = int(end_page) if end_page else total_pages
            end = min(end, total_pages)

            pages_text = []
            for i in range(start, end):
                text = reader.pages[i].extract_text()
                if text:
                    pages_text.append(f"--- 第 {i+1} 页 ---\n{text}")

        if not pages_text:
            return f"⚠️ PDF 无法提取文本 (可能是扫描版): {_display_path(file_obj)}"

        full_text = "\n\n".join(pages_text)
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n\n... (已截断，共约 {len(full_text)} 字符)"

        return f"📄 PDF: {_display_path(file_obj)} ({total_pages} 页, 读取第 {start+1}-{end} 页)\n\n{full_text}"

    except Exception as e:
        return f"❌ PDF 读取失败: {e}"


# ==========================================
# 3. 文档摘要
# ==========================================
summarize_doc_schema = {
    "type": "function",
    "function": {
        "name": "summarize_document",
        "description": (
            "对文档内容生成摘要。支持文本文件、PDF、Markdown 等。"
            "使用 AI 模型自动提取关键信息并生成结构化摘要。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "文档文件路径"},
                "summary_type": {
                    "type": "string",
                    "description": "摘要类型: 'brief'(简要100字), 'detailed'(详细500字), 'outline'(大纲), 'key_points'(关键要点)"
                },
                "language": {"type": "string", "description": "输出语言，默认中文"}
            },
            "required": ["filepath"]
        }
    }
}


@register(summarize_doc_schema)
def summarize_document(filepath: str, summary_type: str = "detailed", language: str = "中文"):
    """文档摘要"""
    try:
        file_obj, err = guard_path(filepath, must_exist=True, for_write=False)
        if err:
            return err
        if file_obj.is_dir():
            return f"❌ 请输入文档文件路径，当前是目录: {_display_path(file_obj)}"

        # 读取文档内容
        ext = file_obj.suffix.lower()
        content = ""

        if ext == '.pdf':
            result = read_pdf(str(file_obj), max_chars=15000)
            if result.startswith("❌"):
                return result
            content = result
        else:
            try:
                with open(file_obj, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                return f"❌ 无法读取文件 (非文本格式): {_display_path(file_obj)}"

        if not content.strip():
            return f"⚠️ 文件内容为空: {filepath}"

        if len(content) > 15000:
            content = content[:15000] + "\n\n[内容已截断...]"

        type_prompts = {
            "brief": f"用{language}写一段100字以内的简要摘要。",
            "detailed": f"用{language}写一段500字左右的详细摘要，包含主要论点和关键发现。",
            "outline": f"用{language}提取文档的大纲结构，用层级列表展示。",
            "key_points": f"用{language}列出文档的5-10个关键要点，每点一句话。"
        }
        type_prompt = type_prompts.get(summary_type, type_prompts["detailed"])

        from .external_ai import call_ai
        result = call_ai(
            prompt=f"请阅读以下文档并{type_prompt}\n\n---\n{content}",
            provider="kimi",
            system_prompt="你是专业的文档分析助手。准确提取文档要点，不要编造内容。",
            temperature=0.3,
            max_tokens=4096
        )
        return f"📝 文档摘要: {_display_path(file_obj)}\n{result}"

    except Exception as e:
        return f"❌ 摘要生成失败: {e}"
