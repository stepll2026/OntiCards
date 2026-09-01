"""
@Data: 2026-04-29
@Description: 数据源脏数据清理脚本（清除某个数据源在数据库中的数据卡片脏数据）
              根据 datasource_infos -> user_datasource_schemas -> datacards_datasource 的关联关系，清理脏数据
@Usage: python clean_dirty_data.py
"""

import sys
import os
from contextlib import contextmanager

# ========================================
# 配置信息（可在脚本中直接修改）
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

# 数据源ID（必填）- 对应 datasource_infos 表中的 id
# 请替换为你要清理的数据源ID，留空则清理所有数据源
DATASOURCE_ID = "c1027311-1395-4f0d-b5b3-88b97e72a6ee"  # 例如: "59d688b2-e426-419e-8176-b95193766eb1"

# 用户的向量库 class 名称
# 格式通常是: datacard_datasource__{user_id}
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
            print(f"[向量库] collection '{class_name}' 不存在")
            return False
        collection = client.collections.get(class_name)
        collection.data.delete_by_id(uuid_str)
        return True

# ========================================
# 清理逻辑
# ========================================

def get_datasource_info(conn, datasource_id: str) -> dict:
    """根据 datasource_id 获取数据源信息"""
    sql = '''
        SELECT id, user_id, connect_info, connect_info_hash, connect_name, db_type, database_name, schema_name
        FROM datasource_infos
        WHERE id = %s
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (datasource_id,))
        result = cur.fetchone()
        return dict(result) if result else None


def get_all_datasources(conn) -> list:
    """获取所有数据源"""
    sql = '''
        SELECT id, user_id, connect_info, connect_name, db_type, database_name
        FROM datasource_infos
        ORDER BY created_at DESC
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def get_valid_schema_ids_by_connect_info_hash(conn, connect_info_hash: str, schema_name: str = None) -> set:
    """
    根据 connect_info_hash 获取 user_datasource_schemas 表中对应的 id 集合

    关联关系:
    datasource_infos.connect_info_hash == user_datasource_schemas.connect_info_hash
    """
    if not connect_info_hash:
        return set()

    if schema_name is not None:
        sql = '''
            SELECT id::text FROM user_datasource_schemas
            WHERE connect_info_hash = %s AND schema_name = %s
        '''
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (connect_info_hash, schema_name))
            return {str(row['id']) for row in cur.fetchall()}
    else:
        sql = '''
            SELECT id::text FROM user_datasource_schemas
            WHERE connect_info_hash = %s AND schema_name IS NULL
        '''
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (connect_info_hash,))
            return {str(row['id']) for row in cur.fetchall()}


def get_all_valid_schema_ids(conn) -> set:
    """获取所有有效的 schema id"""
    sql = 'SELECT id::text FROM user_datasource_schemas'
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return {str(row['id']) for row in cur.fetchall()}


def get_datacards_records_by_datasource(conn, datasource_id: str) -> list:
    """
    获取指定数据源关联的 datacards 记录
    通过 datasource_id 过滤（虽然这是冗余字段，但可以减少查询范围）
    """
    sql = '''
        SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
               dc.table_name, dc.created_at, dc.user_id::text
        FROM datacards_datasource dc
        WHERE dc.datasource_id = %s
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (datasource_id,))
        return list(cur.fetchall())


def get_all_datacards_records(conn) -> list:
    """获取 datacards_datasource 表中的所有记录"""
    sql = '''
        SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
               dc.table_name, dc.created_at, dc.user_id::text
        FROM datacards_datasource dc
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def find_dirty_records(valid_schema_ids: set, datacards_records: list) -> list:
    """找出 datacards_datasource 表中的脏数据（doc_id 不在有效 schema id 集合中的）"""
    dirty_records = []
    for record in datacards_records:
        doc_id = str(record['doc_id']) if record['doc_id'] else ""
        if doc_id not in valid_schema_ids:
            dirty_records.append(record)
    return dirty_records


def delete_records_from_database(conn, record_ids: list) -> dict:
    """从数据库中删除记录"""
    if not record_ids:
        return {"deleted": 0, "failed": 0}
    
    deleted_count = 0
    failed_count = 0
    
    for record_id in record_ids:
        try:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM datacards_datasource WHERE id = %s', (record_id,))
            deleted_count += 1
        except Exception as e:
            print(f"[数据库删除] 删除记录 {record_id} 失败: {e}")
            failed_count += 1
    
    try:
        conn.commit()
        print(f"[数据库删除] 成功提交，删除了 {deleted_count} 条记录")
    except Exception as e:
        conn.rollback()
        print(f"[数据库删除] 提交失败: {e}")
        failed_count += deleted_count
        deleted_count = 0
    
    return {"deleted": deleted_count, "failed": failed_count}


def delete_records_from_vector(records: list, class_name: str) -> dict:
    """从向量库中删除记录"""
    deleted_count = 0
    failed_count = 0
    skipped_count = 0
    
    for record in records:
        w_uuid = record.get('w_uuid')
        if not w_uuid:
            skipped_count += 1
            continue
        
        try:
            delete_vector_by_uuid(str(w_uuid), class_name)
            deleted_count += 1
        except Exception as e:
            print(f"[向量库删除] 删除失败 w_uuid={w_uuid}: {e}")
            failed_count += 1
    
    return {"deleted": deleted_count, "failed": failed_count, "skipped": skipped_count}


def print_records_table(records: list, title: str = "记录列表"):
    """打印记录表格"""
    if not records:
        print(f"\n[信息] {title}: 无记录")
        return
    
    print(f"\n{'='*120}")
    print(f"{title} (共 {len(records)} 条)")
    print(f"{'='*120}")
    print(f"{'序号':<6} {'ID':<10} {'doc_id':<44} {'w_uuid':<44} {'表名':<30}")
    print(f"{'-'*120}")
    
    for i, record in enumerate(records[:50], 1):  # 最多显示50条
        doc_id = str(record.get('doc_id', ''))[:42]
        w_uuid = str(record.get('w_uuid', ''))[:42]
        table_name = str(record.get('table_name', ''))[:28]
        record_id = str(record.get('id', ''))[:8]
        print(f"{i:<6} {record_id:<10} {doc_id:<44} {w_uuid:<44} {table_name:<30}")
    
    if len(records) > 50:
        print(f"... 还有 {len(records) - 50} 条记录未显示")
    print(f"{'='*120}\n")


def clean_datasource_dirty_data(conn, datasource_id: str, class_name: str, dry_run: bool = True):
    """清理指定数据源的脏数据"""
    print(f"\n{'#'*120}")
    print(f"# 数据源脏数据清理脚本")
    print(f"{'#'*120}")
    print(f"# 数据源ID: {datasource_id}")
    print(f"# 向量库Class: {class_name}")
    print(f"# 运行模式: {'仅预览（DRY RUN）' if dry_run else '执行删除'}")
    print(f"{'#'*120}\n")

    # 1. 获取数据源信息
    print("[步骤 1/6] 查询 datasource_infos 表...")
    ds_info = get_datasource_info(conn, datasource_id)
    if not ds_info:
        print(f"[错误] 未找到数据源: {datasource_id}")
        return

    print(f"[数据源信息]")
    print(f"  - 名称: {ds_info['connect_name']}")
    print(f"  - 类型: {ds_info['db_type']}")
    print(f"  - 数据库: {ds_info['database_name']}")

    connect_info_hash = ds_info.get('connect_info_hash')

    # 2. 获取该数据源关联的 user_datasource_schemas id
    print("\n[步骤 2/6] 查询 user_datasource_schemas 表...")
    valid_schema_ids = get_valid_schema_ids_by_connect_info_hash(conn, connect_info_hash, ds_info.get('schema_name'))
    print(f"[数据库查询] user_datasource_schemas 表中共有 {len(valid_schema_ids)} 条关联记录")

    if not valid_schema_ids:
        print("[警告] 该数据源没有关联的表结构记录")
        return

    # 3. 查询该数据源关联的 datacards
    print("\n[步骤 3/6] 查询 datacards_datasource 表...")
    sql = '''
        SELECT dc.id, dc.doc_id::text, dc.w_uuid::text, dc.datasource_id::text,
               dc.table_name, dc.created_at, dc.user_id::text
        FROM datacards_datasource dc
        WHERE dc.datasource_id = %s
    '''
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (datasource_id,))
        all_records = list(cur.fetchall())

    print(f"[数据库查询] datacards_datasource 表中共有 {len(all_records)} 条相关记录")

    # 4. 分析脏数据
    print("\n[步骤 4/6] 分析脏数据...")

    valid_records = []
    dirty_records = []

    for card in all_records:
        doc_id = str(card['doc_id']) if card['doc_id'] else ""
        if doc_id in valid_schema_ids:
            valid_records.append(card)
        else:
            dirty_records.append(card)

    print(f"[关联分析]")
    print(f"  - user_datasource_schemas 关联记录: {len(valid_schema_ids)} 条")
    print(f"  - datacards 记录总数: {len(all_records)} 条")
    print(f"  - 有效记录（doc_id 在 schema 中）: {len(valid_records)} 条")
    print(f"  - 脏数据（doc_id 不在 schema 中）: {len(dirty_records)} 条")

    if not dirty_records:
        print("\n[结果] 没有发现脏数据，数据源状态正常")
        return

    print(f"\n[分析结果] 发现 {len(dirty_records)} 条脏数据")
    print_records_table(dirty_records, "脏数据记录")

    # 5. 执行清理
    if dry_run:
        print("\n[步骤 5/6] DRY RUN 模式 - 跳过删除操作")
        print("[步骤 6/6] 仅预览完成，未执行任何删除操作")
        print(f"\n[提示] 如需执行删除，请将 DRY_RUN 设置为 False")
    else:
        print("\n[步骤 5/6] 开始清理数据库记录...")
        record_ids = [r['id'] for r in dirty_records]
        db_result = delete_records_from_database(conn, record_ids)

        print("\n[步骤 6/6] 开始清理向量库记录...")
        vector_result = delete_records_from_vector(dirty_records, class_name)

        print(f"\n{'='*120}")
        print(f"# 清理完成")
        print(f"{'='*120}")
        print(f"# 数据库删除: 成功 {db_result['deleted']} 条, 失败 {db_result['failed']} 条")
        print(f"# 向量库删除: 成功 {vector_result['deleted']} 条, 失败 {vector_result['failed']} 条, 跳过 {vector_result['skipped']} 条")
        print(f"{'='*120}\n")


def clean_all_dirty_data(conn, class_name: str, dry_run: bool = True):
    """清理所有数据源的脏数据"""
    print(f"\n{'#'*120}")
    print(f"# 全量脏数据清理脚本")
    print(f"{'#'*120}")
    print(f"# 向量库Class: {class_name}")
    print(f"# 运行模式: {'仅预览（DRY RUN）' if dry_run else '执行删除'}")
    print(f"{'#'*120}\n")

    # 1. 获取所有数据源
    print("[步骤 1/6] 查询 datasource_infos 表...")
    all_datasources = get_all_datasources(conn)
    print(f"[数据库查询] 共有 {len(all_datasources)} 个数据源")

    # 2. 获取所有有效的 schema id
    print("\n[步骤 2/6] 查询 user_datasource_schemas 表...")
    all_valid_schema_ids = get_all_valid_schema_ids(conn)
    print(f"[数据库查询] user_datasource_schemas 表中共有 {len(all_valid_schema_ids)} 条记录")

    # 3. 获取所有 datacards 记录
    print("\n[步骤 3/6] 查询 datacards_datasource 表...")
    all_datacards = get_all_datacards_records(conn)
    print(f"[数据库查询] datacards_datasource 表中共有 {len(all_datacards)} 条记录")

    # 4. 分析关联关系
    print("\n[步骤 4/6] 分析关联关系...")

    # 统计：有多少 datacards 的 doc_id 在 user_datasource_schemas 中
    valid_doc_ids = set()
    invalid_doc_ids = []
    doc_id_counts = {}  # 统计 doc_id 出现次数

    for card in all_datacards:
        doc_id = str(card['doc_id']) if card['doc_id'] else ""
        # 统计 doc_id 出现次数
        doc_id_counts[doc_id] = doc_id_counts.get(doc_id, 0) + 1

        if doc_id in all_valid_schema_ids:
            valid_doc_ids.add(doc_id)
        else:
            invalid_doc_ids.append(card)

    print(f"[关联分析]")
    print(f"  - datacards 总数: {len(all_datacards)}")
    print(f"  - user_datasource_schemas 总数: {len(all_valid_schema_ids)}")
    print(f"  - datacards 中唯一的 doc_id 数量: {len(doc_id_counts)}")
    print(f"  - datacards.doc_id 在 schema 中的数量: {len(valid_doc_ids)}")
    print(f"  - datacards.doc_id 不在 schema 中的数量（脏数据）: {len(invalid_doc_ids)}")

    # 检测重复的 doc_id
    duplicate_doc_ids = {k: v for k, v in doc_id_counts.items() if v > 1}
    if duplicate_doc_ids:
        print(f"\n[警告] 发现 {len(duplicate_doc_ids)} 个重复的 doc_id！")
        print(f"[详情] 部分重复的 doc_id 样例:")
        for i, (doc_id, count) in enumerate(list(duplicate_doc_ids.items())[:5]):
            print(f"    doc_id: {doc_id[:40]}... 出现次数: {count}")
        if len(duplicate_doc_ids) > 5:
            print(f"    ... 还有 {len(duplicate_doc_ids) - 5} 个重复的 doc_id")

    # 差值分析
    diff = len(all_datacards) - len(valid_doc_ids)
    if diff > 0:
        print(f"\n[差值分析]")
        print(f"  - datacards 记录数: {len(all_datacards)}")
        print(f"  - 唯一有效 doc_id 数: {len(valid_doc_ids)}")
        print(f"  - 差值: {diff} 条")
        print(f"  - 这 {diff} 条可能是重复的 doc_id 对应的额外记录")

    if not invalid_doc_ids:
        print("\n[结果] 没有发现脏数据，所有数据源状态正常")
        return

    # 按 datasource_id 分组脏数据
    dirty_by_datasource = {}
    for record in invalid_doc_ids:
        ds_id = str(record['datasource_id']) if record['datasource_id'] else "unknown"
        if ds_id not in dirty_by_datasource:
            dirty_by_datasource[ds_id] = []
        dirty_by_datasource[ds_id].append(record)

    print(f"\n[分析结果] 共发现 {len(invalid_doc_ids)} 条脏数据，分布在 {len(dirty_by_datasource)} 个数据源中")

    # 打印脏数据分布
    print(f"\n{'='*120}")
    print(f"脏数据分布统计")
    print(f"{'='*120}")
    print(f"{'数据源ID':<45} {'数据源名称':<30} {'脏数据条数':<15}")
    print(f"{'-'*120}")
    for ds_id, records in dirty_by_datasource.items():
        # 查找数据源名称
        ds_name = "未知"
        for ds in all_datasources:
            if str(ds['id']) == ds_id:
                ds_name = ds['connect_name'][:28]
                break
        print(f"{ds_id:<45} {ds_name:<30} {len(records):<15}")
    print(f"{'='*120}\n")

    # 打印脏数据详情
    print_records_table(invalid_doc_ids, "待清理的脏数据记录")

    # 5. 执行清理
    if dry_run:
        print("\n[步骤 5/6] DRY RUN 模式 - 跳过删除操作")
        print("[步骤 6/6] 仅预览完成，未执行任何删除操作")
        print(f"\n[提示] 如需执行删除，请将 DRY_RUN 设置为 False")
    else:
        print("\n[步骤 5/6] 开始清理数据库记录...")
        record_ids = [r['id'] for r in invalid_doc_ids]
        db_result = delete_records_from_database(conn, record_ids)

        print("\n[步骤 6/6] 开始清理向量库记录...")
        vector_result = delete_records_from_vector(invalid_doc_ids, class_name)

        print(f"\n{'='*120}")
        print(f"# 全量清理完成")
        print(f"{'='*120}")
        print(f"# 数据库删除: 成功 {db_result['deleted']} 条, 失败 {db_result['failed']} 条")
        print(f"# 向量库删除: 成功 {vector_result['deleted']} 条, 失败 {vector_result['failed']} 条, 跳过 {vector_result['skipped']} 条")
        print(f"# 影响数据源数: {len(dirty_by_datasource)} 个")
        print(f"{'='*120}\n")


# ========================================
# 主入口
# ========================================

if __name__ == '__main__':
    print("""
    ========================================
    数据源脏数据清理工具
    ========================================
    
    使用说明:
    1. 清理指定数据源: 修改 DATASOURCE_ID 为目标数据源ID
    2. 清理所有数据源: 将 DATASOURCE_ID 设为空字符串 ""
    3. DRY_RUN = True 时仅预览，False 时执行删除 ← 注释有误，实际相反
    
    关联关系:
    datasource_infos.connect_info == user_datasource_schemas.connect_info
    datacards_datasource.doc_id == user_datasource_schemas.id
    
    ========================================
    """)
    
    conn = get_db_connection()
    try:
        if DATASOURCE_ID:
            # 清理指定数据源
            clean_datasource_dirty_data(conn, DATASOURCE_ID, WEAVIATE_CLASS_NAME, DRY_RUN)
        else:
            # 清理所有数据源
            clean_all_dirty_data(conn, WEAVIATE_CLASS_NAME, DRY_RUN)
    finally:
        conn.close()
