"""
 @File: datacard_generator.py
 @Description: 数据卡片生成
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 11:48
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, Dict, Any

from flask import current_app

from controllers.agents.qwen import llm_utils
from controllers.datacard.data_card_db_api import add_data_card
from controllers.weaviate_db_tool.weaviate_api import add_vector
from extensions.ext_database import db
from models.user_datasource_schema import UserDatasourceSchema
from models.datacards_datasource import DataCardDataSource
from models.prompt_config import prompt_manager
from core.connect_info_encryptor import get_connect_info_hash


def enhance_column_comments_with_sampling(
    columns: list,
    sampling_analysis_result: dict,
    original_columns: list = None
) -> list:
    """
    使用采样分析结果填充缺失的字段注释

    规则：
    - 原有注释的字段：保持不变
    - 缺失注释的字段：根据采样分析推断业务含义 + 示例数据

    注释格式示例：
    - 枚举型："VIP等级，例如：0=非VIP, 1=铜牌, 2=银牌"
    - 数值型："登录次数，例如：1 ~ 1205 次"
    - 日期型："最后登录时间，例如：2024-01-15 10:30:00"
    - 文本型："用户昵称，例如：张三、李四、王五"
    - 敏感字段："敏感字段"

    Args:
        columns: 增强后的字段列表（用于更新）
        sampling_analysis_result: 采样分析结果
        original_columns: 原始字段列表（包含原始注释信息）

    Returns:
        增强后的字段列表
    """
    if not sampling_analysis_result:
        return columns

    # 建立原始注释的查找表
    original_comments = {}
    if original_columns:
        for col in original_columns:
            name = col.get('name', '')
            comment = col.get('comment', '') or ''
            original_comments[name] = comment

    # 获取敏感字段列表和非敏感字段分析结果
    sensitive_fields = sampling_analysis_result.get('sensitive_fields', [])
    sensitive_field_names = [f['name'] for f in sensitive_fields]
    non_sensitive_fields = sampling_analysis_result.get('non_sensitive_fields', {})

    enhanced_columns = []
    for col in columns:
        col_name = col.get('name')
        col_copy = col.copy()
        original_comment = original_comments.get(col_name, '')

        # 如果原有注释，保持不变
        if original_comment.strip():
            enhanced_columns.append(col_copy)
            continue

        # 缺失注释的字段，根据采样数据推断并填充
        # 敏感字段：只填类型说明
        if col_name in sensitive_field_names:
            col_copy['comment'] = "敏感字段"
            enhanced_columns.append(col_copy)
            continue

        # 非敏感字段：根据类型推断注释并拼接示例
        if col_name in non_sensitive_fields:
            analysis = non_sensitive_fields[col_name]
            category = analysis.get('category', 'text')
            sample_display = analysis.get('sample_display', '')
            suggested_comment = analysis.get('suggested_comment', '')

            # 拼接注释：推断的注释 + 示例数据
            if suggested_comment and sample_display:
                # 根据类型选择示例前缀
                if category == 'enum':
                    col_copy['comment'] = f"{suggested_comment}，枚举值：{sample_display}"
                elif category == 'numeric':
                    col_copy['comment'] = f"{suggested_comment}，例如：{sample_display}"
                elif category == 'date':
                    col_copy['comment'] = f"{suggested_comment}，例如：{sample_display}"
                else:
                    col_copy['comment'] = f"{suggested_comment}，例如：{sample_display}"
            elif suggested_comment:
                col_copy['comment'] = suggested_comment
            elif sample_display:
                # 没有推断出注释，但有采样数据
                if category == 'enum':
                    col_copy['comment'] = f"枚举值：{sample_display}"
                elif category == 'numeric':
                    col_copy['comment'] = f"数值，例如：{sample_display}"
                elif category == 'date':
                    col_copy['comment'] = f"日期，例如：{sample_display}"
                else:
                    col_copy['comment'] = f"文本，例如：{sample_display}"
            else:
                col_copy['comment'] = "数据字段"
        else:
            col_copy['comment'] = "数据字段"

        enhanced_columns.append(col_copy)

    return enhanced_columns


def create_llm_prompt(
    table_info: dict,
    all_tables_schema: dict,
    sampling_analysis_result: dict = None
) -> str:
    """
    为单个表创建高度优化的 LLM Prompt。

    Args:
        table_info (dict): 当前要生成卡片的表的 schema 信息。
        all_tables_schema (dict): 整个数据库的完整 schema，用于提供上下文。
        sampling_analysis_result (dict, optional): 采样分析结果，包含敏感字段识别和字段特征分析。

    Returns:
        str: 用于 LLM 调用的 Prompt 字符串。
    """
    # 为了上下文简洁，可以只提供表名和关系的摘要
    schema_summary = {
        "database_type": all_tables_schema.get("database_type"),
        "tables": [
            {
                "table_name": t.get("table_name"),
                "primary_keys": t.get("primary_keys"),
                "foreign_keys": [
                    {
                        "columns": fk.get("columns"),
                        "referenced_table": fk.get("referenced_table"),
                        "referenced_columns": fk.get("referenced_columns"),
                    } for fk in t.get("foreign_keys", [])
                ]
            } for t in all_tables_schema.get("tables", [])
        ]
    }

    # 优先从数据库读取提示词，fallback到文件
    prompt_file_name = "datacard_generate_prompt.txt"
    prompt_template = prompt_manager.get_prompt(prompt_file_name)

    if not prompt_template:
        # Fallback 到文件（并自动同步到数据库）
        from pathlib import Path
        prompt_path = Path(__file__).resolve().parents[2] / "libs" / "prompt" / "datacard_generate" / "datacard_generate_prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
            prompt_manager.set_prompt(prompt_file_name, prompt_template)
        else:
            raise FileNotFoundError(f"未找到提示词文件: {prompt_file_name}")

    # 替换占位符
    prompt = (
        prompt_template
        .replace("{{database_schema_summary}}", json.dumps(schema_summary, indent=2, ensure_ascii=False))
        .replace("{{table_name}}", table_info.get("table_name", ""))
        .replace("{{table_schema_detail}}", json.dumps(table_info, indent=2, ensure_ascii=False))
    )

    # 如果提供了采样分析结果，替换采样分析占位符
    if sampling_analysis_result:
        prompt = prompt.replace(
            "{{sampling_analysis_result}}",
            json.dumps(sampling_analysis_result, ensure_ascii=False, indent=2)
        )
    else:
        # 没有采样结果时使用空字符串
        prompt = prompt.replace("{{sampling_analysis_result}}", "")

    return prompt


def clean_llm_json_response(response_str: str) -> str:
    """
    清理 LLM 可能返回的 Markdown 代码块，提取出纯净的 JSON 字符串。

    Args:
        response_str: LLM 的原始输出字符串。

    Returns:
        清理后的 JSON 字符串。
    """
    # 使用正则表达式查找被 ```json ... ``` 或 ``` ... ``` 包裹的 JSON
    # re.DOTALL 模式让 . 可以匹配换行符
    match = re.search(r'```(json)?\s*(\{.*?\})\s*```', response_str, re.DOTALL)

    if match:
        # 如果匹配成功，返回捕获的组，即花括号内的内容
        return match.group(2)

    # 如果没有找到 Markdown 块，则假设返回的就是纯 JSON，去除首尾可能存在的空格
    return response_str.strip()


# 基于表结构生成数据卡片
def generate_datacards_for_schema(schema: dict, user_id: str, connect_info: str, connect_name: str | None = None,
                                  datasource_id: str | None = None,
                                  request_id: str | None = None, weaviate_class_name: str | None = None,) -> list:
    """
    基于表结构生成数据卡片

    Args:
        schema: 数据库结构信息
        user_id: 用户ID
        connect_info: 连接信息
        connect_name: 连接名称
        datasource_id: 数据源ID（新增，用于快速查询）
        request_id: 请求ID（用于取消检查）
        weaviate_class_name: 用户的向量检索空间class名
    Returns:
        生成的数据卡片列表
    """
    # 导入取消状态管理器和 schema 过滤器
    from controllers.datasource.database_schema_extractor import request_status_manager, _add_schema_filter
    from models.datasource_infos import DatasourceInfo

    # 在函数开始时检查是否已取消
    if request_id and request_status_manager.is_cancelled(request_id):
        print(f"[CANCELLED] 数据卡片生成在开始前被取消 (request_id: {request_id})")
        return []

    all_data_cards = []
    # 同时处理 tables 和 views（合并处理，因为它们都存储在 UserDatasourceSchema 中）
    tables = schema.get("tables", []) + schema.get("views", [])

    # 兜底：未传则按 user_id + connect_info + schema_name 回查
    if not connect_name or not datasource_id:
        try:
            schema_name_param = schema.get("schema_name")
            db_type_for_lookup = schema.get("database_type", "").lower()
            # 使用 connect_info_hash 进行稳定匹配（因为加密值每次不同）
            connect_info_hash = get_connect_info_hash(connect_info)

            # 按 (connect_info_hash, schema_name) 精确查找
            if _has_schema_dim(db_type_for_lookup) and schema_name_param:
                datasource = (
                    db.session.query(DatasourceInfo)
                    .filter_by(user_id=str(user_id), connect_info_hash=connect_info_hash, schema_name=schema_name_param)
                    .first()
                )
            else:
                datasource = (
                    db.session.query(DatasourceInfo)
                    .filter_by(user_id=str(user_id), connect_info_hash=connect_info_hash)
                    .first()
                )
            
            if datasource:
                if not connect_name:
                    connect_name = datasource.connect_name
                if not datasource_id:
                    datasource_id = str(datasource.id)
        except Exception as e:
            print(f"[WARN] 查询数据源信息失败: {e}")
            pass

    if not tables:
        print("[WARN] Schema中没有找到任何表或视图。")
        return []

    # 再次检查是否已取消
    if request_id and request_status_manager.is_cancelled(request_id):
        print(f"[CANCELLED] 数据卡片生成在处理表之前被取消 (request_id: {request_id})")
        return []

    # ===== (1) 先批量拿到 每张表 -> doc_id 映射 =====
    table_names = [t.get("table_name") for t in tables if t.get("table_name")]
    if not table_names:
        print("[WARN] tables 中没有合法的 table_name。")
        return []

    # 1) 拿每张表 -> doc_id 映射之后，立刻统一转为 str
    # 按 db_type + schema_name 分支过滤（避免同 connect_info 不同 schema 的表被串查）
    db_type_for_filter = schema.get("database_type", "").lower()
    schema_name_for_filter = schema.get("schema_name")
    # 注意：使用稳定的哈希值进行比较（因为 AES-GCM 加密每次使用随机 nonce）
    connect_info_hash = get_connect_info_hash(connect_info)

    existing_schema_query = (
        UserDatasourceSchema.query
        .with_entities(UserDatasourceSchema.table_name, UserDatasourceSchema.id)
        .filter(
            UserDatasourceSchema.user_id == user_id,
            UserDatasourceSchema.connect_info_hash == connect_info_hash,
            UserDatasourceSchema.table_name.in_(table_names)
        )
    )
    existing_schema_query = _add_schema_filter(existing_schema_query, db_type_for_filter, schema_name_for_filter)
    existing_schema_rows = existing_schema_query.all()

    # 原来：name_to_doc_id = {name: doc_id for (name, doc_id) in existing_schema_rows}
    # 改为：全部转成字符串，后续全用字符串比较/写入
    name_to_doc_id = {name: str(doc_id) for (name, doc_id) in existing_schema_rows}

    # 2) 构造候选 doc_id 列表时也用字符串
    candidate_doc_ids = [doc_id for doc_id in name_to_doc_id.values() if doc_id]  # 已是 str

    # 3) 和 DataCardDataSource 里已有的做 in_ 比较时，用字符串列表
    existing_card_doc_ids = set()
    if candidate_doc_ids:
        existing_card_doc_ids = {
            r[0] for r in (
                DataCardDataSource.query
                .with_entities(DataCardDataSource.doc_id)
                .filter(DataCardDataSource.doc_id.in_(candidate_doc_ids))  # 值为 str，列为 varchar -> OK
                .all()
            )
        }

    # 4) 生成 rs_tables 时，用字符串 doc_id 比较
    rs_tables = []
    for t in tables:
        name = t.get("table_name")
        doc_id = name_to_doc_id.get(name)  # 这里已经是 str
        if not doc_id:
            continue
        if doc_id in existing_card_doc_ids:
            continue
        rs_tables.append(t)

    # 仅用于可视化确认
    rs_table_names = [t.get("table_name") for t in rs_tables]
    print(f"[INFO] 共抽取 {len(tables)} 张表；其中已有 DataCard 的 {len(existing_card_doc_ids)} 张。")
    print(f"[INFO] 需要生成数据卡片（不存在者）的表：{rs_table_names}")

    print(f"准备为 {len(rs_tables)} 张表生成数据名片...")

    # 提前构建 table_name -> doc_id 的映射（避免在子线程中访问数据库）
    table_to_doc_id = {}
    for t in rs_tables:
        tname = t.get("table_name")
        # 从之前已经查询好的 name_to_doc_id 中获取
        doc_id = name_to_doc_id.get(tname)
        if doc_id:
            table_to_doc_id[tname] = doc_id

    # 获取当前应用实例（用于在子线程中推送应用上下文）
    app = current_app._get_current_object()

    # 并行生成 DataCard 的辅助函数
    def generate_single_datacard(table_info: dict, idx: int, doc_id_map: dict, flask_app) -> Tuple[
        Optional[dict], str, Optional[str]]:
        """
        为单张表生成数据卡片
        返回: (data_card_skeleton, table_name, doc_id)
        """
        # 在子线程中推送 Flask 应用上下文
        with flask_app.app_context():
            # 在处理每张表之前检查是否已取消
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 数据卡片生成在处理表时被取消 (request_id: {request_id})")
                return None, None, None

            table_name = table_info.get("table_name")
            print(f"[{idx + 1}/{len(rs_tables)}] 正在处理表: {table_name} ...")

            # 从预先构建的映射中获取 doc_id
            doc_id = doc_id_map.get(table_name)

            # 获取采样分析结果（可选，如果连接信息可用）
            sampling_analysis_result = None
            try:
                from controllers.datacard.datacard_sampling import sample_and_analyze
                from sqlalchemy import create_engine

                # 创建临时数据库连接进行采样
                sampling_engine = create_engine(connect_info, pool_pre_ping=True)
                with sampling_engine.connect() as sampling_conn:
                    # 获取字段列表（包含 name, type, comment 用于识别缺失注释的字段）
                    columns = table_info.get("columns", [])
                    schema_name = schema.get("schema_name")
                    db_type = schema.get("database_type", "postgresql")

                    # 创建 LLM 客户端（与 governance_api.py 保持一致）
                    class LLMWrapper:
                        def chat(self, prompt):
                            from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage
                            content, _ = qian_wen_llm_with_usage(prompt, stream_type=False)
                            return content

                    llm_client = LLMWrapper()

                    # 执行采样和分析
                    sampling_analysis_result = sample_and_analyze(
                        connection=sampling_conn,
                        db_type=db_type,
                        table=table_name,
                        schema=schema_name,
                        columns=columns,
                        llm_client=llm_client,
                        sampling_limit=100
                    )

                    # 转换为字典格式
                    sampling_analysis_result = sampling_analysis_result.to_dict()

                sampling_engine.dispose()
                print(f"  - 采样分析完成: 敏感字段 {len(sampling_analysis_result.get('sensitive_fields', []))} 个")

            except Exception as e:
                # 采样失败不影响主流程，使用空结果继续
                print(f"  [WARN] 采样分析失败: {str(e)}")
                import traceback
                traceback.print_exc()
                sampling_analysis_result = None

            data_card_skeleton = {
                "DocInfo": {
                    "doc_id": doc_id,
                    "title": f"数据表: {table_name}",
                    "source_type": "sql",
                    "publish_date": "",
                    "domain": "未分类",  # 默认值，将由LLM生成的值替换
                    "language": "zh-CN",
                    "author": "OntiCards",
                    "pages": 0,
                    "origin_url": "",
                    "connect_name": connect_name,  # 数据源名称，给前端直接显示
                    "datasource_id": datasource_id  # 新增：数据源ID，用于向量检索过滤
                },
                "Abstract": "",
                "KeyConcepts": {},
                "MongoMap": [],
                "GraphMap": {"nodes": [], "edges": []},
                "SQLMeta": {
                    "table": table_name,
                    "pk": ", ".join(table_info.get("primary_keys", [])),
                    "pk_value": None,
                    "file_path": "",
                    "checksum": "",
                    "columns": table_info.get("columns", []),
                    "foreign_keys": table_info.get("foreign_keys", [])
                },
                "Tags": []
            }

            # 创建 Prompt 时传入采样分析结果
            prompt = create_llm_prompt(table_info, schema, sampling_analysis_result)

            # 在 LLM 调用前检查是否已取消（LLM 调用耗时最长，在此之前检查可以避免浪费）
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 数据卡片生成在 LLM 调用前被取消 (table: {table_name}, request_id: {request_id})")
                return None, None, None

            print(f"  - 正在调用 LLM 为 {table_name} 生成描述...")
            try:
                # llm_call 函数内部会从数据库读取配置，无需在此处查询
                llm_response_str = llm_utils.llm_call(
                    prompt
                )

                # 在 LLM 调用后也检查一次（LLM 调用可能耗时 10-15 秒）
                if request_id:
                    is_cancelled = request_status_manager.is_cancelled(request_id)
                    print(
                        f"[DEBUG] LLM 调用后检查取消状态: table={table_name}, request_id={request_id}, is_cancelled={is_cancelled}")
                    if is_cancelled:
                        print(
                            f"[CANCELLED] 数据卡片生成在 LLM 调用后被取消 (table: {table_name}, request_id: {request_id})")
                        return None, None, None

                # 在解析前，先清洗 LLM 的返回
                cleaned_llm_str = clean_llm_json_response(llm_response_str)

                # 解析清洗后的字符串
                llm_generated_parts = json.loads(cleaned_llm_str)

                data_card_skeleton["Abstract"] = llm_generated_parts.get("Abstract", "")
                data_card_skeleton["KeyConcepts"] = llm_generated_parts.get("KeyConcepts", {})
                data_card_skeleton["Tags"] = llm_generated_parts.get("Tags", [])
                # 从LLM响应中提取Domain字段，如果没有则保持默认值"未分类"
                if "Domain" in llm_generated_parts and llm_generated_parts["Domain"]:
                    data_card_skeleton["DocInfo"]["domain"] = llm_generated_parts["Domain"]

                # 使用采样分析结果填充缺失的字段注释
                # 使用 table_info 中的原始注释来判断哪些字段缺失注释
                if sampling_analysis_result:
                    data_card_skeleton["SQLMeta"]["columns"] = enhance_column_comments_with_sampling(
                        data_card_skeleton["SQLMeta"]["columns"],
                        sampling_analysis_result,
                        table_info.get("columns", [])  # 传入原始字段列表
                    )
                    print(f"  - 缺失注释的字段已根据采样数据填充")

                print(f"  - 成功为 {table_name} 生成数据名片。")
                return data_card_skeleton, table_name, doc_id

            except json.JSONDecodeError as e:
                print(f"[ERROR] 解析JSON失败: {e}")
                return None, table_name, doc_id
            except Exception as e:
                print(f"[ERROR] 调用LLM或处理时发生未知错误: {e}")
                return None, table_name, doc_id

    # 使用线程池并行生成数据卡片（最多10个并发）
    max_workers = min(10, len(rs_tables)) if rs_tables else 1
    generated_cards = []

    if rs_tables:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务，保持索引以维持顺序
            future_to_idx = {
                executor.submit(generate_single_datacard, table_info, i, table_to_doc_id, app): i
                for i, table_info in enumerate(rs_tables)
            }

            # 按原始顺序收集结果
            results = [None] * len(rs_tables)
            cancelled_during_collection = False

            for future in as_completed(future_to_idx):
                # 在收集每个结果前检查是否已取消
                if request_id:
                    is_cancelled = request_status_manager.is_cancelled(request_id)
                    print(f"[DEBUG] 收集结果时检查取消状态: request_id={request_id}, is_cancelled={is_cancelled}")
                    if is_cancelled:
                        print(f"[CANCELLED] 在收集 LLM 结果时检测到取消 (request_id: {request_id})")
                        cancelled_during_collection = True
                        # 不再等待剩余的 future，直接跳出
                        break

                idx = future_to_idx[future]
                result = future.result()
                print(f"[DEBUG] 收集到结果: idx={idx}, result={'有数据' if result[0] else '无数据'}")
                results[idx] = result

            # 如果在收集结果时已取消，直接返回
            if cancelled_during_collection:
                print(f"[CANCELLED] 数据卡片生成被取消，已生成的结果将被丢弃 (request_id: {request_id})")
                return []

            # 处理成功生成的卡片：入向量库和数据库
            print(f"[DEBUG] 开始处理入库，共 {len(results)} 个结果")
            for data_card_skeleton, table_name, doc_id in results:
                if data_card_skeleton is None:
                    print(f"[DEBUG] 跳过空结果")
                    continue

                print(f"[DEBUG] 准备入库: table={table_name}")

                # 在入库前检查是否已取消
                if request_id:
                    is_cancelled = request_status_manager.is_cancelled(request_id)
                    print(
                        f"[DEBUG] 入库前检查取消状态: table={table_name}, request_id={request_id}, is_cancelled={is_cancelled}")
                    if is_cancelled:
                        print(f"[CANCELLED] 数据卡片生成在入库前被取消 (request_id: {request_id})")
                        print(
                            f"[INFO] 已生成但未入库的卡片数量: {len([r for r in results if r[0] is not None]) - len(generated_cards)}")
                        break

                try:
                    # 数据卡片入向量库：返回对应的uuid
                    w_uuid = add_vector(data_card_skeleton,class_name=weaviate_class_name)
                    print(f"[SUCCESS WEAVIATE] :表{table_name}的数据卡片入向量库成功！")

                    # 数据卡片入数据库（传入新增的字段）
                    add_data_card(
                        doc_id=str(doc_id),
                        w_uuid=w_uuid,
                        card_data_str=json.dumps(data_card_skeleton, default=str, ensure_ascii=False),
                        user_id=str(user_id) if user_id else None,
                        datasource_id=datasource_id,
                        table_name=table_name,
                        connect_name=connect_name
                    )
                    print(f"[SUCCESS DB] :表{table_name}的数据卡片入数据库成功！")

                    generated_cards.append(data_card_skeleton)

                except Exception as e:
                    print(f"[ERROR] 表{table_name}的数据卡片入库失败: {e}")
                    continue

    all_data_cards.extend(generated_cards)
    return all_data_cards
