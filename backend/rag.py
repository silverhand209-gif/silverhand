"""RAG 模块 - 剧本创作知识库检索"""
import json
import os
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Hugging Face 镜像（国内加速）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI

from config import settings

# 线程池用于 ChromaDB 操作
_executor = ThreadPoolExecutor(max_workers=4)

# 全局变量（延迟初始化）
_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None
_script_kb_collection = None
_llm_client: Optional[AsyncOpenAI] = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE
        )
    return _embedding_model


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client


def _get_script_collection():
    global _script_kb_collection
    if _script_kb_collection is None:
        client = _get_chroma_client()
        _script_kb_collection = client.get_or_create_collection(
            name="script_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
    return _script_kb_collection


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL
        )
    return _llm_client


# ============================================================
# 剧本知识库种子数据
# ============================================================
SCRIPT_KNOWLEDGE_SEEDS = [
    {
        "id": "kb_001",
        "category": "剧本结构",
        "title": "三幕剧结构",
        "content": """三幕剧结构是最经典的剧本叙事框架：
第一幕（开端/建置）：介绍主要角色、世界观和核心冲突。通常占剧本的25%。关键节点：引发事件（Inciting Incident）——打破主角日常的事件。
第二幕（对抗/发展）：主角面对越来越大的障碍，冲突升级。占剧本的50%。关键节点：中点转折（Midpoint）——局势发生重大变化；一无所有时刻（All is Lost）——主角跌入谷底。
第三幕（解决/结局）：冲突达到高潮并解决。占剧本的25%。关键节点：高潮（Climax）——最终对决；结局（Resolution）——新的平衡。"""
    },
    {
        "id": "kb_002",
        "category": "角色塑造",
        "title": "角色弧光设计",
        "content": """角色弧光（Character Arc）是角色在故事中的内在变化轨迹：
正向弧：角色从弱到强、从自私到无私的成长。如《肖申克的救赎》中的安迪。
负向弧：角色从好变坏或走向毁灭。如《教父》中的迈克尔·柯里昂。
平弧：角色本质不变但改变了周围世界。如《阿甘正传》中的阿甘。
设计要点：每个主要角色都应有明确的欲望（Want）和需要（Need），欲望驱动情节，需要决定弧光。"""
    },
    {
        "id": "kb_003",
        "category": "对白技巧",
        "title": "影视对白创作原则",
        "content": """优秀对白的核心原则：
1. 展示而非讲述：通过行动和对话暗示信息，避免角色直接解释背景
2. 潜台词：角色说的话往往不是真正的意思，对白之下有更深层含义
3. 差异化声音：每个角色有独特的词汇量、句长、节奏和口头禅
4. 冲突驱动：好的对白包含冲突——即使日常对话也有张力
5. 经济性：删除所有不必要的词，对白应简洁有力
6. 节奏变化：交替使用短句和长句，创造音乐感
7. 避免问答模式：不要让对话变成一问一答的采访"""
    },
    {
        "id": "kb_004",
        "category": "场景设计",
        "title": "场景写作要点",
        "content": """场景（Scene）是剧本的基本构建块：
每个场景必须有：明确的目标、冲突和变化。
场景类型：开场场景（定调）、转折场景（改变方向）、高潮场景（最大冲突）、情感场景（深化角色）、过场场景（过渡衔接）。
场景要素：地点描述（视觉化）、时间标注（日/夜）、出场角色、核心动作。
场景节奏：通过场景长度变化控制叙事节奏——短场景加速，长场景沉淀。
场景转场：切（CUT TO）、淡入（FADE IN）、淡出（FADE OUT）、叠化（DISSOLVE TO）、 smash cut（突然切）等。"""
    },
    {
        "id": "kb_005",
        "category": "改编技巧",
        "title": "小说转剧本改编要点",
        "content": """小说改编剧本的核心转换：
1. 内心独白→视觉行动：将小说中的心理描写转化为可视的动作、表情和对白
2. 叙述视角→镜头语言：全知叙述者转化为摄影机视角
3. 时间压缩：小说可细写数日，剧本需将时间压缩到关键场景
4. 角色合并：将功能重叠的配角合并，精简角色表
5. 情节取舍：保留核心冲突线，删减支线
6. 对白转化：将叙述性文字转化为自然对话，注意避免"信息倾泻"
7. 视觉化：每个场景都必须能用镜头呈现
8. 节奏重构：小说的章节节奏不等于剧本的场次节奏"""
    },
    {
        "id": "kb_006",
        "category": "格式规范",
        "title": "中文剧本格式标准",
        "content": """中文剧本标准格式要素：
1. 场景标题：场号. 场景地点 - 时间（日/夜）
2. 动作描述：第三人称现在时，描述可见的动作和环境
3. 角色名：对白上方居中标注说话角色
4. 对白：角色名下方，可包含括号指示（表演提示）
5. 转场：场景结尾标注转场方式
6. 独白/旁白：标注（独白）或（VO - Voice Over）
7. 镜头建议：一般不写，除非对叙事有特殊意义
8. 页码：每页约1分钟银幕时间"""
    },
    {
        "id": "kb_007",
        "category": "类型剧本",
        "title": "悬疑类型剧本特征",
        "content": """悬疑类型剧本的写作要点：
1. 信息控制：知道多少、何时揭示是关键
2. 红鲱鱼：设置合理的误导线索
3. 时间压力：加入倒计时或截止期限增加紧张感
4. 反转设计：每15-20页应有一个小反转
5. 视角限制：通常跟随侦探/主角视角
6. 线索分布：公平地散落线索，但巧妙地隐藏
7. 高潮设计：真相揭示应情感与逻辑并重"""
    },
    {
        "id": "kb_008",
        "category": "类型剧本",
        "title": "爱情类型剧本特征",
        "content": """爱情类型剧本的写作要点：
1. 相遇场景：设计独特有趣的初次见面
2. 障碍设置：内外障碍（阶级、性格、误会等）
3. 化学反应：通过小事展示两人默契
4. 中点转折：关系从轻松转向认真
5. 分离时刻：必要的分离/误会/危机
6. 成长弧光：双方各自成长后才能在一起
7. 结局类型：HE/BE/开放式，需符合整体调性"""
    },
]


def _sync_init_knowledge_base():
    """同步初始化知识库（在后台线程中运行）"""
    collection = _get_script_collection()

    # 检查是否已初始化
    existing = collection.get()
    if existing["ids"]:
        return  # 已初始化

    # 向量化种子数据
    model = _get_embedding_model()
    texts = [item["content"] for item in SCRIPT_KNOWLEDGE_SEEDS]
    ids = [item["id"] for item in SCRIPT_KNOWLEDGE_SEEDS]
    metadatas = [
        {"category": item["category"], "title": item["title"]}
        for item in SCRIPT_KNOWLEDGE_SEEDS
    ]

    embeddings = model.encode(texts).tolist()

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )
    return len(ids)


async def init_knowledge_base():
    """异步初始化知识库"""
    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(_executor, _sync_init_knowledge_base)
    if count:
        print(f"[RAG] 知识库已初始化，添加 {count} 条知识")
    else:
        print("[RAG] 知识库已存在，跳过初始化")


def _sync_search(query: str, top_k: int = 3) -> list[dict]:
    """同步检索"""
    collection = _get_script_collection()
    model = _get_embedding_model()

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )

    documents = []
    for i, doc_id in enumerate(results["ids"][0]):
        documents.append({
            "id": doc_id,
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else 0
        })
    return documents


async def search_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """异步检索剧本知识库"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_search, query, top_k)


async def query_rewrite_for_rag(stage: str, context_summary: str) -> list[str]:
    """使用 LLM 改写查询以优化检索"""
    from prompts import RAG_QUERY_REWRITE_PROMPT

    client = _get_llm_client()
    prompt = RAG_QUERY_REWRITE_PROMPT.format(
        stage=stage,
        context_summary=context_summary
    )

    try:
        response = await client.chat.completions.create(
            model=settings.LLM_SMALL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        content = response.choices[0].message.content.strip()
        # 清理可能的代码块标记
        content = content.replace("```json", "").replace("```", "").strip()
        queries = json.loads(content)
        return queries if isinstance(queries, list) else [queries]
    except Exception as e:
        print(f"[RAG] 查询改写失败: {e}")
        return [context_summary]


async def retrieve_context(stage: str, context_summary: str, top_k: int = 3) -> str:
    """获取 RAG 上下文（查询改写 + 多路检索 + 结果合并）"""
    queries = await query_rewrite_for_rag(stage, context_summary)

    all_docs = []
    seen_ids = set()
    for query in queries:
        docs = await search_knowledge(query, top_k=top_k)
        for doc in docs:
            if doc["id"] not in seen_ids:
                seen_ids.add(doc["id"])
                all_docs.append(doc)

    if not all_docs:
        return "暂无相关参考资料"

    # 拼接上下文
    context_parts = []
    for doc in all_docs[:top_k * 2]:  # 限制最终数量
        title = doc.get("metadata", {}).get("title", "未知")
        category = doc.get("metadata", {}).get("category", "通用")
        context_parts.append(f"### [{category}] {title}\n{doc['content']}")

    return "\n\n---\n\n".join(context_parts)


async def add_knowledge(title: str, content: str, category: str = "用户添加") -> str:
    """向知识库添加新知识"""
    import uuid
    doc_id = f"user_{uuid.uuid4().hex[:8]}"

    def _sync_add():
        collection = _get_script_collection()
        model = _get_embedding_model()
        embedding = model.encode([content]).tolist()
        collection.add(
            ids=[doc_id],
            embeddings=embedding,
            documents=[content],
            metadatas=[{"category": category, "title": title}]
        )
        return doc_id

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_add)


async def get_knowledge_stats() -> dict:
    """获取知识库统计信息"""
    def _sync_stats():
        collection = _get_script_collection()
        data = collection.get()
        return {
            "total_documents": len(data["ids"]),
            "categories": list(set(
                m.get("category", "未知")
                for m in data["metadatas"]
            )) if data["metadatas"] else []
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_stats)
