"""
 @File: weaviate_api.py
 @Description: 向量库工具类
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:58
"""
import copy
import time

import weaviate.classes.query as wq
from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams

from contextlib import contextmanager
from config import get_env

from controllers.agents.qwen_embedding.embedding_api import qwen_llm_embeddings, qwen_llm_embeddings_with_usage

# 从环境变量读取 Weaviate 配置
WEAVIATE_URL = get_env('WEAVIATE_URL')
GRPC_PORT = int(get_env('GRPC_PORT') or 50051)  # Weaviate gRPC 默认端口

# 定义向量数据库中的存储结构，可以理解为定义 CLASS_NAME 这张数据库表中的字段
schema = {
    "class": "",  # 运行时填充为用户独立的向量检索空间类名
    "description": "数据卡片存储",
    "properties": [
        {
            "name": "doc_id",
            "dataType": ["string"],  # 精确匹配/过滤更合适
            "description": "卡片id"
        },
        {
            "name": "abstract",
            "dataType": ["text"], # 用于语义检索
            "description": "卡片摘要"
        },
        {
            "name": "datasource_id",
            "dataType": ["string"],  # 精确匹配/过滤，和 doc_id 一样
            "description": "数据源id"
        }
    ],
    "vectorizer": "none",  # 不使用内建 vectorizer 去向量化文本，使用自定义向量化函数
    # 向量索引配置
    "vectorIndexConfig": {
        # weaviate的相似度计算指标：默认为余弦相似度（cosine similarity）
        # 余弦相似度	    "cosine"	    常用于文本语义、推荐系统等【计算向量夹角，方向越一致则相似度高，为1时代表完全一致】
        # 欧氏距离	    "l2"	        常用于数值特征，如图像像素值等【计算向量差值，越小则相似度高】
        # 欧几里得距离	"l2-squared"	几何空间中的欧式距离平方
        # 曼哈顿距离	    "manhattan"	    各维度差值绝对值之和
        # 点积	        "dot"	        向量点乘（未归一化向量常用）
        "distance": "cosine"  # 可选：cosine / l2 / dot / manhattan
    }
}

# 上下文管理器封装向量库连接
@contextmanager
def weaviate_client():
    client = WeaviateClient(connection_params=ConnectionParams.from_url(url=WEAVIATE_URL, grpc_port=GRPC_PORT))
    client.connect()
    try:
        yield client
    finally:
        client.close()

# 判断某个用户的向量检索空间class是否存在，不存在的新建
def ensure_user_collection_exists(class_name: str) -> str:
    """
    仅用于"用户创建阶段"的初始化：
    - class_name 为空直接报错
    - 不存在则创建（严格隔离下唯一允许创建 collection 的地方）
    - 返回规范化后的 class_name
    """
    target = _require_user_class_name(class_name)

    with weaviate_client() as client:
        if client.collections.exists(target):
            print(f"[Weaviate][INIT] collection exists: {target}")
            return target

        # 使用 Weaviate v4 原生 API 创建 collection
        # 明确指定 tokenization 以支持精确过滤
        from weaviate.classes.config import Property, DataType, Tokenization, Configure, VectorDistances

        client.collections.create(
            name=target,
            description="数据卡片存储",
            properties=[
                Property(
                    name="doc_id",
                    data_type=DataType.TEXT,
                    description="卡片id",
                    tokenization=Tokenization.WHITESPACE,  # UUID 不包含空格，相当于不分词
                    index_filterable=True,
                    index_searchable=True
                ),
                Property(
                    name="abstract",
                    data_type=DataType.TEXT,
                    description="卡片摘要",
                    tokenization=Tokenization.WORD,  # 摘要需要分词以支持全文搜索
                    index_filterable=True,
                    index_searchable=True
                ),
                Property(
                    name="datasource_id",
                    data_type=DataType.TEXT,
                    description="数据源id",
                    tokenization=Tokenization.FIELD,  # 不分词，整个字段作为一个 token，支持精确过滤
                    index_filterable=True,
                    index_searchable=False  # 数据源ID不需要全文搜索
                )
            ],
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE  # 余弦相似度
                )
            )
        )
        print(f"[Weaviate][INIT] collection created with v4 API: {target}")
        return target

# 规范化类名，避免出现 '-' 字符冲突
def _normalize_class_name(name: str) -> str:
    """
    Weaviate class/collection 命名通常不接受 '-' 等字符。
    你要求 DB 存原文，这里仅在使用时做最小规范化。
    """
    if not name:
        return ""
    return str(name).strip().replace("-", "_")

# 校验用户是否拥有向量检索空间
def _require_user_class_name(class_name: str) -> str:
    """严格模式：class_name 必须存在且合法"""
    target = _normalize_class_name(class_name)
    if not target:
        print("[Weaviate][STRICT] user class_name is empty/None")
        raise ValueError("user weaviate class_name is empty")
    return target
# 校验用户的检索空间是否在向量库中存在
def _require_collection_exists(client: WeaviateClient, class_name: str) -> None:
    """严格模式：collection 必须存在，否则报错（不回退、不自动创建）"""
    if not client.collections.exists(class_name):
        print(f"[Weaviate][STRICT] collection '{class_name}' not exists")
        raise RuntimeError(f"weaviate collection '{class_name}' not exists")

# ========================================
# 自适应卡片数量选择算法
# ========================================

def adaptive_select_cards(reranked_results: list,
                          max_results: int = 20,
                          min_results: int = 2,
                          score_threshold: float = 0.3,
                          gap_threshold: float = 0.20,
                          adaptive_mode: str = 'smart',
                          user_query: str = None) -> list:
    """
    智能择优策略：基于重排序分数的卡片择优选择
    
    【核心理念】
    重排序不只是排序，更是智能择优！
    - 阈值过滤：基于向量距离，粗筛候选集
    - 重排序：基于语义理解，评估每张卡片的相关性
    - 智能择优：基于重排序分数，选择最相关的卡片
    
    【策略模式】
    1. 'off' - 无择优：保留所有阈值过滤的卡片（只做排序，不筛选）
    2. 'gap' - 梯度择优：识别分数"断崖"，保留高分段
    3. 'score' - 阈值择优：过滤低分卡片（score < threshold）
    4. 'hybrid' - 混合择优：结合梯度和阈值
    5. 'smart' - 智能择优：自动识别高质量卡片（推荐）
    
    【使用场景】
    - 阈值过滤返回 3-5 张：简单查询，可能都保留
    - 阈值过滤返回 8-12 张：中等查询，择优选择 5-8 张
    - 阈值过滤返回 15+ 张：复杂查询，择优选择 8-12 张
    
    参数：
    - reranked_results: 重排序后的结果列表（需包含 rerank_score 字段）
    - max_results: 最多返回数量（上限保护）
    - min_results: 最少返回数量（保底数量）
    - score_threshold: 分数阈值（0-1，推荐 0.5-0.7）
    - gap_threshold: 梯度阈值（推荐 0.10-0.15）
    - adaptive_mode: 自适应策略 ('smart'推荐 / 'off' / 'gap' / 'score' / 'hybrid')
    - user_query: 用户查询文本（用于检测多条件查询）
    
    返回：
    - 择优后的卡片列表
    """
    
    # 如果结果太少，直接返回
    if not reranked_results or len(reranked_results) <= min_results:
        print(f"[自适应选择] 结果数量 {len(reranked_results)} <= {min_results}，直接返回")
        return reranked_results
    
    # === 模式 1: 'off' - 无择优（保留所有）===
    if adaptive_mode == 'off':
        if len(reranked_results) > max_results:
            result = reranked_results[:max_results]
            print(f"[择优策略] 模式=off（无择优），结果超过上限 {max_results}，截取前 {max_results} 张")
            return result
        else:
            print(f"[择优策略] 模式=off（无择优），保留所有 {len(reranked_results)} 张卡片")
            return reranked_results
    
    scores = [r.get('rerank_score', 0.0) for r in reranked_results]
    
    # === 模式 2: 'smart' - 智能择优（推荐） ===
    if adaptive_mode == 'smart':
        return _smart_selection(reranked_results, scores, min_results, max_results, score_threshold, gap_threshold, user_query)
    
    # === 模式 3: 'gap' - 梯度择优 ===
    if adaptive_mode == 'gap':
        gaps = []
        for i in range(len(scores) - 1):
            gap = scores[i] - scores[i+1]  # 分数是降序排列的
            gaps.append((i+1, gap))
        
        # 按 gap 从大到小排序
        gaps.sort(key=lambda x: x[1], reverse=True)
        
        # 找到最大的 gap（在合理范围内）
        cut_point = None
        for pos, gap in gaps:
            if gap >= gap_threshold and min_results <= pos <= max_results:
                cut_point = pos
                max_gap = gap
                break
        
        if cut_point:
            result = reranked_results[:cut_point]
            print(f"[择优策略] 模式=gap，在位置 {cut_point} 发现分数断崖 (gap={max_gap:.3f})")
            print(f"[择优策略] 从 {len(reranked_results)} 张中择优 {cut_point} 张 ")
            return result
    
    # === 模式 4: 'score' / 'hybrid' - 分数阈值择优 ===
    high_quality = [r for r in reranked_results if r.get('rerank_score', 0.0) >= score_threshold]
    
    if len(high_quality) < min_results:
        # 高质量卡片不足，至少返回 min_results 张
        result = reranked_results[:min_results]
        print(f"[择优策略] 模式={adaptive_mode}，高质量卡片不足，保底返回 {min_results} 张")
        return result
    
    elif len(high_quality) > max_results:
        # 高质量卡片太多，限制在 max_results
        result = high_quality[:max_results]
        print(f"[择优策略] 模式={adaptive_mode}，限制返回 {max_results} 张（阈值={score_threshold}）")
        return result
    
    else:
        # 在合理范围内，按质量返回
        print(f"[择优策略] 模式={adaptive_mode}，从 {len(reranked_results)} 张中择优 {len(high_quality)} 张 ")
        return high_quality


def _detect_multi_condition_query(user_query: str) -> bool:
    """
    检测是否为多条件查询（OR 关系）
    
    例如：
    - "在广州仓库有库存，或者近30天销量超过100的商品"
    - "价格低于100或者销量超过1000的商品"
    - "库存大于50或销量排名前10"
    
    返回：
    - True: 是多条件 OR 查询，需要保留更多候选表
    - False: 单条件或 AND 查询，可以按正常策略筛选
    """
    if not user_query:
        return False
    
    import re
    
    # OR 关键词（中英文）
    or_keywords = [
        r'或者', r'或', r'或是',  # 中文
        r'\bor\b', r'\beither\b',  # 英文
        r'任一', r'任意', r'其一',  # 中文表达
    ]
    
    # 多条件特征词（逗号 + 多个动词/条件）
    multi_condition_patterns = [
        r'，.*?(超过|大于|小于|低于|高于|等于|在|有)',  # 逗号后跟条件词
        r'、.*?(超过|大于|小于|低于|高于|等于|在|有)',  # 顿号后跟条件词
    ]
    
    # 1. 检测明确的 OR 关键词
    for keyword in or_keywords:
        if re.search(keyword, user_query, re.IGNORECASE):
            return True
    
    # 2. 检测多条件特征（至少2个条件）
    condition_count = 0
    for pattern in multi_condition_patterns:
        if re.search(pattern, user_query):
            condition_count += 1
    
    return condition_count >= 1


def _smart_selection(reranked_results: list, scores: list, min_results: int, max_results: int, 
                     score_threshold: float, gap_threshold: float, user_query: str = None) -> list:
    """
    智能择优策略：综合多个维度，自动识别高质量卡片
    
    策略逻辑：
    1. 分数分布分析：识别高分簇和低分簇
    2. 梯度分析：识别分数断崖
    3. 绝对分数：过滤低相关性卡片
    4. 动态调整：根据总数自适应调整返回数量
    5. 多条件查询检测：对 OR 查询保留更多候选表  NEW
    
    目标：
    - 简单查询（3-5张）→ 可能都保留或略微筛选
    - 中等查询（8-12张）→ 择优选择 5-8张
    - 复杂查询（15+张）→ 择优选择 8-12张
    - OR查询（多条件）→ 保留更多候选，避免过滤掉部分相关表  NEW
    """
    total = len(reranked_results)
    
    # === 0. 检测是否为多条件查询 ===
    is_multi_condition = _detect_multi_condition_query(user_query)
    if is_multi_condition:
        print(f"[智能择优] 检测到多条件查询（OR关系），将采用宽松策略 ")
    
    # === 1. 快速路径：结果较少，直接返回 ===
    if total <= 10:
        # 结果很少，全部保留
        print(f"[智能择优] 结果较少 ({total} 张)，全部保留 ")
        return reranked_results
    
    # === 2. 分数分布分析 ===
    max_score = scores[0]
    min_score = scores[-1]
    avg_score = sum(scores) / len(scores)
    
    print(f"[智能择优] 分数分布: max={max_score:.3f}, avg={avg_score:.3f}, min={min_score:.3f}")
    
    # === 3. 梯度分析（寻找断崖） ===
    gaps = []
    for i in range(len(scores) - 1):
        gap = scores[i] - scores[i+1]
        gaps.append((i+1, gap))
    
    # 找到最大梯度
    gaps.sort(key=lambda x: x[1], reverse=True)
    best_gap_pos, best_gap_value = gaps[0] if gaps else (0, 0.0)
    
    # === 4. 智能决策 ===
    selected_count = None
    reason = ""
    
    # 特殊策略：多条件查询（OR关系）- 使用更宽松的筛选
    if is_multi_condition:
        # 计算一个更宽松的分数下限（平均分 * 0.6，但至少要有一定的相关性）
        # 这样可以包含那些只匹配部分条件的表
        relaxed_threshold = max(avg_score * 0.6, 0.05)  # 至少保证分数 > 0.05
        
        above_relaxed = [i for i, s in enumerate(scores) if s >= relaxed_threshold]
        
        if len(above_relaxed) >= min_results:
            # 对于多条件查询，我们保留更多候选
            # 例如：13张候选，如果有10张分数 >= relaxed_threshold，我们保留8-10张
            selected_count = min(len(above_relaxed), max_results)
            reason = f"多条件查询（宽松策略，threshold={relaxed_threshold:.3f}）"
        else:
            # 如果宽松阈值还是过滤太多，至少保留 2/3
            selected_count = max(min_results, total * 2 // 3)
            reason = f"多条件查询（保底策略，返回2/3）"
    
    # 策略 1：发现明显的分数断崖（仅非多条件查询）
    elif best_gap_value >= gap_threshold and min_results <= best_gap_pos <= max_results:
        selected_count = best_gap_pos
        reason = f"发现分数断崖 (gap={best_gap_value:.3f})"
    
    # 策略 2：基于分数阈值过滤
    elif score_threshold > 0:
        high_quality = [i for i, s in enumerate(scores) if s >= score_threshold]
        if len(high_quality) >= min_results:
            selected_count = min(len(high_quality), max_results)
            reason = f"分数阈值过滤 (threshold={score_threshold})"
    
    # 策略 3：基于平均分动态调整
    if selected_count is None:
        # 使用平均分作为参考
        above_avg = [i for i, s in enumerate(scores) if s >= avg_score]
        if len(above_avg) >= min_results:
            selected_count = min(len(above_avg), max_results)
            reason = f"平均分以上 (avg={avg_score:.3f})"
        else:
            # 至少返回一半或 min_results
            selected_count = max(min_results, total // 2)
            reason = f"保底策略（返回一半或最少数量）"
    
    # 策略 4：动态调整（基于总数）
    if selected_count is None or selected_count > max_results:
        if total <= 8:
            selected_count = max(min_results, total * 2 // 3)  # 返回 2/3
        elif total <= 15:
            selected_count = max(min_results, total // 2)  # 返回 1/2
        else:
            selected_count = max(min_results, min(12, total // 3))  # 返回 1/3 或最多 12 张
        reason = f"动态调整（总数={total}）"
    
    # === 5. 最终确定返回数量 ===
    selected_count = max(min_results, min(selected_count, max_results))
    result = reranked_results[:selected_count]
    
    print(f"[智能择优] {reason}")
    print(f"[智能择优] 从 {total} 张中择优 {selected_count} 张 ")
    print(f"[智能择优] 选中卡片分数范围: [{scores[selected_count-1]:.3f}, {scores[0]:.3f}]")
    
    return result

# 向量入库
def add_vector(data_card_obj: dict, class_name: str):
    doc_id = data_card_obj.get("DocInfo", {}).get("doc_id")
    abstract = data_card_obj.get("Abstract", "")
    datasource_id = data_card_obj.get("DocInfo", {}).get("datasource_id")  # 新增：获取数据源ID

    data_object = {
        "doc_id": doc_id,
        "abstract": abstract,
        "datasource_id": str(datasource_id) if datasource_id else ""  # 新增：存储数据源ID（转为字符串）
    }

    enhanced_text = _build_enhanced_text_for_embedding(data_card_obj, abstract)
    vector = qwen_llm_embeddings(enhanced_text)

    with weaviate_client() as client:
        target_class_name = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class_name)

        collection = client.collections.get(target_class_name)
        obj_uuid = collection.data.insert(data_object, vector=vector)
        print(f"[向量入库][STRICT] class={target_class_name} doc_id={doc_id} datasource_id={datasource_id} uuid={obj_uuid}")
        return obj_uuid

def apply_rerank(query: str, results: list, top_n: int = 20) -> list:
    """
    使用 Qwen Rerank 模型对向量召回结果进行重排序

    重排序的优势：
    1. 向量检索（粗排）：基于语义相似度，快速召回候选集
    2. 重排序（精排）：理解任务意图和上下文，精确排序最相关的结果

    参数：
    - query: 用户查询文本
    - results: 向量召回的结果列表 [{"uuid": "...", "doc_id": "...", "abstract": "...", "distance": ...}, ...]
    - top_n: 重排序后保留的 top N 结果

    返回：
    重排序后的结果列表，按 rerank_score 降序排列（分数越高越相关）
    [
        {"uuid": "...", "doc_id": "...", "abstract": "...", "distance": ..., "rerank_score": 0.95, "rerank_index": 0},
        ...
    ]
    """
    reranked, rerank_usage = apply_rerank_with_usage(query, results, top_n)
    return reranked


def apply_rerank_with_usage(query: str, results: list, top_n: int = 20):
    """
    使用 Qwen Rerank 模型对向量召回结果进行重排序（带 Token 使用量统计）

    参数：
    - query: 用户查询文本
    - results: 向量召回的结果列表
    - top_n: 重排序后保留的 top N 结果

    返回：(reranked_results, usage_dict)
        - reranked_results: 重排序后的结果列表
        - usage_dict: Token 使用量 {"total_tokens": int}
    """
    if not results:
        return [], {"total_tokens": 0}

    # 如果结果数量小于等于 1，无需重排序
    if len(results) <= 1:
        print(f"[重排序] 结果数量 <= 1，跳过重排序")
        return results, {"total_tokens": 0}

    try:
        # 导入 Qwen Rerank 模型（带 usage 版本）
        from controllers.agents.qwen_rerank.QwenRerank import QwenRerank_llm_with_usage

        # 准备文档列表（只传递摘要文本）
        documents = [r.get("abstract", "") for r in results]

        # 调用重排序模型
        print(f"[重排序] 调用 Qwen Rerank 模型，query='{query[:50]}...', 文档数={len(documents)}, top_n={top_n}")
        rerank_results, rerank_usage = QwenRerank_llm_with_usage(
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents))
        )

        if not rerank_results:
            print(f"[重排序] 重排序结果为空，回退到向量排序")
            # 为回退结果添加默认的 rerank_score（基于向量距离的转换分数）
            for r in results:
                r["rerank_score"] = max(0, 1 - r.get("distance", 0))
            return results, rerank_usage

        # 打印 API 返回的原始 rerank_results
        print(f"\n[重排序] API 返回的原始数据：")
        for i, item in enumerate(rerank_results):
            print(f"  [{i}] index={item.get('index')}, relevance_score={item.get('relevance_score')}")

        # 构建重排序后的结果列表
        reranked = []
        raw_scores = []
        for rerank_item in rerank_results:
            original_index = rerank_item.get("index")
            relevance_score = rerank_item.get("relevance_score", 0.0)
            raw_scores.append(relevance_score)

            if original_index is not None and 0 <= original_index < len(results):
                item = results[original_index].copy()
                item["rerank_score"] = relevance_score
                item["rerank_index"] = original_index
                reranked.append(item)

        # 打印重排序效果对比
        print(f"\n[重排序] 重排序完成，返回 {len(reranked)} 条结果")
        print(f"[重排序] 分数统计：min={min(raw_scores):.4f}, max={max(raw_scores):.4f}, avg={sum(raw_scores)/len(raw_scores):.4f}")
        print(f"[重排序] === 重排序前后对比 ===")
        print(f"{'排名':<6} {'重排序分数':<12} {'向量距离':<12} {'doc_id':<40}")
        print("-" * 70)
        for i, item in enumerate(reranked[:10], 1):
            doc_id = str(item.get("doc_id", ""))[:36]
            rerank_score = item.get("rerank_score", 0.0)
            distance = item.get("distance", 0.0)
            print(f"{i:<6} {rerank_score:<12.4f} {distance:<12.4f} {doc_id}")

        # 应用自适应选择
        if top_n is not None and top_n > 0:
            selected = adaptive_select_cards(
                reranked,
                max_results=top_n,
                score_threshold=float(get_env('VECTOR_SEARCH_SCORE_THRESHOLD')),
                gap_threshold=float(get_env('VECTOR_SEARCH_GAP_THRESHOLD')),
                adaptive_mode=get_env('VECTOR_SEARCH_ADAPTIVE_MODE'),
                user_query=query
            )
            return selected, rerank_usage

        return reranked, rerank_usage

    except ImportError as e:
        print(f"[重排序] 无法导入 Qwen Rerank 模型: {e}，回退到向量排序")
        # 为回退结果添加默认的 rerank_score（基于向量距离的转换分数）
        for r in results:
            r["rerank_score"] = max(0, 1 - r.get("distance", 0))
        return results, {"total_tokens": 0}
    except Exception as e:
        print(f"[重排序] 重排序失败: {e}，回退到向量排序")
        import traceback
        traceback.print_exc()
        # 为回退结果添加默认的 rerank_score（基于向量距离的转换分数）
        for r in results:
            r["rerank_score"] = max(0, 1 - r.get("distance", 0))
        return results, {"total_tokens": 0}

def _build_enhanced_text_for_embedding(data_card_obj: dict, abstract: str) -> str:
    """
    构建增强的文本用于向量化
    
    策略：
    1. 原始摘要（核心）
    2. 表名和字段名（中英文）
    3. Tags 标签
    4. 适用场景描述
    5. 业务领域
    6. 字段详细信息（包含注释，提高匹配精度）
    
    这样可以提高向量语义匹配的精度
    """
    parts = [abstract]  # 摘要作为核心
    
    # 1. 添加表名和数据库信息
    doc_info = data_card_obj.get("DocInfo", {})
    sqlmeta = data_card_obj.get("SQLMeta", {})
    
    table_name = sqlmeta.get("table", "") or doc_info.get("table_name", "")
    database_name = doc_info.get("database_name", "")
    
    if table_name:
        parts.append(f"表名: {table_name}")
    if database_name:
        parts.append(f"数据库: {database_name}")
    
    # 2. 添加关键字段名称（中英文）+ 注释（增强）
    columns = sqlmeta.get("columns", []) or data_card_obj.get("Columns", [])
    if columns:
        # 提取字段名和注释
        field_info = []
        for col in columns[:20]:  # 最多取前20个字段
            col_name = col.get("name", "") or col.get("column_name", "")
            col_comment = col.get("comment", "")
            col_type = col.get("type", "")
            
            if col_name:
                # 增强格式：字段名(注释)[类型]
                if col_comment and col_type:
                    field_info.append(f"{col_name}({col_comment})[{col_type}]")
                elif col_comment:
                    field_info.append(f"{col_name}({col_comment})")
                elif col_type:
                    field_info.append(f"{col_name}[{col_type}]")
                else:
                    field_info.append(col_name)
        
        if field_info:
            parts.append(f"关键字段: {', '.join(field_info)}")
    
    # 3. 添加 Tags 标签
    tags = data_card_obj.get("Tags", [])
    if tags:
        parts.append(f"标签: {', '.join(tags)}")
    
    # 4. 添加业务领域
    domain = doc_info.get("domain", "") or data_card_obj.get("Domain", "")
    if domain:
        parts.append(f"业务领域: {domain}")
    
    # 5. 添加适用场景
    key_concepts = data_card_obj.get("KeyConcepts", {})
    applicable_scenarios = key_concepts.get("applicable_scenarios", [])
    if applicable_scenarios:
        parts.append(f"适用场景: {', '.join(applicable_scenarios)}")
    
    # 6. 添加核心主题和别名
    canonical_topic = key_concepts.get("canonical_topic", "")
    if canonical_topic:
        parts.append(f"核心主题: {canonical_topic}")
    
    alias = key_concepts.get("alias", [])
    if alias:
        parts.append(f"别名: {', '.join(alias)}")
    
    # 7. 添加关键实体（新增）
    key_entities = key_concepts.get("key_entities", [])
    if key_entities:
        parts.append(f"核心实体: {', '.join(key_entities)}")
    
    # 拼接所有部分，用换行符分隔
    enhanced_text = "\n".join(parts)
    
    return enhanced_text

# 向量检索（改进版：基于距离阈值的智能召回 + 重排序）
def search_vector(
    input_text: str,
    class_name: str,      # 新增：优先检索的 class
    distance_threshold: float = 0.6,   # 距离阈值：越小越相似（cosine distance: 0=完全相同, 2=完全相反）
    max_results: int = 20,             # 最大返回数量
    min_results: int = 2,              # 最小返回数量（确保至少返回一些结果）
    query_limit: int = 50,             # 初始查询数量（用于过滤）
    enable_rerank: bool = True,        # 是否启用重排序（默认启用）
    rerank_top_n: int = None,          # 重排序后保留的 top N 结果（None 则使用 max_results）
    datasource_id = None               # 新增：数据源ID过滤（支持 str 单个ID 或 list 多个ID）
):
    """
    基于向量相似度的智能召回 + 语义重排序：

    【两阶段检索流程】
    阶段 1 - 向量粗排（Weaviate）：
      1. 【可选】根据 datasource_id 预过滤（支持单个或多个数据源）
      2. 先查询较多的候选结果（query_limit）
      3. 根据 distance_threshold 过滤出高相关性的结果
      4. 如果过滤后结果少于 min_results，返回最相似的 min_results 条
      5. 如果过滤后结果多于 max_results，只返回前 max_results 条

    阶段 2 - 语义重排（Qwen Rerank）：
      6. 【可选】使用重排序模型对粗排结果进行精排，理解任务语义和上下文相关性
      7. 返回重排序后的 top_n 结果

    参数说明：
    - distance_threshold: 余弦距离阈值，建议 0.5-0.6（越小越严格）
      * 0.3-0.4: 非常严格，只召回高度相似的
      * 0.5-0.55: 平衡（推荐），召回相关性较好的卡片
      * 0.6-0.7: 宽松，召回更多可能相关的卡片
    - max_results: 最大返回数量，避免返回过多结果
    - min_results: 最小返回数量，避免因阈值过严导致无结果
    - query_limit: 初始查询数量，应大于 max_results（建议 50-100）
    - enable_rerank: 是否启用重排序（默认 True），设为 False 可关闭重排序
    - rerank_top_n: 重排序后保留的数量（默认使用 max_results）
    - datasource_id: 数据源ID过滤（可选），支持：
        * str: 单个数据源ID，仅检索该数据源的卡片
        * list: 多个数据源ID，检索这些数据源的卡片（OR 关系）
        * None: 不过滤，检索所有卡片

    返回：
    [
        {"uuid": "...", "doc_id": "...", "abstract": "...", "distance": 0.25, "rerank_score": 0.95},
        ...
    ]
    启用重排序时：按 rerank_score 降序排列（越大越相关）
    未启用重排序时：按 distance 升序排列（越小越相似）
    """
    if not input_text:
        return {"error": "Missing text"}, 400

    # 收集 token 使用量
    usage = {
        "embedding_tokens": 0,
        "rerank_tokens": 0,
        "rerank_ms": 0,
        "reranked_count": 0,
        "top1_rerank_score": None,
        "avg_rerank_score": None
    }

    with weaviate_client() as client:
        # 调用 embedding（带 usage 版本）
        vector, embed_usage = qwen_llm_embeddings_with_usage(input_text)
        usage["embedding_tokens"] = embed_usage.get("total_tokens", 0)

        target_class = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class)

        collection = client.collections.get(target_class)

        # 构建过滤条件（支持单个或多个数据源ID）
        filters = None
        if datasource_id:
            from weaviate.classes.query import Filter

            # 支持单个ID（str）或多个ID（list）
            if isinstance(datasource_id, list):
                # 多个数据源ID：使用 contains_any 实现 OR 查询
                datasource_ids = [str(ds_id) for ds_id in datasource_id]
                filters = Filter.by_property("datasource_id").contains_any(datasource_ids)
                print(f"[向量检索] 应用数据源过滤（多个）: datasource_ids={datasource_ids}")
            else:
                # 单个数据源ID：使用 equal
                filters = Filter.by_property("datasource_id").equal(str(datasource_id))
                print(f"[向量检索] 应用数据源过滤（单个）: datasource_id={datasource_id}")

        # 1. 查询较多的候选结果（应用数据源过滤）
        resp = collection.query.near_vector(
            near_vector=vector,
            limit=query_limit,
            filters=filters,  # 应用过滤器
            return_metadata=wq.MetadataQuery(distance=True)
        )

        # 2. 转换为列表并按距离排序
        all_results = [
            {
                "uuid": str(o.uuid),
                "doc_id": o.properties.get("doc_id"),
                "abstract": o.properties.get("abstract"),
                "distance": getattr(o.metadata, "distance", None)
            }
            for o in resp.objects
        ]

        # 按距离升序排列（距离越小越相似）
        all_results.sort(key=lambda x: x.get("distance") or float('inf'))
        
        # 3. 根据阈值过滤
        filtered_results = [
            r for r in all_results 
            if r.get("distance") is not None and r["distance"] <= distance_threshold
        ]
        
        # 4. 应用 min_results 和 max_results 约束
        if len(filtered_results) < min_results:
            # 如果过滤后结果太少，至少返回 min_results 条最相似的
            final_results = all_results[:min_results]
            print(f"[向量召回] 阈值过滤后仅 {len(filtered_results)} 条，返回最相似的 {len(final_results)} 条")
        elif len(filtered_results) > max_results:
            # 如果过滤后结果太多，只返回前 max_results 条
            final_results = filtered_results[:max_results]
            print(f"[向量召回] 阈值过滤出 {len(filtered_results)} 条，限制返回前 {max_results} 条")
        else:
            # 过滤后的结果在合理范围内
            final_results = filtered_results
            print(f"[向量召回] 阈值 {distance_threshold} 过滤后返回 {len(final_results)} 条卡片")
        
        # 5. 打印召回详情（便于调试和优化阈值）
        if final_results:
            distances = [r.get("distance", 0) for r in final_results]
            print(f"[向量召回] 距离范围: [{min(distances):.3f}, {max(distances):.3f}]")
            for i, r in enumerate(final_results):
                print(f"  [{i+1}] doc_id={r.get('doc_id')}, distance={r.get('distance'):.3f}")
        
        # 6. 【可选】重排序阶段：使用 Qwen Rerank 进行语义精排
        if enable_rerank and final_results:
            print(f"\n[重排序] 启动语义重排序，对 {len(final_results)} 条结果进行精排...")
            rerank_start = time.time()
            final_results, rerank_usage = apply_rerank_with_usage(
                query=input_text,
                results=final_results,
                top_n=rerank_top_n or max_results
            )
            usage["rerank_tokens"] = rerank_usage.get("total_tokens", 0)
            usage["rerank_ms"] = int((time.time() - rerank_start) * 1000)
            usage["reranked_count"] = len(final_results)
            
            # 收集重排序分数
            rerank_scores = [r.get("rerank_score", 0) for r in final_results if r.get("rerank_score")]
            if rerank_scores:
                usage["top1_rerank_score"] = rerank_scores[0]
                usage["avg_rerank_score"] = sum(rerank_scores) / len(rerank_scores)

        # 返回结果和 usage
        return final_results, usage

# 根据id删除对应class中的单条记录
def delete_by_uuid(uuid_str: str, class_name: str) -> bool:
    with weaviate_client() as client:
        target_class = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class)

        collection = client.collections.get(target_class)
        collection.data.delete_by_id(uuid_str)
        return True

# 批量删除向量库中某个class的指定数据
def batch_delete_by_uuids(uuids: list, class_name: str) -> bool:
    if not uuids:
        print("[Weaviate][STRICT] empty uuids")
        raise ValueError("empty uuids")

    with weaviate_client() as client:
        target_class = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class)

        collection = client.collections.get(target_class)
        from contextlib import suppress
        for uuid in uuids:
            with suppress(Exception):
                collection.data.delete_by_id(uuid)
        return True

# 获取某个class中的所有记录数
def get_total_count(class_name: str) -> int:
    """
    获取向量库中指定用户检索空间的记录数量（严格隔离：不回退、不默认）
    """
    with weaviate_client() as client:
        target_class = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class)

        collection = client.collections.get(target_class)
        result = collection.aggregate.over_all(total_count=True)
        total = result.total_count

        print(f"[向量库统计][STRICT] {target_class} 表中共有 {total} 条记录")
        return total

# 获取向量库中某个class的指定 doc_id 的记录
def get_records_by_doc_id(doc_id: str, class_name: str) -> list:
    """
    根据 doc_id 查询指定用户检索空间中的所有记录（严格隔离：不回退、不默认）
    """
    if not doc_id:
        print("[Weaviate][STRICT] doc_id is empty")
        raise ValueError("doc_id is empty")

    with weaviate_client() as client:
        target_class = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class)

        collection = client.collections.get(target_class)

        # 使用 where 过滤器精确匹配 doc_id
        from weaviate.classes.query import Filter

        response = collection.query.fetch_objects(
            filters=Filter.by_property("doc_id").equal(doc_id),
            limit=1000
        )

        results = []
        for obj in response.objects:
            results.append({
                "uuid": str(obj.uuid),
                "doc_id": obj.properties.get("doc_id"),
                "abstract": obj.properties.get("abstract"),
                "creation_time": getattr(obj.metadata, "creation_time_unix", None),
                "last_update_time": getattr(obj.metadata, "last_update_time_unix", None)
            })

        print(f"[向量库查询][STRICT] class={target_class} doc_id={doc_id} 找到 {len(results)} 条记录")
        for i, record in enumerate(results, 1):
            print(f"  [{i}] uuid={record['uuid']}")

        return results

# 删除目标检索空间class中的所有向量记录
def delete_all_records_in_class(class_name: str, batch_size: int = 100) -> dict:
    """
    删除指定用户检索空间 class 中的所有向量记录（严格隔离：class_name 必传且必须存在）
    """
    with weaviate_client() as client:
        try:
            target_class = _require_user_class_name(class_name)
            _require_collection_exists(client, target_class)

            collection = client.collections.get(target_class)

            # 先获取当前记录总数
            total_before = collection.aggregate.over_all(total_count=True).total_count
            print(f"[批量删除][STRICT] 准备删除 {target_class} 中的所有记录，当前共有 {total_before} 条")

            if total_before == 0:
                return {
                    "success": True,
                    "deleted_count": 0,
                    "message": f"向量库 {target_class} 中没有记录，无需删除"
                }

            deleted_count = 0
            while True:
                response = collection.query.fetch_objects(
                    limit=batch_size,
                    return_properties=[]
                )
                if not response.objects:
                    break

                uuids = [str(obj.uuid) for obj in response.objects]
                print(f"[批量删除][STRICT] 正在删除 {target_class} 的 {len(uuids)} 条记录...")

                for uuid in uuids:
                    collection.data.delete_by_id(uuid)
                    deleted_count += 1

                if len(uuids) < batch_size:
                    break

            total_after = collection.aggregate.over_all(total_count=True).total_count
            print(f"[批量删除][STRICT] 成功删除 {deleted_count} 条记录，删除后剩余 {total_after} 条")

            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"成功从 {target_class} 中删除 {deleted_count} 条记录" + (f"，仍有 {total_after} 条未删除" if total_after > 0 else "")
            }

        except Exception as e:
            error_msg = f"[批量删除][STRICT] 删除 {class_name} 中的所有记录失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "deleted_count": 0,
                "message": error_msg
            }

# 删除向量库中的某个class（而不是只删除其中的数据）
def drop_collection_by_class_name(class_name: str) -> None:
    """
    【危险操作】
    直接删除 Weaviate 中的整个 collection / class（不可逆）

    设计约束：
    - 严格模式：class_name 不能为空
    - 不存在直接报错
    - 不做任何 fallback
    - 不删除其中数据，而是删除整个 class
    """

    # 严格校验 class_name
    target = _require_user_class_name(class_name)

    with weaviate_client() as client:
        # 严格校验 collection 是否存在
        if not client.collections.exists(target):
            print(f"[Weaviate][STRICT][DROP] collection '{target}' not exists")
            raise RuntimeError(f"weaviate collection '{target}' not exists")

        # 删除整个 collection
        client.collections.delete(target)

        print(f"[Weaviate][DROP] collection '{target}' has been deleted")

# 列出所有class
def list_all_collections() -> list:
    """
    列出当前 Weaviate 向量数据库中的所有 collection / class 名称

    返回：
    [
        "datacard_datasource__xxx",
        "datacard_datasource__yyy",
        ...
    ]
    """
    with weaviate_client() as client:
        collections = client.collections.list_all()

        class_names = list(collections.keys())

        print(f"[Weaviate] 当前共有 {len(class_names)} 个 collection：")
        for name in class_names:
            print(f"  - {name}")

        return class_names

# ============ Field Index (全域盘点所需的字段索引) ============

FIELD_INDEX_SUFFIX = "__field_index"

field_index_schema = {
    "class": "",  # 运行时填充
    "description": "字段索引（全域盘点）",
    "properties": [
        {"name": "object_type", "dataType": ["string"], "description": "固定=field_entry"},
        {"name": "datasource_id", "dataType": ["string"], "description": "数据源ID"},
        {"name": "schema_hash", "dataType": ["string"], "description": "schema版本hash"},
        {"name": "source_type", "dataType": ["string"], "description": "table_ref/dict/confirmed"},
        {"name": "table_name", "dataType": ["string"], "description": "表名（dict可空）"},
        {"name": "column_name", "dataType": ["string"], "description": "字段名"},
        {"name": "column_type", "dataType": ["string"], "description": "字段类型（可空）"},
        {"name": "column_comment", "dataType": ["text"], "description": "字段注释"},
        {"name": "text", "dataType": ["text"], "description": "用于向量化的语义文本"},
    ],
    "vectorizer": "none",
    "vectorIndexConfig": {"distance": "cosine"}
}

def _field_index_class_name(user_class: str) -> str:
    base = _require_user_class_name(user_class)
    return f"{base}{FIELD_INDEX_SUFFIX}"

def ensure_field_index_collection_exists(user_class: str) -> str:
    """
    创建字段索引collection（可在全域盘点第一次运行时创建）
    """
    idx_class = _field_index_class_name(user_class)
    with weaviate_client() as client:
        if client.collections.exists(idx_class):
            return idx_class
        s = copy.deepcopy(field_index_schema)
        s["class"] = idx_class
        client.collections.create_from_dict(s)
        print(f"[Weaviate][FieldIndex] created: {idx_class}")
        return idx_class

def add_field_entry(entry: dict, user_class: str):
    """
    entry 需要包含：
      datasource_id, schema_hash, source_type, table_name, column_name, column_type, column_comment
    """
    idx_class = ensure_field_index_collection_exists(user_class)

    # 组装 text（这是向量召回的语义载体）
    text_for_embed = (
        f"表 {entry.get('table_name')} 字段 {entry.get('column_name')} 类型 {entry.get('column_type')} "
        f"注释 {entry.get('column_comment')}"
    ).strip()

    data_object = {
        "object_type": "field_entry",
        "datasource_id": str(entry.get("datasource_id") or ""),
        "schema_hash": str(entry.get("schema_hash") or ""),
        "source_type": entry.get("source_type") or "table_ref",
        "table_name": entry.get("table_name") or "",
        "column_name": entry.get("column_name") or "",
        "column_type": entry.get("column_type") or "",
        "column_comment": entry.get("column_comment") or "",
        "text": text_for_embed,
    }

    vector = qwen_llm_embeddings(text_for_embed)
    with weaviate_client() as client:
        _require_collection_exists(client, idx_class)
        collection = client.collections.get(idx_class)
        obj_uuid = collection.data.insert(data_object, vector=vector)
        return str(obj_uuid)

def search_field_entries(
    query_text: str,
    user_class: str,
    datasource_id: str,
    schema_hash: str,
    limit: int = 20
) -> list:
    """
    字段索引专用检索：仅在 field_index collection 中搜索，并按 datasource_id + schema_hash 过滤
    返回：[{uuid, distance, properties...}]
    """
    from weaviate.classes.query import Filter
    idx_class = _field_index_class_name(user_class)

    with weaviate_client() as client:
        vector = qwen_llm_embeddings(query_text)
        _require_collection_exists(client, idx_class)
        collection = client.collections.get(idx_class)

        # filters: object_type + datasource_id + schema_hash
        f = (
            Filter.by_property("object_type").equal("field_entry") &
            Filter.by_property("datasource_id").equal(str(datasource_id)) &
            Filter.by_property("schema_hash").equal(str(schema_hash))
        )

        resp = collection.query.near_vector(
            near_vector=vector,
            limit=limit,
            filters=f,
            return_metadata=wq.MetadataQuery(distance=True)
        )

        out = []
        for o in resp.objects:
            out.append({
                "uuid": str(o.uuid),
                "distance": getattr(o.metadata, "distance", None),
                **(o.properties or {})
            })
        # 距离越小越相似
        out.sort(key=lambda x: x.get("distance") if x.get("distance") is not None else 999)
        return out

def delete_field_index_by_datasource(
    datasource_id: str,
    user_class: str
) -> int:
    """
    删除字段索引中指定数据源的所有记录

    Args:
        datasource_id: 数据源ID
        user_class: 用户的向量库类名

    Returns:
        删除的记录数量
    """
    from weaviate.classes.query import Filter

    idx_class = _field_index_class_name(user_class)
    deleted_count = 0

    try:
        with weaviate_client() as client:
            if not client.collections.exists(idx_class):
                print(f"[FieldIndex][Delete] collection not exists: {idx_class}")
                return 0

            collection = client.collections.get(idx_class)

            # 查询该数据源的所有记录
            f = Filter.by_property("datasource_id").equal(str(datasource_id))

            response = collection.query.fetch_objects(
                filters=f,
                limit=1000
            )

            # 收集所有 uuid
            uuids_to_delete = [str(o.uuid) for o in response.objects]

            if uuids_to_delete:
                # 批量删除
                for uuid in uuids_to_delete:
                    try:
                        collection.data.delete_by_id(uuid)
                        deleted_count += 1
                    except Exception as e:
                        print(f"[FieldIndex][Delete] failed to delete uuid={uuid}: {e}")

            print(f"[FieldIndex][Delete] datasource_id={datasource_id} deleted {deleted_count} records from {idx_class}")

    except Exception as e:
        print(f"[FieldIndex][Delete] error: {e}")

    return deleted_count

# ========================================
# 关系卡片向量入库
# ========================================

def add_relationship_card_vector(relationship_card: dict, class_name: str) -> str:
    """
    将关系卡片入向量库

    关系卡片用于NL2SQL时的联表查询和结果融合，
    向量化时重点关注：表名、关联表名、JOIN字段、业务关系描述

    Args:
        relationship_card: 关系卡片对象
        class_name: 用户的向量库类名

    Returns:
        入库后的UUID
    """
    doc_info = relationship_card.get("DocInfo", {})
    doc_id = doc_info.get("doc_id", "")
    table_name = doc_info.get("table_name", "")

    # 构建增强文本用于向量化
    enhanced_text = _build_relationship_card_text_for_embedding(relationship_card)

    # 构建存储对象
    data_object = {
        "doc_id": doc_id,
        "abstract": enhanced_text  # 使用增强文本作为摘要
    }

    # 向量化
    vector = qwen_llm_embeddings(enhanced_text)

    with weaviate_client() as client:
        target_class_name = _require_user_class_name(class_name)
        _require_collection_exists(client, target_class_name)

        collection = client.collections.get(target_class_name)
        obj_uuid = collection.data.insert(data_object, vector=vector)
        print(f"[关系卡片向量入库] class={target_class_name} table={table_name} uuid={obj_uuid}")
        return str(obj_uuid)


def _build_relationship_card_text_for_embedding(relationship_card: dict) -> str:
    """
    构建关系卡片的增强文本用于向量化

    策略：
    1. 表名和关联摘要
    2. 所有关联表名
    3. JOIN字段信息
    4. 业务关系描述
    5. 联表使用场景

    这样在用户查询涉及多表联合时，可以召回相关的关系卡片
    """
    parts = []

    # 1. 基本信息
    doc_info = relationship_card.get("DocInfo", {})
    table_info = relationship_card.get("TableInfo", {})
    table_name = doc_info.get("table_name", "") or table_info.get("table_name", "")

    if table_name:
        parts.append(f"关系卡片: {table_name}")

    # 2. JOIN摘要
    join_summary = relationship_card.get("JoinSummary", "")
    if join_summary:
        parts.append(join_summary)

    # 3. 所有关联表和字段
    relationships = relationship_card.get("Relationships", [])
    if relationships:
        related_tables = []
        join_fields = []
        business_descriptions = []
        use_cases = []

        for rel in relationships:
            related_table = rel.get("related_table", "")
            if related_table:
                related_tables.append(related_table)

            # JOIN字段
            for field in rel.get("join_fields", []):
                local_field = field.get("local_field", "")
                remote_field = field.get("remote_field", "")
                if local_field and remote_field:
                    join_fields.append(f"{table_name}.{local_field}={related_table}.{remote_field}")

            # 业务关系描述
            business_rel = rel.get("business_relation", {})
            if business_rel.get("relation_description"):
                business_descriptions.append(business_rel["relation_description"])

            # 使用场景
            join_suggestion = rel.get("join_suggestion", {})
            for case in join_suggestion.get("use_cases", []):
                use_cases.append(case)

        if related_tables:
            parts.append(f"关联表: {', '.join(related_tables)}")

        if join_fields:
            parts.append(f"JOIN条件: {'; '.join(join_fields[:5])}")  # 最多5个

        if business_descriptions:
            parts.append(f"业务关系: {'; '.join(business_descriptions[:3])}")  # 最多3个

        if use_cases:
            parts.append(f"使用场景: {'; '.join(use_cases[:5])}")  # 最多5个

    # 4. 融合建议
    fusion_hints = relationship_card.get("FusionHints", {})
    as_master = fusion_hints.get("as_master", [])
    as_detail = fusion_hints.get("as_detail", [])

    if as_master:
        parts.append(f"作为主表: {'; '.join(as_master[:2])}")
    if as_detail:
        parts.append(f"作为明细表: {'; '.join(as_detail[:2])}")

    # 组合文本
    result = " | ".join(parts)

    print(f"[关系卡片向量化] 表: {table_name}, 文本长度: {len(result)}")

    return result


def delete_relationship_card_vector(doc_id: str, class_name: str) -> bool:
    """
    删除关系卡片的向量

    Args:
        doc_id: 关系卡片的doc_id
        class_name: 用户的向量库类名

    Returns:
        是否删除成功
    """
    records = get_records_by_doc_id(doc_id, class_name)
    if not records:
        return True

    uuids = [r.get("uuid") for r in records if r.get("uuid")]
    if uuids:
        return batch_delete_by_uuids(uuids, class_name)

    return True


# 单脚本运行
# if __name__ == '__main__':
#
    # delete_by_uuid('a501ccce-8f12-4013-9354-e361e7e9ae42','datacard_datasource__050bf967_f1c0_4d2b_99d8_c0da6bb423ed')
#     delete_by_uuid('fe8c1ec6-d920-4ff3-ae77-76462c46147d', 'datacard_datasource__0e594d21_9096_48ea_a33a_76af3872c328')

    # delete_all_records_in_class('datacard_datasource__e7e3a07d_d3d1_44bf_83d3_b5c0b5de9caf__field_index')
    # delete_all_records_in_class('datacard_datasource__59d688b2_e426_419e_8176_b95193766eb1__field_index')
    #
    # all_classes = list_all_collections()
    #
    # get_total_count('datacard_datasource__050bf967_f1c0_4d2b_99d8_c0da6bb423ed')
    # get_total_count('datacard_datasource__59d688b2_e426_419e_8176_b95193766eb1__field_index')
    #
    # drop_collection_by_class_name('datacard_datasource__050bf967_f1c0_4d2b_99d8_c0da6bb423ed')
    # drop_collection_by_class_name('datacard_datasource__59d688b2_e426_419e_8176_b95193766eb1__field_index')
