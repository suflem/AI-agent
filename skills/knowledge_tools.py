# skills/knowledge_tools.py
# 知识库工具：从文件/目录/网页构建结构化知识库，支持语义检索

import os
import json
import time
import hashlib
import re
from .registry import register
from .path_safety import guard_path

KB_DIR = "data/knowledge_base"


def _normalize_kb_name(kb_name: str):
    name = (kb_name or "").strip()
    if not name:
        return None, "❌ 知识库名称不能为空"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        return None, "❌ 知识库名称只允许字母、数字、下划线和短横线，长度 1-64"
    return name, None


def _ensure_kb_dir():
    if not os.path.exists(KB_DIR):
        os.makedirs(KB_DIR)


# ==========================================
# 1. 构建知识库
# ==========================================
kb_build_schema = {
    "type": "function",
    "function": {
        "name": "kb_build",
        "description": (
            "从文件或目录构建知识库。自动读取文本文件、PDF、Markdown，"
            "将内容分块后存入向量数据库 (chromadb) 以支持语义搜索。"
            "每个知识库有独立的名称和存储空间。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kb_name": {"type": "string", "description": "知识库名称 (英文，如 'python_docs')"},
                "source_path": {"type": "string", "description": "源文件或目录路径"},
                "file_pattern": {"type": "string", "description": "文件过滤 (glob 模式，如 '*.md')，默认所有文本文件"},
                "chunk_size": {"type": "integer", "description": "分块大小 (字符数)，默认 500"}
            },
            "required": ["kb_name", "source_path"]
        }
    }
}


TEXT_EXTS = {'.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml',
             '.html', '.css', '.csv', '.xml', '.rst', '.ini', '.cfg', '.toml',
             '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb', '.php', '.sql'}


def _chunk_text(text: str, chunk_size: int = 500) -> list:
    """将文本分块"""
    chunks = []
    paragraphs = text.split('\n\n')
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current += ("\n\n" if current else "") + para

    if current.strip():
        chunks.append(current.strip())

    # 对超大块再次分割
    final = []
    for chunk in chunks:
        while len(chunk) > chunk_size * 2:
            split_pos = chunk.rfind('\n', 0, chunk_size)
            if split_pos == -1:
                split_pos = chunk_size
            final.append(chunk[:split_pos].strip())
            chunk = chunk[split_pos:].strip()
        if chunk:
            final.append(chunk)

    return final


@register(kb_build_schema)
def kb_build(kb_name: str, source_path: str, file_pattern: str = "", chunk_size: int = 500):
    """构建知识库"""
    try:
        import chromadb
        import fnmatch

        _ensure_kb_dir()
        chunk_size = max(200, min(int(chunk_size) if chunk_size else 500, 2000))

        kb_name, kb_name_err = _normalize_kb_name(kb_name)
        if kb_name_err:
            return kb_name_err
        kb_path = os.path.join(KB_DIR, kb_name)

        source_obj, err = guard_path(source_path, must_exist=True, for_write=False)
        if err:
            return err

        client = chromadb.PersistentClient(path=kb_path)
        collection = client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

        # 收集要处理的文件
        files = []
        if source_obj.is_file():
            files = [str(source_obj)]
        elif source_obj.is_dir():
            for root, dirs, fnames in os.walk(source_obj):
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'venv', 'node_modules'}]
                for fname in fnames:
                    if file_pattern and not fnmatch.fnmatch(fname, file_pattern):
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if not file_pattern and ext not in TEXT_EXTS:
                        continue
                    files.append(os.path.join(root, fname))
        else:
            return f"❌ 路径不存在: {source_obj}"

        if not files:
            return f"⚠️ 未找到匹配的文件"

        total_chunks = 0
        processed_files = 0
        replaced_chunks = 0
        failed_files = 0

        for filepath in files:
            try:
                source_abs = os.path.abspath(filepath)

                # PDF 特殊处理
                if source_abs.lower().endswith('.pdf'):
                    try:
                        import PyPDF2
                        with open(source_abs, 'rb') as f:
                            reader = PyPDF2.PdfReader(f)
                            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                    except ImportError:
                        continue
                else:
                    with open(source_abs, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()

                if not text.strip():
                    continue

                chunks = _chunk_text(text, chunk_size)

                ids = []
                documents = []
                metadatas = []

                source_id = hashlib.sha1(source_abs.encode('utf-8')).hexdigest()[:16]

                # 先删除该来源旧数据，避免重复/冲突堆积
                old = collection.get(where={"source": source_abs}, include=[])
                old_ids = old.get("ids", []) if isinstance(old, dict) else []
                if old_ids:
                    collection.delete(ids=old_ids)
                    replaced_chunks += len(old_ids)

                for i, chunk in enumerate(chunks):
                    chunk_hash = hashlib.sha1(chunk.encode('utf-8')).hexdigest()[:12]
                    doc_id = f"{source_id}_{i}_{chunk_hash}"
                    ids.append(doc_id)
                    documents.append(chunk)
                    metadatas.append({
                        "source": source_abs,
                        "chunk_index": str(i),
                        "total_chunks": str(len(chunks))
                    })

                if documents:
                    collection.add(ids=ids, documents=documents, metadatas=metadatas)
                    total_chunks += len(documents)
                    processed_files += 1

            except Exception as e:
                failed_files += 1
                continue  # 跳过读取失败的文件

        return (
            f"✅ 知识库 '{kb_name}' 构建完成:\n"
            f"  处理文件: {processed_files}/{len(files)}\n"
            f"  替换旧块: {replaced_chunks}\n"
            f"  文档分块: {total_chunks}\n"
            f"  失败文件: {failed_files}\n"
            f"  存储位置: {kb_path}"
        )

    except ImportError:
        return "❌ 需要安装 chromadb: pip install chromadb"
    except Exception as e:
        return f"❌ 知识库构建失败: {e}"


# ==========================================
# 2. 查询知识库
# ==========================================
kb_query_schema = {
    "type": "function",
    "function": {
        "name": "kb_query",
        "description": (
            "在知识库中进行语义搜索。输入自然语言查询，返回最相关的文档片段。"
            "适合在已构建的知识库中查找特定信息。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kb_name": {"type": "string", "description": "知识库名称"},
                "query": {"type": "string", "description": "搜索查询 (自然语言)"},
                "top_k": {"type": "integer", "description": "返回最相关的条数，默认 5"}
            },
            "required": ["kb_name", "query"]
        }
    }
}


@register(kb_query_schema)
def kb_query(kb_name: str, query: str, top_k: int = 5):
    """查询知识库"""
    try:
        import chromadb

        kb_name, kb_name_err = _normalize_kb_name(kb_name)
        if kb_name_err:
            return kb_name_err

        kb_path = os.path.join(KB_DIR, kb_name)
        if not os.path.exists(kb_path):
            return f"❌ 知识库不存在: {kb_name}"

        top_k = max(1, min(int(top_k) if top_k else 5, 20))

        client = chromadb.PersistentClient(path=kb_path)
        collection = client.get_collection("documents")

        count = collection.count()
        actual_k = min(top_k, count)
        if actual_k == 0:
            return f"📭 知识库 '{kb_name}' 为空"

        results = collection.query(query_texts=[query], n_results=actual_k)

        if not results['documents'] or not results['documents'][0]:
            return f"🔍 未找到相关内容"

        lines = [f"🔍 知识库 '{kb_name}' 搜索结果 (共 {count} 个文档块):\n"]

        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            similarity = max(0, 1 - dist)
            source = meta.get('source', '未知')
            chunk_idx = meta.get('chunk_index', '?')
            preview = doc[:300] + "..." if len(doc) > 300 else doc
            lines.append(f"  [{i+1}] ({similarity:.0%}) 来源: {source} (块#{chunk_idx})")
            lines.append(f"      {preview}\n")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 知识库查询失败: {e}"


# ==========================================
# 3. 管理知识库
# ==========================================
kb_manage_schema = {
    "type": "function",
    "function": {
        "name": "kb_manage",
        "description": "管理知识库：列出所有知识库、查看状态、删除知识库。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: list(列出), status(查看状态), delete(删除)"},
                "kb_name": {"type": "string", "description": "知识库名称 (status/delete 时需要)"}
            },
            "required": ["action"]
        }
    }
}


@register(kb_manage_schema)
def kb_manage(action: str, kb_name: str = ""):
    try:
        _ensure_kb_dir()
        import chromadb

        if action == "list":
            entries = [d for d in os.listdir(KB_DIR)
                      if os.path.isdir(os.path.join(KB_DIR, d))]
            if not entries:
                return "📚 暂无知识库"

            lines = ["📚 知识库列表:\n"]
            for name in sorted(entries):
                try:
                    client = chromadb.PersistentClient(path=os.path.join(KB_DIR, name))
                    col = client.get_collection("documents")
                    count = col.count()
                    lines.append(f"  📁 {name} ({count} 个文档块)")
                except Exception:
                    lines.append(f"  📁 {name} (无法读取)")
            return "\n".join(lines)

        elif action == "status":
            kb_name, kb_name_err = _normalize_kb_name(kb_name)
            if kb_name_err:
                return kb_name_err
            kb_path = os.path.join(KB_DIR, kb_name)
            if not os.path.exists(kb_path):
                return f"❌ 知识库不存在: {kb_name}"

            client = chromadb.PersistentClient(path=kb_path)
            col = client.get_collection("documents")
            count = col.count()

            # 统计来源文件
            if count > 0:
                sample = col.get(limit=min(count, 100), include=["metadatas"])
                sources = set()
                for m in sample['metadatas']:
                    sources.add(m.get('source', '未知'))
                return (
                    f"📊 知识库 '{kb_name}':\n"
                    f"  文档块数: {count}\n"
                    f"  来源文件: {len(sources)}\n"
                    f"  存储路径: {kb_path}"
                )
            return f"📊 知识库 '{kb_name}': 空 (0 个文档块)"

        elif action == "delete":
            kb_name, kb_name_err = _normalize_kb_name(kb_name)
            if kb_name_err:
                return kb_name_err
            kb_path = os.path.join(KB_DIR, kb_name)
            if not os.path.exists(kb_path):
                return f"❌ 知识库不存在: {kb_name}"
            import shutil
            shutil.rmtree(kb_path)
            return f"✅ 已删除知识库: {kb_name}"

        else:
            return f"❌ 未知操作: {action}。支持: list, status, delete"

    except Exception as e:
        return f"❌ 知识库管理失败: {e}"
