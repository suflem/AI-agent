# skills/study_tools.py
# 学习辅助工具：基于知识库生成考前资料与知识讲解

import json
from .registry import register


study_pack_schema = {
    "type": "function",
    "function": {
        "name": "study_pack",
        "description": (
            "基于指定知识库生成考前复习资料。会先检索知识片段，再由 AI 组织成结构化复习包。"
            "适合期末/考试前快速整理重点。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kb_name": {"type": "string", "description": "知识库名称"},
                "subject": {"type": "string", "description": "课程/科目名称"},
                "focus_topics": {"type": "string", "description": "重点主题，逗号分隔"},
                "top_k": {"type": "integer", "description": "检索片段数，默认 10"},
                "output_style": {
                    "type": "string",
                    "description": "输出风格: compact(紧凑), detailed(详细), qa(问答)"
                }
            },
            "required": ["kb_name", "subject"]
        }
    }
}


@register(study_pack_schema)
def study_pack(
    kb_name: str,
    subject: str,
    focus_topics: str = "",
    top_k: int = 10,
    output_style: str = "detailed",
):
    try:
        from .knowledge_tools import kb_query
        from .external_ai import call_ai

        top_k = max(3, min(int(top_k) if top_k else 10, 20))
        topics = [t.strip() for t in (focus_topics or "").split(",") if t.strip()]
        topic_text = "、".join(topics) if topics else "课程核心内容"
        query = f"{subject} 的 {topic_text}，用于考前复习"

        context = kb_query(kb_name=kb_name, query=query, top_k=top_k)
        if isinstance(context, str) and context.startswith("❌"):
            return context

        style_prompts = {
            "compact": "输出 1 页以内速记版：核心概念、公式/定义、易错点、最后冲刺清单。",
            "detailed": "输出结构化复习包：知识框架、高频考点、重点题型、常见误区、冲刺计划。",
            "qa": "输出问答版：10-15 个高价值问题，每题给简洁标准答案。"
        }
        style_prompt = style_prompts.get(output_style, style_prompts["detailed"])

        result = call_ai(
            prompt=(
                f"科目: {subject}\n"
                f"重点主题: {topic_text}\n\n"
                f"以下是知识库检索片段:\n{context}\n\n"
                f"请基于片段整理考前资料，{style_prompt}\n"
                "要求: 不编造；证据不足时明确标注“需补充资料”。"
            ),
            provider="kimi",
            system_prompt="你是高校课程学习助教，擅长考前复习资料整理。",
            temperature=0.3,
            max_tokens=4096,
        )
        return f"📚 考前复习包 ({subject})\n{result}"
    except Exception as e:
        return f"❌ 复习包生成失败: {e}"


kb_explain_schema = {
    "type": "function",
    "function": {
        "name": "kb_explain",
        "description": (
            "讲解指定知识库中的某个主题。支持分层解释（入门/本科/进阶），"
            "可附带例子和自测题。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kb_name": {"type": "string", "description": "知识库名称"},
                "topic": {"type": "string", "description": "要讲解的主题"},
                "level": {
                    "type": "string",
                    "description": "讲解层级: beginner(入门), undergraduate(本科), advanced(进阶)"
                },
                "with_quiz": {"type": "boolean", "description": "是否附带 3-5 道自测题，默认 true"},
                "top_k": {"type": "integer", "description": "检索片段数，默认 8"}
            },
            "required": ["kb_name", "topic"]
        }
    }
}


@register(kb_explain_schema)
def kb_explain(
    kb_name: str,
    topic: str,
    level: str = "undergraduate",
    with_quiz: bool = True,
    top_k: int = 8,
):
    try:
        from .knowledge_tools import kb_query
        from .external_ai import call_ai

        top_k = max(3, min(int(top_k) if top_k else 8, 20))
        level_map = {
            "beginner": "用通俗语言解释，少术语，多比喻。",
            "undergraduate": "面向本科生，兼顾概念与推导逻辑。",
            "advanced": "强调严谨性、边界条件与常见争议点。"
        }
        level_prompt = level_map.get(level, level_map["undergraduate"])
        quiz_prompt = "最后给 3-5 道自测题并附参考答案。" if with_quiz else ""

        context = kb_query(kb_name=kb_name, query=topic, top_k=top_k)
        if isinstance(context, str) and context.startswith("❌"):
            return context

        result = call_ai(
            prompt=(
                f"主题: {topic}\n"
                f"讲解要求: {level_prompt}\n\n"
                f"知识片段:\n{context}\n\n"
                "请按以下结构输出：\n"
                "1) 核心定义\n2) 关键原理\n3) 典型例子\n4) 易错点与纠正\n"
                f"{quiz_prompt}"
            ),
            provider="kimi",
            system_prompt="你是严谨的课程讲解老师，必须基于给定片段讲解。",
            temperature=0.35,
            max_tokens=4096,
        )
        return f"🎓 主题讲解: {topic}\n{result}"
    except Exception as e:
        return f"❌ 主题讲解失败: {e}"


study_plan_schema = {
    "type": "function",
    "function": {
        "name": "study_plan_generate",
        "description": "根据考试日期和知识库内容，生成可执行的倒计时复习计划。",
        "parameters": {
            "type": "object",
            "properties": {
                "kb_name": {"type": "string", "description": "知识库名称"},
                "subject": {"type": "string", "description": "课程名称"},
                "exam_date": {"type": "string", "description": "考试日期，格式 YYYY-MM-DD"},
                "daily_hours": {"type": "number", "description": "日均可投入学习时长（小时），默认 2.0"},
                "top_k": {"type": "integer", "description": "检索片段数，默认 10"}
            },
            "required": ["kb_name", "subject", "exam_date"]
        }
    }
}


@register(study_plan_schema)
def study_plan_generate(
    kb_name: str,
    subject: str,
    exam_date: str,
    daily_hours: float = 2.0,
    top_k: int = 10,
):
    try:
        from .knowledge_tools import kb_query
        from .external_ai import call_ai

        top_k = max(5, min(int(top_k) if top_k else 10, 20))
        hours = max(0.5, min(float(daily_hours) if daily_hours else 2.0, 12.0))
        context = kb_query(
            kb_name=kb_name,
            query=f"{subject} 课程的关键考点和知识结构",
            top_k=top_k,
        )
        if isinstance(context, str) and context.startswith("❌"):
            return context

        result = call_ai(
            prompt=(
                f"课程: {subject}\n"
                f"考试日期: {exam_date}\n"
                f"日均学习时长: {hours} 小时\n\n"
                f"课程材料片段:\n{context}\n\n"
                "请生成倒计时复习计划：\n"
                "- 按周/按天安排\n"
                "- 每日任务可执行\n"
                "- 包含阶段性自测点\n"
                "- 最后 3 天冲刺策略"
            ),
            provider="kimi",
            system_prompt="你是学习规划顾问，计划要现实、可执行。",
            temperature=0.3,
            max_tokens=4096,
        )
        return f"🗓️ 复习计划 ({subject})\n{result}"
    except Exception as e:
        return f"❌ 复习计划生成失败: {e}"
