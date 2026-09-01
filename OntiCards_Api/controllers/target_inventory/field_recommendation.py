"""
 @File: field_recommendation.py
 @Description: 字段推荐模块 - 为目标表字段推荐更准确的注释
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-02
 @Update: 2026-05-08 - 添加多线程并发优化支持
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from flask import current_app
from flask_login import current_user
from controllers.target_inventory.recall import rule_recall, merge_rank
from controllers.target_inventory.value_profiling import profile_field
from controllers.weaviate_db_tool.weaviate_api import search_field_entries


def recommend_field_annotations(
    target_fields: List[Dict[str, Any]],
    ref_entries: List[Dict[str, Any]],
    llm_annotations: Dict[str, str],
    topk: int = 10,
    datasource_id: str = None,
    schema_hash: str = None,
    vector_topn: int = 20,
    max_workers: int = 4
) -> Dict[str, Dict[str, Any]]:
    """
    为目标字段推荐注释

    【重要】只对LLM填充注释的字段进行推荐，原始数据库中有注释的字段不需要推荐

    Args:
        target_fields: 目标字段列表，每个字段包含 table_name, column_name, column_type, column_comment 等
        ref_entries: 参考字段条目列表（从参考表和字典文件中获取）
        llm_annotations: LLM填充的注释 {table.column: annotation}，只有在这个字典中的字段才需要推荐
        topk: 每个字段返回的最大候选数量（实际返回数量可能更少，取决于相关性）
        datasource_id: 数据源ID（用于向量召回）
        schema_hash: Schema哈希值（用于向量召回）
        vector_topn: 向量召回数量

    Returns:
        推荐结果 {table_name: {column_name: {
            "original_comment": "原始注释",
            "llm_comment": "LLM填充的注释",
            "candidates": [
                {
                    "source": "table.column" or "dict:column",
                    "comment": "推荐的注释",
                    "confidence": 0.85,
                    "reasoning": "推荐理由",
                    "source_type": "reference_table" or "dict_file" or "llm",
                    ...
                }
            ],
            "profile": {...}
        }}}
    """
    print(f"[字段推荐] 开始推荐，目标字段数: {len(target_fields)}, 参考条目数: {len(ref_entries)}, 并发线程数: {max_workers}")

    # 按表分组
    fields_by_table = {}
    for field in target_fields:
        table_name = field.get("table_name")
        if table_name not in fields_by_table:
            fields_by_table[table_name] = []
        fields_by_table[table_name].append(field)

    # 【核心修改】只对LLM填充注释的字段进行推荐
    fields_to_recommend = {}
    skipped_count = 0
    for table_name, fields in fields_by_table.items():
        for field in fields:
            column_name = field.get("column_name")
            field_key = f"{table_name}.{column_name}"
            # 只有LLM填充注释的字段才需要推荐
            if field_key in llm_annotations:
                if table_name not in fields_to_recommend:
                    fields_to_recommend[table_name] = []
                fields_to_recommend[table_name].append(field)
            else:
                skipped_count += 1

    total_to_recommend = sum(len(fields) for fields in fields_to_recommend.values())
    print(f"[字段推荐] 共 {len(target_fields)} 个字段，{total_to_recommend} 个需要推荐（LLM填充），{skipped_count} 个跳过（原始注释）")

    if total_to_recommend == 0:
        print(f"[字段推荐] 没有需要推荐的字段")
        return {}

    # 获取 user_class 和 app（需要在主线程获取，线程共享）
    # 使用安全的获取方式，避免访问 current_user 触发上下文错误
    user_class = None
    try:
        if hasattr(current_user, 'weaviate_class_name'):
            user_class = getattr(current_user, "weaviate_class_name", None)
    except RuntimeError:
        print(f"[字段推荐] ⚠️ 无法获取 current_user，上下文不可用")

    # 获取 Flask app 用于在线程中创建应用上下文
    app = None
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        print(f"[字段推荐] ⚠️ 无法获取 Flask app，上下文可能不可用")

    # 构建所有需要推荐的字段任务列表
    all_field_tasks = []
    for table_name, fields in fields_to_recommend.items():
        for field in fields:
            column_name = field.get("column_name")
            column_type = field.get("column_type")
            original_comment = field.get("column_comment") or ""
            llm_key = f"{table_name}.{column_name}"
            llm_comment_val = llm_annotations.get(llm_key, "")

            all_field_tasks.append({
                "table_name": table_name,
                "column_name": column_name,
                "column_type": column_type,
                "original_comment": original_comment,
                "llm_comment": llm_comment_val,
                "sample_values": field.get("sample_values", []),
                "profile": field.get("profile", {})
            })

    # 使用线程锁保护结果字典（因为字典赋值不是线程安全的）
    result_lock = threading.Lock()
    result = {}
    completed_count = [0]  # 使用列表以便在嵌套函数中修改

    def _recommend_single_field(task: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """处理单个字段的推荐（在线程中执行）"""
        table_name = task["table_name"]
        column_name = task["column_name"]
        column_type = task["column_type"]
        original_comment = task["original_comment"]
        llm_comment_val = task["llm_comment"]
        sample_values = task["sample_values"]

        try:
            # 1. 字段画像
            profile = profile_field(
                column_name=column_name,
                column_type=column_type,
                column_comment=original_comment or llm_comment_val,
                sample_values=sample_values
            )

            # 2. 规则召回
            rule_pool = rule_recall(column_name, ref_entries, limit=30)

            # 3. 向量召回（需要在 Flask 应用上下文中执行）
            vec_pool = []
            vector_success = False
            if datasource_id and schema_hash and user_class:
                try:
                    # 构建查询文本
                    query_text = _build_query_text(table_name, column_name, column_type, profile)

                    # 根据是否有 app 上下文决定执行方式
                    if app:
                        with app.app_context():
                            # 执行向量检索
                            vec_results = search_field_entries(
                                query_text=query_text,
                                user_class=user_class,
                                datasource_id=datasource_id,
                                schema_hash=schema_hash,
                                limit=vector_topn
                            )
                            vector_success = True
                    else:
                        # 无 app 上下文，直接执行
                        vec_results = search_field_entries(
                            query_text=query_text,
                            user_class=user_class,
                            datasource_id=datasource_id,
                            schema_hash=schema_hash,
                            limit=vector_topn
                        )
                        vector_success = True

                    # 转换为候选格式，计算向量相似度
                    for vr in vec_results:
                        distance = vr.get("distance", 1.0)
                        vector_sim = max(0.0, 1.0 - distance) if distance is not None else 0.0

                        vec_pool.append({
                            "datasource_id": vr.get("datasource_id", ""),
                            "schema_hash": vr.get("schema_hash", ""),
                            "source_type": vr.get("source_type", "table_ref"),
                            "table_name": vr.get("table_name", ""),
                            "column_name": vr.get("column_name", ""),
                            "column_type": vr.get("column_type", ""),
                            "column_comment": vr.get("column_comment", ""),
                            "vector_sim": vector_sim,
                            "name_sim": 0.0
                        })

                except Exception as e:
                    print(f"[字段推荐]   ⚠️ 向量召回失败 ({table_name}.{column_name}): {e}")

            # 4. 合并排序
            merge_result = merge_rank(rule_pool, vec_pool, profile, topk=topk)
            candidates = merge_result.get("topk", [])

            # 5. 格式化候选结果
            formatted_candidates = _format_candidates(
                table_name, column_name, column_type,
                original_comment, llm_comment_val,
                candidates, profile, topk
            )

            field_result = {
                "original_comment": original_comment,
                "llm_comment": llm_comment_val,
                "candidates": formatted_candidates,
                "profile": profile
            }

            print(f"[字段推荐]   ✓ {table_name}.{column_name}: {len(formatted_candidates)} 个候选" +
                  ("" if vector_success else " (无向量召回)"))
            return (table_name, column_name, field_result)

        except Exception as e:
            print(f"[字段推荐]   ✗ {table_name}.{column_name}: 处理失败 - {e}")
            return (table_name, column_name, {
                "original_comment": original_comment,
                "llm_comment": llm_comment_val,
                "candidates": [],
                "profile": {}
            })

    # 记录开始时间
    start_time = time.time()

    # 使用线程池并行处理所有字段
    print(f"[字段推荐] 🚀 启动 {max_workers} 个并发线程处理 {len(all_field_tasks)} 个字段...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_recommend_single_field, task): task for task in all_field_tasks}

        for future in as_completed(futures):
            try:
                table_name, column_name, field_result = future.result()
                with result_lock:
                    if table_name not in result:
                        result[table_name] = {}
                    result[table_name][column_name] = field_result
                    completed_count[0] += 1
                    # 打印进度（每完成3个或完成时）
                    if completed_count[0] % 3 == 0 or completed_count[0] == len(all_field_tasks):
                        elapsed = time.time() - start_time
                        rate = completed_count[0] / elapsed if elapsed > 0 else 0
                        print(f"[字段推荐]   📊 进度: {completed_count[0]}/{len(all_field_tasks)} ({rate:.1f} 字段/秒)")
            except Exception as e:
                task = futures[future]
                print(f"[字段推荐]   ✗ {task['table_name']}.{task['column_name']}: 任务失败 - {e}")

    elapsed_time = time.time() - start_time
    print(f"[字段推荐] ✅ 完成，共处理 {sum(len(fields) for fields in result.values())} 个字段，耗时 {elapsed_time:.2f} 秒")

    return result


def _generate_reasoning(candidate: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """
    生成推荐理由

    Args:
        candidate: 候选项
        profile: 字段画像

    Returns:
        推荐理由文本
    """
    reasons = []

    # 来源类型
    source_type = candidate.get("source_type", "reference_table")
    if source_type == "llm":
        reasons.append("由大语言模型推断生成")
    elif source_type == "dict_file":
        reasons.append("来自字典文件")
    else:
        reasons.append("来自参考表")

    # 名称相似度
    name_sim = candidate.get("name_sim", 0.0)
    if name_sim >= 0.9:
        reasons.append("字段名高度相似")
    elif name_sim >= 0.7:
        reasons.append("字段名相似")

    # 向量相似度
    vector_sim = candidate.get("vector_sim", 0.0)
    if vector_sim >= 0.8:
        reasons.append("语义高度相似")
    elif vector_sim >= 0.6:
        reasons.append("语义相似")

    # 类型匹配
    if candidate.get("type_match", 0.0) > 0:
        reasons.append("数据类型匹配")

    # 画像匹配
    profile_match = candidate.get("profile_match", 0.0)
    if profile_match >= 0.5:
        type_hint = profile.get("type_hint", "")
        if type_hint:
            reasons.append(f"字段特征匹配({type_hint})")

    return "；".join(reasons) if reasons else "综合评分推荐"


def _format_candidates(
    table_name: str,
    column_name: str,
    column_type: str,
    original_comment: str,
    llm_comment: str,
    candidates: List[Dict[str, Any]],
    profile: Dict[str, Any],
    topk: int = 10
) -> List[Dict[str, Any]]:
    """
    格式化候选结果（将LLM注释和规则/向量召回的候选合并）

    Args:
        table_name: 表名
        column_name: 字段名
        column_type: 字段类型
        original_comment: 原始注释
        llm_comment: LLM注释
        candidates: 规则/向量召回的候选列表
        profile: 字段画像
        topk: 返回的最大候选数量

    Returns:
        格式化后的候选列表
    """
    formatted_candidates = []

    # 1. 将LLM注释作为候选之一（始终作为第一个候选）
    if llm_comment:
        formatted_candidates.append({
            "source": f"llm:{table_name}.{column_name}",
            "source_type": "llm",
            "table_name": table_name,
            "column_name": column_name,
            "column_comment": llm_comment,
            "column_type": column_type,
            "confidence": 0.7,
            "reasoning": "由大语言模型推断生成（当前注释）",
            "is_current_llm": True,
            "scores": {
                "name_sim": 1.0,
                "vector_sim": 0.0,
                "profile_match": 0.5,
                "type_match": 1.0,
            }
        })

    # 2. 添加规则/向量召回的候选
    for cand in candidates:
        # 跳过置信度低于40%的候选
        if cand.get("score", 0.0) < 0.4:
            continue

        # 跳过与LLM注释完全相同的候选（避免重复）
        if llm_comment and cand.get("column_comment") == llm_comment:
            continue

        # 构建 source 字段
        source_type = cand.get("source_type", "table_ref")
        cand_table = cand.get("table_name", "")
        cand_column = cand.get("column_name", "")

        if source_type == "llm":
            source = f"llm:{cand_table}.{cand_column}"
        elif source_type == "dict" or source_type == "dict_file":
            source = f"dict:{cand_column}"
        else:
            source = f"{cand_table}.{cand_column}" if cand_table else cand_column

        formatted_candidates.append({
            "source": source,
            "source_type": source_type,
            "table_name": cand_table,
            "column_name": cand_column,
            "column_comment": cand.get("column_comment", ""),
            "column_type": cand.get("column_type", ""),
            "confidence": round(cand.get("score", 0.0), 4),
            "reasoning": _generate_reasoning(cand, profile),
            "scores": {
                "name_sim": round(cand.get("name_sim", 0.0), 4),
                "vector_sim": round(cand.get("vector_sim", 0.0), 4),
                "profile_match": round(cand.get("profile_match", 0.0), 4),
                "type_match": round(cand.get("type_match", 0.0), 4),
                "semantic_relevance": round(cand.get("semantic_relevance", 0.0), 4),
            }
        })

    # 3. 限制候选数量（LLM候选 + topk-1 个其他候选）
    if len(formatted_candidates) > topk:
        # 保留第一个（LLM候选）+ 按置信度排序的其他候选
        other_candidates = formatted_candidates[1:]
        other_candidates.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        formatted_candidates = [formatted_candidates[0]] + other_candidates[:topk-1]

    return formatted_candidates


def format_recommendations_for_display(recommendations: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    格式化推荐结果用于前端展示

    Args:
        recommendations: 推荐结果

    Returns:
        格式化后的结果
    """
    formatted = {
        "tables": [],
        "summary": {
            "total_tables": len(recommendations),
            "total_fields": sum(len(fields) for fields in recommendations.values()),
            "fields_with_candidates": 0,
            "fields_without_candidates": 0
        }
    }

    for table_name, fields in recommendations.items():
        table_data = {
            "table_name": table_name,
            "fields": []
        }

        for column_name, field_data in fields.items():
            candidates = field_data.get("candidates", [])

            if candidates:
                formatted["summary"]["fields_with_candidates"] += 1
            else:
                formatted["summary"]["fields_without_candidates"] += 1

            table_data["fields"].append({
                "column_name": column_name,
                "original_comment": field_data.get("original_comment", ""),
                "llm_comment": field_data.get("llm_comment", ""),
                "candidate_count": len(candidates),
                "top_candidate": candidates[0] if candidates else None,
                "all_candidates": candidates
            })

        formatted["tables"].append(table_data)

    return formatted


def _build_query_text(table_name: str, column_name: str, column_type: str, profile: dict) -> str:
    """
    构造规范的 query_text，用于向量召回

    Args:
        table_name: 表名
        column_name: 字段名
        column_type: 字段类型
        profile: 字段画像

    Returns:
        用于向量检索的查询文本
    """
    type_hint = profile.get("type_hint", "unknown")
    format_hint = profile.get("format_hint", "")
    top_values = profile.get("top_values", [])

    # 格式化 top_values
    top_str = ", ".join([f"{v.get('v')}({v.get('cnt')}次)" for v in top_values[:3]])

    parts = [
        f"表 {table_name}",
        f"字段 {column_name}",
        f"类型 {column_type}",
        f"画像类型 {type_hint}"
    ]

    if format_hint:
        parts.append(f"格式 {format_hint}")

    if top_str:
        parts.append(f"高频值 {top_str}")

    parts.append("目标：匹配语义相近的字段注释")

    return "。".join(parts) + "。"
