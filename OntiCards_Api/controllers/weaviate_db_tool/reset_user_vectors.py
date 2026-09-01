"""
@Data: 2026-04-29
@Description: 重置用户的向量数据(当向量库中有脏数据时，清空向量库，随后将该用户的数据库的数据卡片重新入向量库，最后更新数据库中的数据卡片记录的w_uuid字段)
              1. 清空用户向量库 class_name 下的所有向量记录
              2. 根据 user_id 从 datacards_datasource 表获取所有记录
              3. 重新入库并更新 w_uuid

@Usage:
    python reset_user_vectors.py
"""

import json
import sys
import os
from contextlib import contextmanager

# ========================================
# 配置信息（请修改以下配置）
# ========================================

# 数据库连接配置
DB_CONFIG = {
    "host": "27.43.110.184",
    "port": 55432,
    "database": "prod-ontiCards",
    "user": "postgres",
    "password": "master_ds123",
}

# 向量库配置
WEAVIATE_URL = "http://172.16.1.7:8080"
WEAVIATE_GRPC_PORT = 50051

# 用户ID（必填）
USER_ID = "2f0ed815-f921-414c-bad1-53bed8f48287"

# 用户的向量库 class 名称（必填）
# 格式: datacard_datasource__{user_id中的横线替换为下划线}
WEAVIATE_CLASS_NAME = "datacard_datasource__2f0ed815_f921_414c_bad1_53bed8f48287"

# DRY_RUN 控制执行模式:
#   True  = 仅预览（不会删除/入库任何数据）
#   False = 执行真正的操作
DRY_RUN = False

# ========================================
# Flask 应用上下文（用于 qwen_llm_embeddings）
# ========================================

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app import create_app

app = create_app()

# ========================================
# 初始化数据库连接
# ========================================

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )


# ========================================
# 初始化向量库连接
# ========================================

import weaviate
from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams
from controllers.agents.qwen_embedding.embedding_api import qwen_llm_embeddings


def get_weaviate_client() -> WeaviateClient:
    """获取 Weaviate 客户端"""
    return weaviate.connect_to_custom(
        http_host=WEAVIATE_URL.replace("http://", "").split(":")[0],
        http_port=int(WEAVIATE_URL.split(":")[-1]) if ":" in WEAVIATE_URL else 8080,
        http_secure=False,
        grpc_host=WEAVIATE_URL.replace("http://", "").split(":")[0],
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=False,
    )


def _build_enhanced_text_for_embedding(data_card_obj: dict, abstract: str) -> str:
    """构建增强的文本用于向量化"""
    parts = [abstract] if abstract else []

    doc_info = data_card_obj.get("DocInfo", {})
    sqlmeta = data_card_obj.get("SQLMeta", {})

    table_name = sqlmeta.get("table", "") or doc_info.get("table_name", "")
    database_name = doc_info.get("database_name", "")

    if table_name:
        parts.append(f"表名: {table_name}")
    if database_name:
        parts.append(f"数据库: {database_name}")

    columns = sqlmeta.get("columns", []) or data_card_obj.get("Columns", [])
    if columns:
        field_info = []
        for col in columns[:20]:
            col_name = col.get("name", "") or col.get("column_name", "")
            col_comment = col.get("comment", "")
            col_type = col.get("type", "")

            if col_name:
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

    tags = data_card_obj.get("Tags", [])
    if tags:
        parts.append(f"标签: {', '.join(tags)}")

    return " | ".join(filter(None, parts))


# ========================================
# 核心功能
# ========================================


def delete_all_vectors_in_class(class_name: str) -> int:
    """
    删除向量库中指定 class 的所有向量记录
    返回删除数量
    """
    if DRY_RUN:
        print(f"[DRY RUN] 跳过删除向量库中的记录")
        return 0

    client = get_weaviate_client()
    try:
        collection = client.collections.get(class_name)
        # 获取总数量
        total = collection.aggregate.over_all(total_count=True).total_count
        print(f"[向量库] class={class_name} 共有 {total} 条记录待删除")

        if total == 0:
            return 0

        # 分批删除
        deleted = 0
        batch_size = 1000
        while True:
            # 获取一批数据
            results = collection.query.fetch_objects(limit=batch_size).objects
            if not results:
                break

            # 提取 UUID
            uuids = [obj.uuid for obj in results]

            # 批量删除
            for uuid in uuids:
                collection.data.delete_by_id(uuid)
                deleted += 1

            print(f"[向量库] 已删除 {deleted}/{total} 条记录")
            client.close()
            client = get_weaviate_client()
            collection = client.collections.get(class_name)

        return deleted
    finally:
        client.close()


def get_user_datacards(conn, user_id: str) -> list:
    """获取用户的所有 datacards 记录"""
    sql = '''
        SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
               dc.table_name, dc.created_at, dc.user_id::text, dc.card_data
        FROM datacards_datasource dc
        WHERE dc.user_id = %s
        ORDER BY dc.created_at ASC
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (user_id,))
        return [dict(row) for row in cur.fetchall()]


def reimport_datacard_to_vector(card_record: dict, class_name: str, conn) -> str:
    """
    重新入库单条 datacard 到向量库
    返回新的 w_uuid
    """
    card_data = card_record.get('card_data')

    # 解析 card_data
    if isinstance(card_data, str):
        data_card_obj = json.loads(card_data)
    else:
        data_card_obj = card_data

    if not data_card_obj:
        raise ValueError(f"card_data 为空或解析失败")

    doc_id = data_card_obj.get("DocInfo", {}).get("doc_id")
    abstract = data_card_obj.get("Abstract", "")
    datasource_id = data_card_obj.get("DocInfo", {}).get("datasource_id")

    data_object = {
        "doc_id": doc_id,
        "abstract": abstract,
        "datasource_id": str(datasource_id) if datasource_id else ""
    }

    # 构建向量化文本
    enhanced_text = _build_enhanced_text_for_embedding(data_card_obj, abstract)

    if DRY_RUN:
        print(f"[DRY RUN] 模拟入库: doc_id={doc_id}")
        return "dry_run_uuid"

    # 生成向量
    vector = qwen_llm_embeddings(enhanced_text)

    client = get_weaviate_client()
    try:
        collection = client.collections.get(class_name)
        new_uuid = collection.data.insert(data_object, vector=vector)
        print(f"[向量库] 入库成功: doc_id={doc_id} uuid={new_uuid}")
        return str(new_uuid)
    finally:
        client.close()


def update_w_uuid(conn, card_id: int, new_w_uuid: str):
    """更新数据库中的 w_uuid"""
    sql = "UPDATE datacards_datasource SET w_uuid = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (new_w_uuid, card_id))
    conn.commit()


# ========================================
# 主入口
# ========================================

def main():
    print(f"""
    ========================================
    重置用户向量数据工具
    ========================================

    用户ID: {USER_ID}
    向量库Class: {WEAVIATE_CLASS_NAME}
    运行模式: {'仅预览（DRY RUN）' if DRY_RUN else '执行操作（EXECUTE）'}

    操作步骤:
      1. 清空向量库 class_name 下的所有记录
      2. 查询用户的所有 datacards 记录
      3. 重新入库并更新 w_uuid

    ========================================
    """)

    # 1. 清空向量库
    print("\n[步骤 1/3] 清空向量库...")
    deleted_count = delete_all_vectors_in_class(WEAVIATE_CLASS_NAME)
    print(f"[结果] 向量库已清空，删除 {deleted_count} 条记录")

    # 2. 获取用户的 datacards
    print(f"\n[步骤 2/3] 查询用户 datacards (user_id={USER_ID})...")
    conn = get_db_connection()
    try:
        datacards = get_user_datacards(conn, USER_ID)
        print(f"[结果] 共查询到 {len(datacards)} 条 datacards 记录")

        if not datacards:
            print("\n[完成] 没有找到需要重置的 datacards")
            return

        # 3. 重新入库（需要 Flask 应用上下文）
        print(f"\n[步骤 3/3] 重新入库并更新 w_uuid...")

        def do_reimport():
            success_count = 0
            failed_count = 0

            for i, card in enumerate(datacards, 1):
                try:
                    if DRY_RUN:
                        print(f"[{i}/{len(datacards)}] DRY RUN: 模拟入库 doc_id={card.get('doc_id')}")
                        success_count += 1
                        continue

                    # 重新入库
                    new_uuid = reimport_datacard_to_vector(card, WEAVIATE_CLASS_NAME, conn)

                    # 更新数据库
                    update_w_uuid(conn, card['id'], new_uuid)

                    success_count += 1

                    if i % 10 == 0:
                        print(f"[进度] 已处理 {i}/{len(datacards)} 条记录")

                except Exception as e:
                    failed_count += 1
                    print(f"[错误] 入库失败 doc_id={card.get('doc_id')}: {e}")

            return success_count, failed_count

        # 在 Flask 应用上下文中执行入库操作
        with app.app_context():
            success_count, failed_count = do_reimport()

    finally:
        conn.close()

    # 输出结果汇总
    print(f"""
    ========================================
    # 执行结果汇总
    ========================================
    # 运行模式: {'预览（DRY RUN）' if DRY_RUN else '已执行'}
    #
    # 向量库:
    #   - 删除记录数: {deleted_count}
    #
    # 数据库 datacards_datasource:
    #   - 总记录数: {len(datacards) if 'datacards' in dir() else 0}
    #   - 成功入库: {success_count}
    #   - 失败数量: {failed_count}
    ========================================
    """)

    if DRY_RUN:
        print("[提示] 如需执行操作，请将 DRY_RUN 设置为 False")


if __name__ == "__main__":
    main()
