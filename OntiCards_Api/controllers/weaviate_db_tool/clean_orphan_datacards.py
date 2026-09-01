"""
clean_orphan_datacards.py

清理孤儿数据卡片脚本：
- 删除 datacards_datasource 中没有对应 user_datasource_schemas 的记录
- 删除 Weaviate 向量库中对应的记录（通过 w_uuid）

关联关系：
- user_datasource_schemas.id::text = datacards_datasource.doc_id
- datacards_datasource.w_uuid = Weaviate 中的 id
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional, Dict, Set

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams


# ========= 配置区 =========
DATABASE_URL = "postgresql+psycopg2://postgres:master_ds123@172.16.1.7:55432/prod-ontiCards"

WEAVIATE_URL = "http://172.16.1.7:8080"
WEAVIATE_GRPC_PORT = 50051

SCHEMAS_TABLE = "user_datasource_schemas"
DATACARDS_TABLE = "datacards_datasource"
# =============================


def normalize_class_name(name: str) -> str:
    if not name:
        return ""
    return str(name).strip().replace("-", "_")


@contextmanager
def weaviate_client():
    client = WeaviateClient(
        connection_params=ConnectionParams.from_url(url=WEAVIATE_URL, grpc_port=WEAVIATE_GRPC_PORT)
    )
    client.connect()
    try:
        yield client
    finally:
        client.close()


def get_user_class_mapping(engine: Engine) -> Dict[str, str]:
    """获取 user_id -> weaviate_class_name 的映射"""
    sql = text("""
        SELECT id::text, weaviate_class_name
        FROM users
        WHERE weaviate_class_name IS NOT NULL AND weaviate_class_name <> ''
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()
    return {str(row[0]): normalize_class_name(str(row[1])) for row in rows}


def get_orphan_datacards(engine: Engine) -> List[dict]:
    """
    获取所有孤儿数据卡片（datacards 有但 schemas 没有）
    即：datacards_datasource.doc_id 不在 user_datasource_schemas.id 集合中的记录
    """
    sql = text(f"""
        SELECT dc.id, dc.doc_id, dc.w_uuid, dc.table_name, dc.datasource_id
        FROM "{DATACARDS_TABLE}" dc
        LEFT JOIN "{SCHEMAS_TABLE}" uds ON dc.doc_id = uds.id::text
        WHERE uds.id IS NULL
        ORDER BY dc.datasource_id, dc.id
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()

    return [
        {
            "id": int(r[0]),
            "doc_id": str(r[1]),
            "w_uuid": str(r[2]) if r[2] else None,
            "table_name": str(r[3]) if r[3] else None,
            "datasource_id": str(r[4]) if r[4] else None,
        }
        for r in rows
    ]


def get_datacard_datasource_mapping(engine: Engine) -> Dict[int, str]:
    """
    获取 datacard id -> user_id 的映射
    用于确定每个孤儿 datacard 属于哪个用户
    """
    sql = text(f"""
        SELECT dc.id, di.user_id
        FROM "{DATACARDS_TABLE}" dc
        LEFT JOIN datasource_infos di ON dc.datasource_id = di.id::uuid
        WHERE dc.id IN (
            SELECT dc2.id
            FROM "{DATACARDS_TABLE}" dc2
            LEFT JOIN "{SCHEMAS_TABLE}" uds ON dc2.doc_id = uds.id::text
            WHERE uds.id IS NULL
        )
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()
    return {int(r[0]): str(r[1]) if r[1] else None for r in rows}


def iter_weaviate_objects(collection):
    if hasattr(collection, "iterator"):
        try:
            return collection.iterator()
        except Exception:
            pass

    def _gen():
        after = None
        while True:
            resp = collection.query.fetch_objects(limit=200, after=after)
            objs = getattr(resp, "objects", None)
            if not objs:
                break
            for o in objs:
                yield o
            after = getattr(resp, "next_after", None) or getattr(resp, "nextAfter", None)
            if not after:
                break

    return _gen()


def get_obj_uuid(obj) -> Optional[str]:
    return getattr(obj, "uuid", None)


def delete_weaviate_objects_batch(client: WeaviateClient, class_name: str, uuids: List[str]) -> int:
    """批量删除 Weaviate 中的对象"""
    if not uuids:
        return 0

    col = client.collections.get(class_name)
    deleted = 0

    for uuid_str in uuids:
        try:
            col.data.delete_by_id(uuid_str)
            deleted += 1
        except Exception as e:
            print(f"      删除向量失败: {uuid_str}, 错误: {e}")

    return deleted


def delete_datacards_from_db(engine: Engine, datacard_ids: List[int]) -> int:
    """从数据库删除 datacards 记录"""
    if not datacard_ids:
        return 0

    placeholders = ",".join([f":id_{i}" for i in range(len(datacard_ids))])
    params = {f"id_{i}": id_val for i, id_val in enumerate(datacard_ids)}

    sql = text(f"""
        DELETE FROM "{DATACARDS_TABLE}"
        WHERE id IN ({placeholders})
    """)

    with engine.begin() as conn:
        result = conn.execute(sql, params)
    return result.rowcount


def get_weaviate_class_counts(client: WeaviateClient, user_class_mapping: Dict[str, str]) -> Dict[str, int]:
    """获取每个 Weaviate Class 的总记录条数"""
    counts = {}
    for user_id, class_name in user_class_mapping.items():
        try:
            if client.collections.exists(class_name):
                col = client.collections.get(class_name)
                # 使用 aggregate count
                result = col.aggregate.over_all(total_count=True)
                counts[class_name] = result.total_count
            else:
                counts[class_name] = 0
        except Exception as e:
            counts[class_name] = 0
            print(f"  获取 {class_name} 记录数失败: {e}")
    return counts


def main():
    engine = create_engine(DATABASE_URL, future=True)

    print("=" * 80)
    print("清理孤儿数据卡片及向量")
    print("=" * 80)

    # 1. 获取用户和 Weaviate Class 映射
    print("\n[步骤 1/5] 获取用户 Weaviate Class 映射...")
    user_class_mapping = get_user_class_mapping(engine)
    print(f"获取到 {len(user_class_mapping)} 个用户的 Weaviate Class")

    # 2. 获取每个 Class 的总记录数
    print("\n[步骤 2/5] 获取每个用户 Class 的总记录数...")
    with weaviate_client() as client:
        class_counts = get_weaviate_class_counts(client, user_class_mapping)

    print("\n  用户 Class 记录数统计：")
    total_all = 0
    for user_id, class_name in user_class_mapping.items():
        count = class_counts.get(class_name, 0)
        total_all += count
        print(f"    用户 {user_id[:8]}... | Class: {class_name} | 总记录数: {count}")
    print(f"    ─────────────────────────────────────────")
    print(f"    所有 Class 总记录数: {total_all}")

    # 3. 获取所有孤儿数据卡片
    print("\n[步骤 3/5] 查询孤儿数据卡片...")
    orphan_datacards = get_orphan_datacards(engine)

    if not orphan_datacards:
        print("未发现孤儿数据卡片，无需清理")
        return

    print(f"发现 {len(orphan_datacards)} 条孤儿数据卡片")

    # 按 datasource_id 分组显示
    by_datasource: Dict[str, List[dict]] = {}
    for dc in orphan_datacards:
        ds_id = dc["datasource_id"] or "unknown"
        if ds_id not in by_datasource:
            by_datasource[ds_id] = []
        by_datasource[ds_id].append(dc)

    print(f"\n按数据源分组：")
    for ds_id, dcs in by_datasource.items():
        tables = [dc["table_name"] for dc in dcs if dc["table_name"]]
        print(f"  - datasource_id={ds_id}: {len(dcs)} 条 (表: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''})")

    # 4. 删除 Weaviate 向量
    print("\n[步骤 4/5] 删除 Weaviate 向量...")
    deleted_weaviate = 0
    failed_weaviate = []

    # 获取 datacard -> user_id 映射
    dc_user_mapping = get_datacard_datasource_mapping(engine)

    with weaviate_client() as client:
        # 按用户分批删除
        for user_id, class_name in user_class_mapping.items():
            # 找出属于该用户的孤儿 datacard 的 w_uuid
            user_orphan_wuuids = []
            for dc in orphan_datacards:
                if dc_user_mapping.get(dc["id"]) == user_id and dc["w_uuid"]:
                    user_orphan_wuuids.append(dc["w_uuid"])

            if not user_orphan_wuuids:
                continue

            if not client.collections.exists(class_name):
                print(f"  用户 {user_id} 的 Class {class_name} 不存在，跳过 {len(user_orphan_wuuids)} 条")
                continue

            print(f"  用户 {user_id} ({class_name}): 删除 {len(user_orphan_wuuids)} 条向量")
            batch_deleted = delete_weaviate_objects_batch(client, class_name, user_orphan_wuuids)
            deleted_weaviate += batch_deleted
            print(f"    成功删除 {batch_deleted} 条")

    # 5. 删除数据库记录
    print("\n[步骤 5/5] 删除数据库中的孤儿数据卡片记录...")
    datacard_ids = [dc["id"] for dc in orphan_datacards]
    deleted_db = delete_datacards_from_db(engine, datacard_ids)
    print(f"成功删除 {deleted_db} 条数据库记录")

    # 总结
    print("\n" + "=" * 80)
    print("清理完成")
    print("=" * 80)
    print(f"  - 孤儿数据卡片总数：{len(orphan_datacards)}")
    print(f"  - 删除 Weaviate 向量：{deleted_weaviate} 条")
    print(f"  - 删除数据库记录：{deleted_db} 条")

    if failed_weaviate:
        print(f"\n  ⚠️  删除失败的 Weaviate 向量：{len(failed_weaviate)} 条")
        for w_uuid in failed_weaviate[:10]:
            print(f"      - {w_uuid}")


if __name__ == "__main__":
    confirm = input("\n确认删除孤儿数据卡片？(输入 'yes' 确认): ")
    if confirm.lower() == "yes":
        main()
    else:
        print("已取消")
