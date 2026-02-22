# skills/rag_tools.py
# 向量检索记忆 (RAG) - 基于 chromadb 的语义搜索记忆系统

import os
from .registry import register

CHROMA_DIR = "memories/chroma_db"
_collection = None
_collection_error = None


def _get_collection():
    """Lazy-init Chroma collection; return (collection, error_message)."""
    global _collection, _collection_error

    if _collection is not None:
        return _collection, None
    if _collection_error:
        return None, _collection_error

    try:
        import chromadb

        if not os.path.exists(CHROMA_DIR):
            os.makedirs(CHROMA_DIR)

        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}
        )
        return _collection, None
    except ImportError:
        _collection_error = "❌ 语义记忆不可用：缺少 chromadb。请安装: pip install chromadb"
        return None, _collection_error
    except Exception as e:
        _collection_error = f"❌ 语义记忆初始化失败: {e}"
        return None, _collection_error

# ==========================================
# 1. 语义存储记忆
# ==========================================
rag_save_schema = {
    "type": "function",
    "function": {
        "name": "rag_save",
        "description": (
            "将信息存入语义记忆库。适合保存项目笔记、用户偏好、技术文档片段等。"
            "存入后可通过 rag_search 按语义相似度检索，无需记住精确的关键词。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要记忆的内容"
                },
                "tags": {
                    "type": "string",
                    "description": "标签，用逗号分隔 (如 'python,bug修复,项目A')"
                }
            },
            "required": ["content"]
        }
    }
}


@register(rag_save_schema)
def rag_save(content: str, tags: str = ""):
    """存入语义记忆"""
    try:
        collection, err = _get_collection()
        if err:
            return err

        import time
        doc_id = f"mem_{int(time.time() * 1000)}"
        metadata = {"tags": tags, "timestamp": str(int(time.time()))}

        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )

        count = collection.count()
        return f"✅ 已存入语义记忆库 (ID: {doc_id})。当前共 {count} 条记忆。"
    except Exception as e:
        return f"❌ 语义记忆保存失败: {e}"


# ==========================================
# 2. 语义搜索记忆
# ==========================================
rag_search_schema = {
    "type": "function",
    "function": {
        "name": "rag_search",
        "description": (
            "按语义相似度搜索记忆库。输入自然语言查询，返回最相关的记忆。"
            "当你需要回忆之前保存的信息但不确定精确关键词时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询 (自然语言)"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回最相关的记忆条数，默认 5"
                }
            },
            "required": ["query"]
        }
    }
}


@register(rag_search_schema)
def rag_search(query: str, top_k: int = 5):
    """语义搜索记忆"""
    try:
        collection, err = _get_collection()
        if err:
            return err

        top_k = int(top_k) if top_k else 5
        top_k = max(1, min(top_k, 20))

        count = collection.count()
        if count == 0:
            return "📭 记忆库为空，尚无可搜索的内容。"

        # 限制 top_k 不超过实际数量
        actual_k = min(top_k, count)

        results = collection.query(
            query_texts=[query],
            n_results=actual_k
        )

        if not results['documents'] or not results['documents'][0]:
            return f"❌ 未找到与 '{query}' 相关的记忆。"

        lines = [f"🔍 搜索: '{query}' (共 {count} 条记忆中找到 {len(results['documents'][0])} 条相关):\n"]
        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            similarity = max(0, 1 - dist)  # cosine distance -> similarity
            tags = meta.get('tags', '')
            tag_str = f" [{tags}]" if tags else ""
            lines.append(f"  {i+1}. ({similarity:.0%}){tag_str} {doc}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ 语义搜索失败: {e}"


# ==========================================
# 3. 查看记忆库状态
# ==========================================
rag_status_schema = {
    "type": "function",
    "function": {
        "name": "rag_status",
        "description": "查看语义记忆库的状态和统计信息。",
        "parameters": {"type": "object", "properties": {}}
    }
}


@register(rag_status_schema)
def rag_status():
    """查看记忆库状态"""
    try:
        collection, err = _get_collection()
        if err:
            return err

        count = collection.count()
        return f"📊 语义记忆库状态:\n  总记忆数: {count}\n  存储位置: {CHROMA_DIR}"
    except Exception as e:
        return f"❌ 获取状态失败: {e}"
