# skills/academic_tools.py
# 学术写作工具：论文草稿、学术邮件、推荐信、套磁信

from .registry import register


academic_write_schema = {
    "type": "function",
    "function": {
        "name": "academic_write",
        "description": (
            "学术写作生成器。支持论文结构草稿、学术邮件、推荐信、套磁信。"
            "可根据输入背景与要求生成初稿，并给出可改写版本。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "string",
                    "description": "文档类型: paper_outline, academic_email, recommendation_letter, outreach_email"
                },
                "topic": {"type": "string", "description": "主题或申请方向"},
                "background": {"type": "string", "description": "个人背景/项目经历/论文信息"},
                "requirements": {"type": "string", "description": "额外约束，如字数、语气、必须包含的点"},
                "language": {"type": "string", "description": "输出语言，默认中文"},
                "tone": {"type": "string", "description": "语气: formal/professional/warm，默认 professional"}
            },
            "required": ["doc_type", "topic"]
        }
    }
}


@register(academic_write_schema)
def academic_write(
    doc_type: str,
    topic: str,
    background: str = "",
    requirements: str = "",
    language: str = "中文",
    tone: str = "professional",
):
    try:
        from .external_ai import call_ai

        prompts = {
            "paper_outline": (
                "生成学术论文写作草稿框架，包含：标题候选、摘要草稿、问题定义、方法、实验设计、"
                "结果展示建议、讨论与局限、参考文献组织建议。"
            ),
            "academic_email": (
                "生成学术邮件（导师/招生办/合作方）初稿，包含：主题行、简短自我介绍、来意、"
                "关键问题、礼貌结尾。再给一个更精简版本。"
            ),
            "recommendation_letter": (
                "生成推荐信草稿，包含：推荐人关系、能力证据、项目表现、研究潜力、结论推荐等级。"
            ),
            "outreach_email": (
                "生成套磁信草稿，包含：研究兴趣匹配点、你的相关成果、拟开展方向、请求交流。"
                "要求具体，避免空泛。"
            ),
        }
        if doc_type not in prompts:
            return "❌ doc_type 不支持。可选: paper_outline, academic_email, recommendation_letter, outreach_email"

        tone_map = {
            "formal": "正式严谨",
            "professional": "专业克制",
            "warm": "礼貌且有温度"
        }
        tone_text = tone_map.get(tone, tone_map["professional"])

        result = call_ai(
            prompt=(
                f"文档类型: {doc_type}\n"
                f"主题: {topic}\n"
                f"背景: {background or '（未提供）'}\n"
                f"额外要求: {requirements or '（无）'}\n"
                f"语言: {language}\n"
                f"语气: {tone_text}\n\n"
                f"任务: {prompts[doc_type]}"
            ),
            provider="kimi",
            system_prompt=(
                "你是学术写作助手。内容要真实、具体、可执行；不编造论文结果或头衔。"
                "对于邮箱/姓名/数据等未知信息，用 [待补充] 占位。"
            ),
            temperature=0.45,
            max_tokens=4096,
        )

        return f"✍️ 学术写作结果 ({doc_type})\n{result}"
    except Exception as e:
        return f"❌ 学术写作失败: {e}"


academic_revise_schema = {
    "type": "function",
    "function": {
        "name": "academic_revise",
        "description": "对已有学术文本进行润色与结构修订，支持学术邮件/推荐信/套磁信/论文段落。",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "原始文本"},
                "goal": {"type": "string", "description": "修订目标，如“更简洁”“更正式”“减少夸张表述”"},
                "language": {"type": "string", "description": "输出语言，默认中文"},
                "keep_length": {"type": "boolean", "description": "是否保持字数大致不变，默认 false"}
            },
            "required": ["text", "goal"]
        }
    }
}


@register(academic_revise_schema)
def academic_revise(
    text: str,
    goal: str,
    language: str = "中文",
    keep_length: bool = False,
):
    try:
        from .external_ai import call_ai

        length_rule = "尽量保持原文长度。" if keep_length else "可根据表达质量调整长度。"

        result = call_ai(
            prompt=(
                f"修订目标: {goal}\n"
                f"输出语言: {language}\n"
                f"{length_rule}\n\n"
                f"原文:\n{text}\n\n"
                "请输出：\n1) 修订后版本\n2) 关键修改说明（3-5条）"
            ),
            provider="kimi",
            system_prompt="你是学术写作编辑，强调清晰、礼貌、证据导向。",
            temperature=0.35,
            max_tokens=4096,
        )
        return f"🛠️ 学术文本修订\n{result}"
    except Exception as e:
        return f"❌ 学术修订失败: {e}"
