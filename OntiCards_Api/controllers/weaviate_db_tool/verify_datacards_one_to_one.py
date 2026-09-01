"""
@File: verify_datacards_one_to_one.py
@Description: 校验 user_datasource_schemas 和 datacards_datasource 表的记录是否一对一对应
              user_datasource_schemas.id == datacards_datasource.doc_id

@Usage:
    python scripts/verify_datacards_one_to_one.py

@Author: 韩小豪
@Create: 2026-08-26
"""

import sys
import os

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from collections import Counter


def main():
    from extensions.ext_database import db
    from models.user_datasource_schema import UserDatasourceSchema
    from models.datacards_datasource import DataCardDataSource

    print("=" * 70)
    print("校验 user_datasource_schemas 与 datacards_datasource 的一对一关系")
    print("=" * 70)

    # 1. 统计总数
    total_schemas = db.session.query(UserDatasourceSchema).count()
    total_datacards = db.session.query(DataCardDataSource).count()
    print(f"\n[统计] user_datasource_schemas 总记录数: {total_schemas}")
    print(f"[统计] datacards_datasource 总记录数:   {total_datacards}")
    print(f"[差值] 多出的 datacards 数量:           {total_datacards - total_schemas}")

    # 2. 获取所有 schema_id 和 doc_id
    print("\n" + "-" * 70)
    print("[1] 检查 datacards_datasource.doc_id 是否都能对应到 user_datasource_schemas.id")
    print("-" * 70)

    schema_ids = set()
    for s in db.session.query(UserDatasourceSchema.id).all():
        schema_ids.add(str(s[0]))

    orphan_datacards = []
    for dc in db.session.query(DataCardDataSource).all():
        doc_id = str(dc.doc_id)
        if doc_id not in schema_ids:
            orphan_datacards.append(dc)

    print(f"  找不到对应 schema 的 datacards 数: {len(orphan_datacards)}")
    if orphan_datacards:
        print("\n  [孤立 datacards] doc_id 在 user_datasource_schemas 中不存在：")
        for dc in orphan_datacards:
            print(f"    - id={dc.id}, doc_id={dc.doc_id}, w_uuid={dc.w_uuid}, "
                  f"user_id={dc.user_id}, datasource_id={dc.datasource_id}, "
                  f"table_name={dc.table_name}, connect_name={dc.connect_name}, "
                  f"created_at={dc.created_at}")

    # 3. 检查 datacards_datasource 是否有重复的 doc_id
    print("\n" + "-" * 70)
    print("[2] 检查 datacards_datasource 是否有重复的 doc_id (一个 schema 应只有一张卡片)")
    print("-" * 70)

    doc_id_counter = Counter()
    for dc in db.session.query(DataCardDataSource.doc_id).all():
        doc_id_counter[str(dc[0])] += 1

    duplicate_doc_ids = [(d, c) for d, c in doc_id_counter.items() if c > 1]
    if duplicate_doc_ids:
        print(f"  发现 {len(duplicate_doc_ids)} 个 doc_id 出现了多次：")
        for doc_id, cnt in duplicate_doc_ids:
            print(f"    - doc_id={doc_id} 出现 {cnt} 次")
            records = db.session.query(DataCardDataSource).filter(
                DataCardDataSource.doc_id == doc_id
            ).all()
            for r in records:
                print(f"      * id={r.id}, w_uuid={r.w_uuid}, created_at={r.created_at}")
    else:
        print("  未发现重复 doc_id")

    # 4. 检查 user_datasource_schemas 中是否有 schema 没有对应的 datacard
    print("\n" + "-" * 70)
    print("[3] 检查 user_datasource_schemas 中是否有 schema 没有对应 datacard")
    print("-" * 70)

    datacard_doc_ids = set()
    for dc in db.session.query(DataCardDataSource.doc_id).all():
        datacard_doc_ids.add(str(dc[0]))

    missing_datacards = []
    for s in db.session.query(UserDatasourceSchema).all():
        if str(s.id) not in datacard_doc_ids:
            missing_datacards.append(s)

    print(f"  缺少 datacard 的 schema 数: {len(missing_datacards)}")
    if missing_datacards:
        print("\n  [缺少 datacard] schema 没有对应的 datacard：")
        for s in missing_datacards[:20]:
            print(f"    - schema_id={s.id}, user_id={s.user_id}, "
                  f"db_type={s.db_type}, table_name={s.table_name}, "
                  f"connect_name={s.connect_name}, schema_name={s.schema_name}")
        if len(missing_datacards) > 20:
            print(f"    ... 共 {len(missing_datacards)} 条，仅显示前 20 条")

    # 5. 总结
    print("\n" + "=" * 70)
    print("总结：所有「多出来」的 datacards_datasource 记录的 w_uuid")
    print("=" * 70)

    extra_w_uuids = []
    if orphan_datacards:
        print(f"\n类型 A: doc_id 在 schemas 中找不到（{len(orphan_datacards)} 条）")
        for dc in orphan_datacards:
            print(f"  w_uuid={dc.w_uuid}    doc_id={dc.doc_id}    table_name={dc.table_name}")
            extra_w_uuids.append(dc.w_uuid)

    if duplicate_doc_ids:
        print(f"\n类型 B: doc_id 重复（多余卡片，共 {sum(c - 1 for _, c in duplicate_doc_ids)} 条）")
        for doc_id, cnt in duplicate_doc_ids:
            records = db.session.query(DataCardDataSource).filter(
                DataCardDataSource.doc_id == doc_id
            ).order_by(DataCardDataSource.created_at.asc()).all()
            for r in records[1:]:
                print(f"  w_uuid={r.w_uuid}    doc_id={r.doc_id}    created_at={r.created_at}")
                extra_w_uuids.append(r.w_uuid)

    print("\n" + "=" * 70)
    print(f"所有需要清理的 w_uuid 总数: {len(extra_w_uuids)}")
    print("=" * 70)
    if extra_w_uuids:
        print("\nw_uuid 列表（每行一个，可直接用于清理）：")
        for w in extra_w_uuids:
            print(w)


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        main()
