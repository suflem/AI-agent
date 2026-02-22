# skills/grad_school_tools.py
# 研究生择校工具：资料录入、检索落库、多校对比

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from .registry import register
from .path_safety import guard_path, WORKSPACE_ROOT


GRAD_DIR = "data/grad_school"
PROFILES_FILE = "profiles.json"
PROFILE_DOCS_DIR = "profiles_docs"
WEB_CACHE_DIR = "web_cache"


def _display_path(path_obj: Path):
    try:
        return str(path_obj.relative_to(WORKSPACE_ROOT))
    except Exception:
        return str(path_obj)


def _ensure_grad_dir():
    grad_obj, err = guard_path(GRAD_DIR, must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    if not grad_obj.exists():
        grad_obj.mkdir(parents=True, exist_ok=True)
    return grad_obj


def _grad_file(filename: str):
    grad_obj = _ensure_grad_dir()
    path_obj, err = guard_path(str(grad_obj / filename), must_exist=False, for_write=True)
    if err:
        raise ValueError(err)
    return path_obj


def _load_profiles():
    file_obj = _grad_file(PROFILES_FILE)
    if file_obj.exists():
        with open(file_obj, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def _save_profiles(items):
    file_obj = _grad_file(PROFILES_FILE)
    with open(file_obj, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _parse_json_object(text: str):
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {"raw_text": raw}
    except Exception:
        return {"raw_text": raw}


def _slugify(text: str):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (text or "").strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64] or "item"


def _ensure_subdir(name: str):
    grad_obj = _ensure_grad_dir()
    sub_obj = grad_obj / name
    if not sub_obj.exists():
        sub_obj.mkdir(parents=True, exist_ok=True)
    return sub_obj


def _profile_key(school: str, program: str):
    return f"{(school or '').strip().lower()}::{(program or '').strip().lower()}"


def _clamp_score(value, low=0.0, high=100.0):
    try:
        x = float(value)
    except Exception:
        x = 0.0
    if x < low:
        return low
    if x > high:
        return high
    return x


def _to_float(value, default=None):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return default
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return default
    try:
        return float(m.group(0))
    except Exception:
        return default


def _parse_date(value: str):
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    fmts = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y%m%d",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y.%m.%d %H:%M",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass

    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(y, mo, d)
        except Exception:
            return None
    return None


def _extract_deadline(profile: dict):
    info = profile.get("info", {}) if isinstance(profile.get("info", {}), dict) else {}
    candidates = [
        info.get("application_deadline"),
        info.get("deadline"),
        info.get("ddl"),
        info.get("deadline_date"),
    ]
    if isinstance(info.get("deadlines"), dict):
        dct = info.get("deadlines", {})
        candidates.extend([
            dct.get("application"),
            dct.get("final"),
            dct.get("priority"),
        ])
    for item in candidates:
        dt = _parse_date(item)
        if dt:
            return dt
    return None


def _filter_profiles(profiles, schools: str, program: str):
    selected = profiles
    target_schools = [x.strip() for x in (schools or "").split(",") if x.strip()]
    if target_schools:
        keyset = {x.lower() for x in target_schools}
        selected = [p for p in selected if p.get("school", "").strip().lower() in keyset]
    if program:
        pkey = program.strip().lower()
        selected = [p for p in selected if p.get("program", "").strip().lower() == pkey]
    return selected


def _normalize_weights(weights_obj):
    default_weights = {
        "research_fit": 0.35,
        "admission_feasibility": 0.25,
        "cost_funding": 0.2,
        "location_career": 0.2,
    }
    if not isinstance(weights_obj, dict) or not weights_obj:
        return default_weights

    cleaned = {}
    for k, v in weights_obj.items():
        if k not in default_weights:
            continue
        fv = _to_float(v, None)
        if fv is None or fv < 0:
            continue
        cleaned[k] = fv
    if not cleaned:
        return default_weights

    total = sum(cleaned.values())
    if total <= 0:
        return default_weights
    return {k: v / total for k, v in cleaned.items()}


def _keyword_set(value):
    if isinstance(value, list):
        raw = " ".join([str(x) for x in value])
    elif isinstance(value, dict):
        raw = " ".join([str(v) for v in value.values()])
    else:
        raw = str(value or "")
    parts = re.split(r"[,;/|\s]+", raw.lower())
    return {p.strip() for p in parts if p.strip()}


def _score_research_fit(profile: dict, user_profile: dict):
    info = profile.get("info", {}) if isinstance(profile.get("info", {}), dict) else {}
    explicit = (
        _to_float(info.get("research_fit_score"), None)
        or _to_float((info.get("scores", {}) or {}).get("research_fit"), None)
    )
    if explicit is not None:
        return _clamp_score(explicit)

    school_text = " ".join([
        str(profile.get("program", "")),
        str(info.get("research_areas", "")),
        str(info.get("faculty_interests", "")),
        str(info.get("lab_keywords", "")),
    ])
    user_text = " ".join([
        str(user_profile.get("target_interest", "")),
        str(user_profile.get("research_interests", "")),
        str(user_profile.get("keywords", "")),
    ])
    a = _keyword_set(school_text)
    b = _keyword_set(user_text)
    if not a or not b:
        return 60.0
    overlap = len(a.intersection(b))
    return _clamp_score(50 + overlap * 12)


def _score_admission(profile: dict, user_profile: dict):
    info = profile.get("info", {}) if isinstance(profile.get("info", {}), dict) else {}
    explicit = (
        _to_float(info.get("admission_feasibility_score"), None)
        or _to_float((info.get("scores", {}) or {}).get("admission_feasibility"), None)
    )
    if explicit is not None:
        return _clamp_score(explicit)

    score = 60.0
    ugpa = _to_float(user_profile.get("gpa"), None)
    rgpa = _to_float(info.get("min_gpa"), None)
    if rgpa is None:
        rgpa = _to_float(info.get("required_gpa"), None)
    if ugpa is not None and rgpa is not None:
        score += (ugpa - rgpa) * 25

    ugre = _to_float(user_profile.get("gre"), None)
    rgre = _to_float(info.get("min_gre"), None)
    if rgre is None:
        rgre = _to_float(info.get("required_gre"), None)
    if ugre is not None and rgre is not None:
        score += (ugre - rgre) / 2.5

    accept_rate = _to_float(info.get("acceptance_rate"), None)
    if accept_rate is not None:
        if accept_rate <= 1:
            accept_rate *= 100
        score += (accept_rate - 20) * 0.4

    return _clamp_score(score)


def _score_cost(profile: dict, user_profile: dict):
    info = profile.get("info", {}) if isinstance(profile.get("info", {}), dict) else {}
    explicit = (
        _to_float(info.get("cost_funding_score"), None)
        or _to_float((info.get("scores", {}) or {}).get("cost_funding"), None)
    )
    if explicit is not None:
        return _clamp_score(explicit)

    tuition = (
        _to_float(info.get("tuition_usd"), None)
        or _to_float(info.get("tuition"), None)
        or _to_float(info.get("per_year_tuition"), None)
    )
    funding = _to_float(info.get("funding_rate"), None)
    budget = _to_float(user_profile.get("budget_usd"), None)

    score = 65.0
    if tuition is not None:
        score = 100 - tuition / 900
    if budget is not None and tuition is not None:
        score += (budget - tuition) / 1500
    if funding is not None:
        if funding <= 1:
            funding *= 100
        score += (funding - 25) * 0.3
    return _clamp_score(score)


def _score_location(profile: dict, user_profile: dict):
    info = profile.get("info", {}) if isinstance(profile.get("info", {}), dict) else {}
    explicit = (
        _to_float(info.get("location_career_score"), None)
        or _to_float((info.get("scores", {}) or {}).get("location_career"), None)
    )
    if explicit is not None:
        return _clamp_score(explicit)

    pref = _keyword_set(user_profile.get("preferred_locations", ""))
    career = _keyword_set(user_profile.get("career_goal", ""))
    loc_text = " ".join([
        str(info.get("location", "")),
        str(info.get("city", "")),
        str(info.get("country", "")),
        str(info.get("career_outcomes", "")),
    ])
    pset = _keyword_set(loc_text)

    score = 60.0
    if pref and pset:
        score += len(pref.intersection(pset)) * 12
    if career and pset:
        score += len(career.intersection(pset)) * 8
    return _clamp_score(score)


def _tier_by_admission(admission_score: float):
    if admission_score < 45:
        return "冲刺"
    if admission_score < 70:
        return "匹配"
    return "保底"


grad_school_manage_schema = {
    "type": "function",
    "function": {
        "name": "grad_school_manage",
        "description": (
            "管理研究生择校资料。支持录入/更新学校档案、查看列表、删除、导出到知识库文档源。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: upsert/get/list/remove/build_kb_source"
                },
                "school": {"type": "string", "description": "学校名称"},
                "program": {"type": "string", "description": "项目/专业名称"},
                "intake": {"type": "string", "description": "申请学期，如 2027 Fall"},
                "info_json": {"type": "string", "description": "补充信息(JSON对象或纯文本)"},
                "top_n": {"type": "integer", "description": "list 时返回条数，默认 20"}
            },
            "required": ["action"]
        }
    }
}


@register(grad_school_manage_schema)
def grad_school_manage(
    action: str,
    school: str = "",
    program: str = "",
    intake: str = "",
    info_json: str = "",
    top_n: int = 20,
):
    try:
        action = (action or "").strip().lower()
        profiles = _load_profiles()

        if action == "list":
            if not profiles:
                return "🎓 暂无择校档案"
            top_n = max(1, min(int(top_n) if top_n else 20, 100))
            lines = [f"🎓 择校档案 ({len(profiles)} 条):\n"]
            for idx, p in enumerate(profiles[:top_n], 1):
                lines.append(
                    f"  {idx}. {p.get('school', '?')} | {p.get('program', '?')} | {p.get('intake', '-')}"
                )
                lines.append(f"     更新: {p.get('updated_at', '-')}")
            return "\n".join(lines)

        if action == "get":
            if not school:
                return "❌ get 需要 school"
            key = _profile_key(school, program)
            candidates = [p for p in profiles if _profile_key(p.get("school", ""), p.get("program", "")) == key]
            if not candidates:
                # program 为空时允许按 school 模糊取第一条
                if not program:
                    candidates = [p for p in profiles if p.get("school", "").strip().lower() == school.strip().lower()]
            if not candidates:
                return f"❌ 未找到档案: {school} / {program or '*'}"
            return "🎓 档案详情:\n" + json.dumps(candidates[0], ensure_ascii=False, indent=2)

        if action == "remove":
            if not school:
                return "❌ remove 需要 school"
            before = len(profiles)
            if program:
                key = _profile_key(school, program)
                profiles = [p for p in profiles if _profile_key(p.get("school", ""), p.get("program", "")) != key]
            else:
                s = school.strip().lower()
                profiles = [p for p in profiles if p.get("school", "").strip().lower() != s]
            if len(profiles) == before:
                return "❌ 未删除任何档案（未匹配）"
            _save_profiles(profiles)
            return f"✅ 已删除 {before - len(profiles)} 条档案"

        if action == "upsert":
            if not school or not program:
                return "❌ upsert 需要 school 和 program"
            ext_info = _parse_json_object(info_json)
            key = _profile_key(school, program)

            updated = False
            now_str = time.strftime("%Y-%m-%d %H:%M")
            for p in profiles:
                if _profile_key(p.get("school", ""), p.get("program", "")) == key:
                    p["intake"] = intake or p.get("intake", "")
                    p["info"] = ext_info or p.get("info", {})
                    p["updated_at"] = now_str
                    updated = True
                    break
            if not updated:
                profiles.append({
                    "school": school.strip(),
                    "program": program.strip(),
                    "intake": (intake or "").strip(),
                    "info": ext_info,
                    "created_at": now_str,
                    "updated_at": now_str,
                })
            _save_profiles(profiles)
            return f"✅ 已{'更新' if updated else '新增'}档案: {school} / {program}"

        if action == "build_kb_source":
            docs_dir = _ensure_subdir(PROFILE_DOCS_DIR)
            if not profiles:
                return "❌ 没有可导出的档案"

            written = 0
            for p in profiles:
                school_name = p.get("school", "")
                program_name = p.get("program", "")
                filename = f"{_slugify(school_name)}__{_slugify(program_name)}.md"
                fpath = docs_dir / filename
                md = [
                    f"# {school_name} - {program_name}",
                    "",
                    f"- intake: {p.get('intake', '')}",
                    f"- updated_at: {p.get('updated_at', '')}",
                    "",
                    "## profile_info",
                    "```json",
                    json.dumps(p.get("info", {}), ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(md))
                written += 1

            return (
                f"✅ 已导出 {written} 份择校资料文档\n"
                f"📁 路径: {_display_path(docs_dir)}\n"
                "💡 下一步可用 kb_build(kb_name='grad_school_kb', source_path='data/grad_school/profiles_docs')"
            )

        return "❌ 未知 action。支持: upsert/get/list/remove/build_kb_source"
    except Exception as e:
        return f"❌ 择校资料管理失败: {e}"


grad_school_research_schema = {
    "type": "function",
    "function": {
        "name": "grad_school_research",
        "description": (
            "联网搜索院校/专业信息，抓取网页后存入本地缓存，并可一键构建/更新择校知识库。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最多抓取结果数，默认 5"},
                "kb_name": {"type": "string", "description": "落地知识库名称，默认 grad_school_kb"},
                "build_kb": {"type": "boolean", "description": "是否自动构建知识库，默认 true"},
                "fetch_chars": {"type": "integer", "description": "单页抓取字符数，默认 8000"}
            },
            "required": ["query"]
        }
    }
}


@register(grad_school_research_schema)
def grad_school_research(
    query: str,
    max_results: int = 5,
    kb_name: str = "grad_school_kb",
    build_kb: bool = True,
    fetch_chars: int = 8000,
):
    try:
        from .web_tools import web_search, fetch_url
        from .knowledge_tools import kb_build

        max_results = max(1, min(int(max_results) if max_results else 5, 10))
        fetch_chars = max(2000, min(int(fetch_chars) if fetch_chars else 8000, 20000))

        raw_search = web_search(query=query, num_results=max_results)
        if not isinstance(raw_search, str):
            return "❌ 搜索失败: web_search 返回了非文本结果"
        if raw_search.startswith("❌"):
            return raw_search

        urls = re.findall(r"https?://[^\s)]+", raw_search)
        dedup_urls = []
        seen = set()
        for u in urls:
            if u not in seen:
                dedup_urls.append(u)
                seen.add(u)
        dedup_urls = dedup_urls[:max_results]
        if not dedup_urls:
            return f"⚠️ 搜索结果中未解析到可抓取链接\n{raw_search}"

        cache_dir = _ensure_subdir(WEB_CACHE_DIR)
        saved = 0
        failed = []
        ts = int(time.time())
        for idx, url in enumerate(dedup_urls, 1):
            fetched = fetch_url(url=url, max_length=fetch_chars)
            if not isinstance(fetched, str) or fetched.startswith("❌"):
                failed.append(f"{url} -> {fetched}")
                continue
            fname = f"{ts}_{idx}_{_slugify(query)[:32]}.md"
            fpath = cache_dir / fname
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# query: {query}\n\nsource: {url}\n\n{fetched}\n")
            saved += 1

        lines = [
            f"🔎 择校联网检索完成: {query}",
            f"  解析链接: {len(dedup_urls)}",
            f"  成功缓存: {saved}",
            f"  失败: {len(failed)}",
            f"  缓存目录: {_display_path(cache_dir)}",
        ]

        if build_kb and saved > 0:
            build_result = kb_build(
                kb_name=kb_name,
                source_path=str(cache_dir),
                file_pattern="*.md",
                chunk_size=700,
            )
            lines.append("")
            lines.append("📚 知识库更新结果:")
            lines.append(str(build_result))

        if failed:
            lines.append("")
            lines.append("⚠️ 失败样例:")
            lines.extend([f"  - {x}" for x in failed[:5]])

        return "\n".join(lines)
    except Exception as e:
        return f"❌ 择校联网检索失败: {e}"


grad_school_compare_schema = {
    "type": "function",
    "function": {
        "name": "grad_school_compare",
        "description": (
            "对多所学校/项目进行结构化对比，输出优先级建议和选校理由。"
            "可结合本地档案与择校知识库。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "schools": {"type": "string", "description": "学校名列表，逗号分隔；留空表示全部档案"},
                "program": {"type": "string", "description": "限定专业（可选）"},
                "criteria_weights": {
                    "type": "string",
                    "description": "权重 JSON，如 {\"research_fit\":0.35,\"admission\":0.25,\"cost\":0.2,\"location\":0.2}"
                },
                "kb_name": {"type": "string", "description": "可选知识库名称（如 grad_school_kb）"},
                "top_k": {"type": "integer", "description": "每校检索片段数，默认 4"}
            },
            "required": []
        }
    }
}


@register(grad_school_compare_schema)
def grad_school_compare(
    schools: str = "",
    program: str = "",
    criteria_weights: str = "",
    kb_name: str = "",
    top_k: int = 4,
):
    try:
        from .external_ai import call_ai
        from .knowledge_tools import kb_query

        profiles = _load_profiles()
        if not profiles:
            return "❌ 没有可对比的择校档案，请先 grad_school_manage(action='upsert') 录入。"

        selected = _filter_profiles(profiles, schools=schools, program=program)

        if len(selected) < 2:
            return "❌ 至少需要 2 个项目进行对比（当前不足）。"

        top_k = max(2, min(int(top_k) if top_k else 4, 10))
        weights = _normalize_weights(_parse_json_object(criteria_weights))

        kb_context = {}
        if kb_name:
            for p in selected:
                sname = p.get("school", "")
                pname = p.get("program", "")
                q = f"{sname} {pname} admission requirement tuition scholarship faculty research"
                kb_context[f"{sname}::{pname}"] = kb_query(kb_name=kb_name, query=q, top_k=top_k)

        prompt_payload = {
            "profiles": selected,
            "criteria_weights": weights,
            "kb_context": kb_context,
        }

        result = call_ai(
            prompt=(
                "请对以下研究生申请选项做结构化对比。\n"
                "输出格式：\n"
                "1) 对比总览表（每校每维度简评）\n"
                "2) 排名与分层（冲刺/匹配/保底）\n"
                "3) 每个选项的核心风险\n"
                "4) 最终建议（含下一步行动清单）\n\n"
                f"输入数据:\n{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
            ),
            provider="kimi",
            system_prompt=(
                "你是研究生申请顾问。必须依据输入材料，不编造录取率和奖学金。"
                "信息不足要直接标注“待补充”。"
            ),
            temperature=0.3,
            max_tokens=4096,
        )
        return f"🏫 择校对比结果\n{result}"
    except Exception as e:
        return f"❌ 择校对比失败: {e}"


grad_school_scorecard_schema = {
    "type": "function",
    "function": {
        "name": "grad_school_scorecard",
        "description": (
            "基于可配置权重生成择校量化评分卡，并给出冲刺/匹配/保底分层。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "schools": {"type": "string", "description": "学校名列表，逗号分隔；留空表示全部档案"},
                "program": {"type": "string", "description": "限定专业（可选）"},
                "user_profile_json": {
                    "type": "string",
                    "description": "用户画像 JSON，如 GPA/GRE/预算/研究兴趣/城市偏好"
                },
                "criteria_weights": {
                    "type": "string",
                    "description": "权重 JSON，如 {\"research_fit\":0.35,\"admission_feasibility\":0.3,\"cost_funding\":0.2,\"location_career\":0.15}"
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序字段: total/research_fit/admission_feasibility/cost_funding/location_career"
                },
                "top_n": {"type": "integer", "description": "最多返回条目数，默认 20"}
            },
            "required": []
        }
    }
}


@register(grad_school_scorecard_schema)
def grad_school_scorecard(
    schools: str = "",
    program: str = "",
    user_profile_json: str = "",
    criteria_weights: str = "",
    sort_by: str = "total",
    top_n: int = 20,
):
    try:
        profiles = _load_profiles()
        if not profiles:
            return "❌ 没有可评分档案，请先 grad_school_manage(action='upsert') 录入。"

        selected = _filter_profiles(profiles, schools=schools, program=program)
        if not selected:
            return "❌ 未筛选到可评分档案"

        user_profile = _parse_json_object(user_profile_json)
        weights = _normalize_weights(_parse_json_object(criteria_weights))
        top_n = max(1, min(int(top_n) if top_n else 20, 100))

        rows = []
        for p in selected:
            s_research = _score_research_fit(p, user_profile)
            s_adm = _score_admission(p, user_profile)
            s_cost = _score_cost(p, user_profile)
            s_loc = _score_location(p, user_profile)
            details = {
                "research_fit": s_research,
                "admission_feasibility": s_adm,
                "cost_funding": s_cost,
                "location_career": s_loc,
            }
            total = 0.0
            for k, w in weights.items():
                total += details.get(k, 0.0) * w

            rows.append({
                "school": p.get("school", ""),
                "program": p.get("program", ""),
                "total": round(total, 1),
                "research_fit": round(s_research, 1),
                "admission_feasibility": round(s_adm, 1),
                "cost_funding": round(s_cost, 1),
                "location_career": round(s_loc, 1),
                "tier": _tier_by_admission(s_adm),
            })

        sort_key = (sort_by or "total").strip()
        if sort_key not in {
            "total", "research_fit", "admission_feasibility", "cost_funding", "location_career"
        }:
            sort_key = "total"
        rows.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
        rows = rows[:top_n]

        lines = [
            f"📊 择校评分卡（共 {len(rows)} 条，按 {sort_key} 排序）",
            f"权重: {json.dumps(weights, ensure_ascii=False)}",
            "",
            "学校 | 项目 | 总分 | 研究匹配 | 录取可行性 | 成本资助 | 区位就业 | 分层",
            "---|---|---:|---:|---:|---:|---:|---",
        ]
        for r in rows:
            lines.append(
                f"{r['school']} | {r['program']} | {r['total']:.1f} | "
                f"{r['research_fit']:.1f} | {r['admission_feasibility']:.1f} | "
                f"{r['cost_funding']:.1f} | {r['location_career']:.1f} | {r['tier']}"
            )

        lines.append("")
        lines.append("分层规则: admission_feasibility <45=冲刺, 45-69.9=匹配, >=70=保底")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 评分卡生成失败: {e}"


grad_application_timeline_schema = {
    "type": "function",
    "function": {
        "name": "grad_application_timeline",
        "description": (
            "基于档案截止时间生成申请时间线，可选写入提醒事项。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "schools": {"type": "string", "description": "学校名列表，逗号分隔；留空表示全部档案"},
                "program": {"type": "string", "description": "限定专业（可选）"},
                "start_date": {"type": "string", "description": "起始日期，格式 YYYY-MM-DD，默认今天"},
                "target_deadline": {"type": "string", "description": "手动指定最早申请截止日期（可选）"},
                "create_reminders": {"type": "boolean", "description": "是否写入提醒，默认 false"},
                "reminder_time": {"type": "string", "description": "提醒时间，格式 HH:MM，默认 09:00"}
            },
            "required": []
        }
    }
}


@register(grad_application_timeline_schema)
def grad_application_timeline(
    schools: str = "",
    program: str = "",
    start_date: str = "",
    target_deadline: str = "",
    create_reminders: bool = False,
    reminder_time: str = "09:00",
):
    try:
        profiles = _load_profiles()
        if not profiles:
            return "❌ 没有档案数据，请先录入择校档案。"

        selected = _filter_profiles(profiles, schools=schools, program=program)
        if not selected:
            return "❌ 未筛选到任何档案。"

        start_dt = _parse_date(start_date) if start_date else datetime.now()
        if not start_dt:
            return "❌ start_date 格式错误，示例: 2026-02-17"

        deadlines = []
        manual_deadline = _parse_date(target_deadline) if target_deadline else None
        if manual_deadline:
            deadlines.append(("手动指定", manual_deadline))

        for p in selected:
            dt = _extract_deadline(p)
            if dt:
                tag = f"{p.get('school', '?')} - {p.get('program', '?')}"
                deadlines.append((tag, dt))

        if not deadlines:
            return (
                "❌ 未发现可用 deadline。请在档案 info_json 中补充 application_deadline/deadline，"
                "或传入 target_deadline。"
            )

        deadlines.sort(key=lambda x: x[1])
        final_deadline = deadlines[0][1]
        if final_deadline < start_dt:
            return f"❌ 截止日期 {final_deadline.strftime('%Y-%m-%d')} 早于起始日期"

        reminder_time = (reminder_time or "09:00").strip()
        if not re.fullmatch(r"\d{2}:\d{2}", reminder_time):
            return "❌ reminder_time 格式错误，示例: 09:00"

        milestones = [
            (180, "申请定位定稿：确定冲刺/匹配/保底名单，检查硬性要求"),
            (120, "完成考试与背景材料准备：标化、成绩单、科研/实习证明"),
            (90, "完成 PS/SOP 与简历初稿，确认推荐人并沟通推荐时间"),
            (60, "完成网申材料二轮打磨：文书、推荐信信息、补充问题"),
            (30, "提交前终审：格式、逻辑、证明文件、缴费与系统状态"),
            (14, "完成主要项目提交并准备面试问答（研究动机/项目经历）"),
            (7, "查漏补缺：确认提交回执、补件状态、面试时间安排"),
        ]

        lines = [
            "🗓️ 申请时间线",
            f"起始日期: {start_dt.strftime('%Y-%m-%d')}",
            f"关键截止: {final_deadline.strftime('%Y-%m-%d')}",
            f"总计时长: {(final_deadline - start_dt).days} 天",
            "",
            "各项目截止时间：",
        ]
        for tag, dt in deadlines[:20]:
            lines.append(f"- {tag}: {dt.strftime('%Y-%m-%d')}")

        lines.append("")
        lines.append("里程碑计划：")

        reminder_payloads = []
        for days_before, task in milestones:
            d = final_deadline - timedelta(days=days_before)
            if d < start_dt:
                continue
            dstr = d.strftime("%Y-%m-%d")
            lines.append(f"- {dstr}: {task}")
            reminder_payloads.append((dstr, task))

        # Always include final deadline reminder.
        final_str = final_deadline.strftime("%Y-%m-%d")
        final_task = "最终提交截止日：确认所有申请状态为已提交"
        lines.append(f"- {final_str}: {final_task}")
        reminder_payloads.append((final_str, final_task))

        if create_reminders and reminder_payloads:
            from .daily_tools import reminder_manage

            ok = 0
            errs = []
            for dstr, task in reminder_payloads:
                resp = reminder_manage(
                    action="add",
                    content=f"[申请时间线] {task}",
                    remind_time=f"{dstr} {reminder_time}",
                )
                if isinstance(resp, str) and resp.startswith("✅"):
                    ok += 1
                else:
                    errs.append(str(resp))

            lines.append("")
            lines.append(f"提醒写入: {ok}/{len(reminder_payloads)}")
            if errs:
                lines.append("提醒异常样例:")
                lines.extend([f"- {e}" for e in errs[:5]])

        return "\n".join(lines)
    except Exception as e:
        return f"❌ 申请时间线生成失败: {e}"
