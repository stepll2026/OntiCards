"""
@Data: 2026-04-29
@Description: 清理 datacards_datasource 和 user_datasource_schemas 中重复的数据
              1. 找出 datacards_datasource 中重复的 doc_id
              2. 删除所有重复 doc_id 的 datacards 记录
              3. 同时删除 user_datasource_schemas 中对应的重复记录

@关联关系:
  - datacards_datasource.doc_id = user_datasource_schemas.id
  - 一个 doc_id 应该只对应一条 datacard 记录

@Usage:
    python clean_duplicate_datacards.py --mode preview   # 仅预览
    python clean_duplicate_datacards.py --mode execute   # 执行清理
"""

import argparse
import sys
import os
from contextlib import contextmanager
from collections import defaultdict

# ========================================
# 配置信息
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
WEAVIATE_URL = "http://27.43.110.184:8080"
WEAVIATE_GRPC_PORT = 50051

# 数据源ID（可选）- 对应 datasource_infos 表中的 id
# 留空则清理所有数据源中的重复记录，指定则只清理该数据源
DATASOURCE_ID = "c1027311-1395-4f0d-b5b3-88b97e72a6ee"

# 用户的向量库 class 名称（可选）
# 格式通常是: datacard_datasource__{user_id}
# 如果为空，脚本会尝试根据 user_id 自动构建
WEAVIATE_CLASS_NAME = "datacard_datasource__2f0ed815_f921_414c_bad1_53bed8f48287"

# DRY_RUN 控制执行模式:
#   True  = 仅预览（不会删除任何数据）
#   False = 执行真正的删除操作
DRY_RUN = False

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
# 向量库客户端
# ========================================

from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams


@contextmanager
def weaviate_client_local():
    """向量库上下文管理器"""
    client = WeaviateClient(
        connection_params=ConnectionParams.from_url(
            url=WEAVIATE_URL,
            grpc_port=WEAVIATE_GRPC_PORT
        )
    )
    client.connect()
    try:
        yield client
    finally:
        client.close()


def delete_vector_by_uuid(uuid_str: str, class_name: str) -> bool:
    """根据 UUID 删除向量库中的记录"""
    with weaviate_client_local() as client:
        if not client.collections.exists(class_name):
            return False
        collection = client.collections.get(class_name)
        collection.data.delete_by_id(uuid_str)
        return True


# ========================================
# 清理逻辑
# ========================================


def find_duplicate_doc_ids(conn, datasource_id: str = None) -> dict:
    """
    找出 datacards_datasource 中重复的 doc_id
    Args:
        conn: 数据库连接
        datasource_id: 可选，指定数据源ID进行过滤
    返回: {
        'doc_id': [record1, record2, ...],  # 按 created_at 排序
        ...
    }
    """
    # 查询所有 datacards，按 doc_id 分组，按 created_at 排序
    if datasource_id:
        sql = '''
            SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
                   dc.table_name, dc.created_at, dc.user_id::text, dc.card_data
            FROM datacards_datasource dc
            WHERE dc.datasource_id = %s
            ORDER BY dc.doc_id, dc.created_at ASC
        '''
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (datasource_id,))
            all_records = list(cur.fetchall())
    else:
        sql = '''
            SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
                   dc.table_name, dc.created_at, dc.user_id::text, dc.card_data
            FROM datacards_datasource dc
            ORDER BY dc.doc_id, dc.created_at ASC
        '''
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            all_records = list(cur.fetchall())

    # 按 doc_id 分组
    doc_id_groups = defaultdict(list)
    for record in all_records:
        doc_id = str(record['doc_id']) if record['doc_id'] else ""
        doc_id_groups[doc_id].append(dict(record))

    # 筛选出重复的 doc_id
    duplicates = {k: v for k, v in doc_id_groups.items() if len(v) > 1}

    return duplicates


def find_orphan_schemas(conn) -> list:
    """
    找出 user_datasource_schemas 中孤立的记录
    即: 记录存在于 schema 中，但 datacards_datasource 中没有对应的 doc_id
    """
    sql = '''
        SELECT uds.id::text, uds.connect_info, uds.table_name, uds.user_id::text,
               uds.created_at
        FROM user_datasource_schemas uds
        WHERE NOT EXISTS (
            SELECT 1 FROM datacards_datasource dc
            WHERE dc.doc_id::text = uds.id::text
        )
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def print_duplicate_report(duplicates: dict):
    """打印重复数据报告"""
    if not duplicates:
        print("\n[结果] 没有发现重复的 doc_id")
        return

    total_records = sum(len(v) for v in duplicates.values())
    affected_doc_ids = len(duplicates)

    print(f"\n{'='*120}")
    print(f"# 重复数据报告")
    print(f"{'='*120}")
    print(f"# 重复的 doc_id 数量: {affected_doc_ids}")
    print(f"# 涉及删除的 datacards 记录总数: {total_records}")
    print(f"# 涉及删除的 schemas 记录数: {affected_doc_ids}")
    print(f"{'='*120}\n")

    # 打印详情表格
    print(f"\n{'='*120}")
    print(f"重复数据详情 (每个 doc_id 显示前 5 条记录)")
    print(f"{'='*120}")
    print(f"{'序号':<6} {'doc_id':<42} {'记录ID':<10} {'w_uuid':<42} {'创建时间':<25}")
    print(f"{'-'*120}")

    idx = 0
    for doc_id, records in list(duplicates.items())[:20]:
        for record in records:
            doc_id_display = f"{doc_id[:40]}..." if len(doc_id) > 40 else doc_id
            w_uuid = str(record.get('w_uuid', ''))[:40]
            created_at = str(record.get('created_at', ''))[:23]
            record_id = str(record.get('id', ''))[:8]
            print(f"{idx+1:<6} {doc_id_display:<42} {record_id:<10} {w_uuid:<42} {created_at:<25} [删除]")
            idx += 1
        print(f"{'-'*120}")

    if len(duplicates) > 20:
        print(f"... 还有 {len(duplicates) - 20} 个重复的 doc_id 未显示")
    print(f"\n{'='*120}\n")


def print_orphan_report(orphan_schemas: list):
    """打印孤立 schema 报告"""
    if not orphan_schemas:
        print("\n[结果] 没有发现孤立的 schema 记录")
        return

    print(f"\n{'='*120}")
    print(f"# 孤立 schema 报告")
    print(f"{'='*120}")
    print(f"# 孤立的 schema 记录数: {len(orphan_schemas)}")
    print(f"{'='*120}\n")

    # 打印详情
    print(f"{'='*120}")
    print(f"孤立 schema 详情 (最多显示 50 条)")
    print(f"{'='*120}")
    print(f"{'序号':<6} {'schema_id':<42} {'user_id':<42} {'表名':<30}")
    print(f"{'-'*120}")

    for i, schema in enumerate(orphan_schemas[:50]):
        schema_id = str(schema['id'])[:40]
        user_id = str(schema['user_id'])[:40]
        table_name = str(schema.get('table_name', ''))[:28]
        print(f"{i+1:<6} {schema_id:<42} {user_id:<42} {table_name:<30}")

    if len(orphan_schemas) > 50:
        print(f"... 还有 {len(orphan_schemas) - 50} 条记录未显示")
    print(f"{'='*120}\n")


def delete_duplicate_datacards(conn, duplicates: dict, dry_run: bool = True) -> dict:
    """
    删除重复的 datacard 记录，删除每个 doc_id 的所有记录
    """
    # 收集要删除的记录（每个 doc_id 的所有记录）
    records_to_delete = []
    for doc_id, records in duplicates.items():
        for record in records:
            records_to_delete.append({
                'id': record['id'],
                'w_uuid': record.get('w_uuid'),
                'doc_id': doc_id,
                'user_id': record.get('user_id')
            })

    if not records_to_delete:
        return {"deleted": 0, "skipped": 0, "failed": 0, "affected_schemas": 0}

    if not records_to_delete:
        return {"deleted": 0, "skipped": 0, "failed": 0}

    print(f"\n{'='*120}")
    print(f"[{'DRY RUN - ' if dry_run else ''}删除重复 datacards]")
    print(f"{'='*120}")
    print(f"# 待删除记录数: {len(records_to_delete)}")
    print(f"{'='*120}\n")

    if dry_run:
        print("[预览] 以下记录将被删除:")
        for i, record in enumerate(records_to_delete[:20]):
            print(f"  {i+1}. id={record['id']}, doc_id={record['doc_id'][:40]}..., w_uuid={str(record.get('w_uuid') or '')[:40]}")
        if len(records_to_delete) > 20:
            print(f"  ... 还有 {len(records_to_delete) - 20} 条记录未显示")
        return {"deleted": 0, "skipped": 0, "failed": 0, "dry_run": True}

    # 执行删除
    deleted_count = 0
    failed_count = 0

    for record in records_to_delete:
        try:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM datacards_datasource WHERE id = %s', (record['id'],))
            deleted_count += 1
        except Exception as e:
            print(f"[DB ERROR] 删除记录 {record['id']} 失败: {e}")
            failed_count += 1

    try:
        conn.commit()
        print(f"[数据库删除] 成功删除 {deleted_count} 条记录")
    except Exception as e:
        conn.rollback()
        print(f"[数据库删除] 提交失败: {e}")
        failed_count += deleted_count
        deleted_count = 0

    return {"deleted": deleted_count, "skipped": 0, "failed": failed_count}


def delete_orphan_schemas(conn, orphan_schemas: list, dry_run: bool = True, is_doc_ids: bool = False) -> dict:
    """
    删除孤立的 schema 记录

    Args:
        conn: 数据库连接
        orphan_schemas: 孤立记录列表 或 doc_id 列表
        dry_run: 是否仅预览
        is_doc_ids: orphan_schemas 是否是 doc_id 列表
    """
    if not orphan_schemas:
        return {"deleted": 0, "skipped": 0, "failed": 0}

    # 打印详情
    print(f"\n{'='*120}")
    print(f"[{'DRY RUN - ' if dry_run else ''}删除 schemas]")
    print(f"{'='*120}")
    print(f"# 待删除记录数: {len(orphan_schemas)}")
    print(f"{'='*120}\n")

    if dry_run:
        print("[预览] 以下 schema 记录将被删除:")
        for i, item in enumerate(orphan_schemas[:20]):
            if is_doc_ids:
                print(f"  {i+1}. id={item}")
            else:
                print(f"  {i+1}. id={item['id']}, table_name={item.get('table_name', '')}")
        if len(orphan_schemas) > 20:
            print(f"  ... 还有 {len(orphan_schemas) - 20} 条记录未显示")
        return {"deleted": 0, "skipped": 0, "failed": 0, "dry_run": True}

    # 执行删除
    deleted_count = 0
    failed_count = 0

    if is_doc_ids:
        # 直接删除 doc_id 对应的 schema 记录
        for doc_id in orphan_schemas:
            try:
                with conn.cursor() as cur:
                    # doc_id 就是 schema 的 id
                    cur.execute('DELETE FROM user_datasource_schemas WHERE id = %s', (doc_id,))
                deleted_count += 1
            except Exception as e:
                print(f"[DB ERROR] 删除 schema {doc_id} 失败: {e}")
                failed_count += 1
    else:
        for schema in orphan_schemas:
            try:
                with conn.cursor() as cur:
                    cur.execute('DELETE FROM user_datasource_schemas WHERE id = %s', (schema['id'],))
                deleted_count += 1
            except Exception as e:
                print(f"[DB ERROR] 删除 schema {schema['id']} 失败: {e}")
                failed_count += 1

    try:
        conn.commit()
        print(f"[数据库删除] 成功删除 {deleted_count} 条 schema 记录")
    except Exception as e:
        conn.rollback()
        print(f"[数据库删除] 提交失败: {e}")
        failed_count += deleted_count
        deleted_count = 0

    return {"deleted": deleted_count, "skipped": 0, "failed": failed_count}


def delete_vectors_for_records(records: list, class_name: str = None) -> dict:
    """
    从向量库中删除记录
    如果 class_name 为 None，会尝试获取用户对应的 class name
    """
    if not records:
        return {"deleted": 0, "failed": 0, "skipped": 0}

    print(f"\n{'='*120}")
    print(f"[向量库清理]")
    print(f"{'='*120}")
    print(f"# 待删除记录数: {len(records)}")
    print(f"{'='*120}\n")

    deleted_count = 0
    failed_count = 0
    skipped_count = 0

    for record in records:
        w_uuid = record.get('w_uuid')
        if not w_uuid:
            skipped_count += 1
            continue

        try:
            # 如果没有指定 class_name，尝试获取用户的 class name
            target_class = class_name
            if not target_class:
                user_id = record.get('user_id')
                if user_id:
                    target_class = f"datacard_datasource__{user_id.replace('-', '_')}"
                else:
                    skipped_count += 1
                    continue

            delete_vector_by_uuid(str(w_uuid), target_class)
            deleted_count += 1
        except Exception as e:
            print(f"[向量库删除] 删除失败 w_uuid={w_uuid}: {e}")
            failed_count += 1

    return {"deleted": deleted_count, "failed": failed_count, "skipped": skipped_count}


# ========================================
# 主入口
# ========================================

def main():
    parser = argparse.ArgumentParser(description='清理重复的 datacard 数据')
    parser.add_argument(
        '--mode',
        choices=['preview', 'execute'],
        default='preview',
        help='preview: 仅预览; execute: 执行清理'
    )
    parser.add_argument(
        '--class-name',
        default=None,
        help='向量库 class name (可选)'
    )
    args = parser.parse_args()

    # 使用配置文件中的 DRY_RUN 控制执行模式
    dry_run = DRY_RUN
    class_name = args.class_name or WEAVIATE_CLASS_NAME
    datasource_id = DATASOURCE_ID

    print(f"""
    ========================================
    清理重复 datacard 数据工具
    ========================================

    运行模式: {'仅预览（PREVIEW）' if dry_run else '执行删除（EXECUTE）'}
    数据源ID: {datasource_id or '所有数据源'}
    向量库Class: {class_name or '自动获取'}

    清理策略:
      - 删除 datacards_datasource 中所有重复 doc_id 的记录
      - 删除 user_datasource_schemas 中对应的重复 doc_id 记录

    ========================================
    """)

    conn = get_db_connection()
    try:
        # 1. 查找重复的 doc_id
        print("\n[步骤 1/4] 分析 datacards_datasource 表中的重复数据...")
        duplicates = find_duplicate_doc_ids(conn, datasource_id)

        if duplicates:
            print_duplicate_report(duplicates)
        else:
            print("\n[结果] datacards_datasource 表中没有重复的 doc_id")

        # 如果没有脏数据，直接退出
        if not duplicates:
            print("\n[完成] 没有发现需要清理的数据")
            return

        # 收集要删除的所有记录
        records_to_delete = []
        doc_ids_to_delete = set()
        for doc_id, records in duplicates.items():
            doc_ids_to_delete.add(doc_id)
            for record in records:
                records_to_delete.append({
                    'id': record['id'],
                    'w_uuid': record.get('w_uuid'),
                    'doc_id': doc_id,
                    'user_id': record.get('user_id')
                })

        # 2. 删除重复的 datacards
        print("\n[步骤 2/4] 删除重复的 datacards 记录...")
        datacard_result = delete_duplicate_datacards(conn, duplicates, dry_run)

        # 3. 删除 user_datasource_schemas 中对应的记录
        print("\n[步骤 3/4] 删除 user_datasource_schemas 中对应的重复记录...")
        schema_result = delete_orphan_schemas(conn, list(doc_ids_to_delete), dry_run, is_doc_ids=True)

        # 4. 删除向量库中的记录
        if not dry_run and records_to_delete:
            print("\n[步骤 4/4] 清理向量库中的重复记录...")
            delete_vectors_for_records(records_to_delete, class_name)

        # 总结
        print(f"\n{'='*120}")
        print(f"# 执行结果汇总")
        print(f"{'='*120}")
        print(f"# 运行模式: {'预览（未执行删除）' if dry_run else '已执行删除'}")
        print(f"#")
        print(f"# datacards_datasource 重复记录:")
        print(f"#   - 发现重复组数: {len(duplicates)}")
        print(f"#   - 待删除记录数: {len(records_to_delete)}")
        print(f"#   - 实际删除数: {datacard_result.get('deleted', 0)}")
        print(f"#")
        print(f"# user_datasource_schemas 重复记录:")
        print(f"#   - 待删除记录数: {len(doc_ids_to_delete)}")
        print(f"#   - 实际删除数: {schema_result.get('deleted', 0)}")
        print(f"{'='*120}\n")

        if dry_run:
            print("[提示] 如需执行删除，请添加 --mode execute 参数")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
