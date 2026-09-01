"""
 @File: ref_builder.py
 @Description: 参考条目构建
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 14:46
"""

from __future__ import annotations
import json
from extensions.ext_database import db
from controllers.weaviate_db_tool.weaviate_api import weaviate_client, ensure_field_index_collection_exists, _require_collection_exists
from controllers.agents.qwen_embedding.embedding_api import qwen_llm_embeddings

# 把参考表 data card 的"已注释字段"拆成 ref_entries，并写入 FieldIndex

def build_ref_entries_from_datacards(datacard_rows: list, datasource_id: str, schema_hash: str) -> list[dict]:
    """
    datacard_rows: 你从 DB 查出来的 DataCardDataSource 记录（参考表）
    产出 entries: {datasource_id, schema_hash, source_type, table_name, column_name, column_type, column_comment}
    """
    entries = []
    for row in datacard_rows:
        table_name = getattr(row, "table_name", None) or getattr(row, "table", None)
        card_data = getattr(row, "card_data", None)
        if not card_data:
            continue
        try:
            card = json.loads(row.card_data) if isinstance(row.card_data, str) else (row.card_data or {})
            table_name = ((card.get("SQLMeta") or {}).get("table") or "").strip()
        except Exception:
            continue

        cols = ((card.get("SQLMeta") or {}).get("columns") or [])
        for c in cols:
            cmt = (c.get("comment") or "").strip()
            if not cmt:
                continue
            entries.append({
                "datasource_id": datasource_id,
                "schema_hash": schema_hash,
                "source_type": "table_ref",
                "table_name": table_name,
                "column_name": c.get("name"),
                "column_type": c.get("type"),
                "column_comment": cmt,
            })
    return entries

def upsert_entries_to_field_index(entries: list[dict], user_class: str) -> int:
    """
    批量插入条目到向量索引（优化版：使用单个连接批量插入）

    Args:
        entries: 条目列表
        user_class: 用户类名

    Returns:
        插入的条目数量
    """
    if not entries:
        return 0

    # 确保集合存在
    idx_class = ensure_field_index_collection_exists(user_class)

    # 使用单个连接批量插入
    with weaviate_client() as client:
        _require_collection_exists(client, idx_class)
        collection = client.collections.get(idx_class)

        # 批量插入
        inserted_count = 0
        batch_size = 100  # 每批插入100条

        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]

            # 准备批量数据
            with collection.batch.dynamic() as batch_context:
                for entry in batch:
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

                    # 生成向量
                    vector = qwen_llm_embeddings(text_for_embed)

                    # 添加到批次
                    batch_context.add_object(
                        properties=data_object,
                        vector=vector
                    )
                    inserted_count += 1

            print(f"[FieldIndex] 批量插入进度: {inserted_count}/{len(entries)}")

    return inserted_count
