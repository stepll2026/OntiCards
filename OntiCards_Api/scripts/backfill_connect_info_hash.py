"""
@File: backfill_connect_info_hash.py
@Description: 回填历史数据的 connect_info_hash 字段
              用于解决 AES-GCM 加密每次随机 nonce 导致相同明文产生不同密文的问题

@Usage:
    python scripts/backfill_connect_info_hash.py

@Author: 韩小豪
@Create: 2026-08-26
"""

import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
from extensions.ext_database import db
from models.datasource_infos import DatasourceInfo
from models.user_datasource_schema import UserDatasourceSchema
from core.connect_info_encryptor import decrypt_connect_info, is_encrypted


def get_connect_info_hash(plaintext: str) -> str:
    """
    获取连接信息的稳定哈希值，用于快速匹配和去重
    """
    if not plaintext:
        return ""
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


def decrypt_connect_info_safe(encrypted_or_plaintext: str) -> str:
    """
    安全解密：如果是加密的则解密，否则直接返回
    """
    if not encrypted_or_plaintext:
        return ""

    if is_encrypted(encrypted_or_plaintext):
        try:
            return decrypt_connect_info(encrypted_or_plaintext)
        except Exception as e:
            print(f"    [警告] 解密失败: {str(e)}, 尝试直接使用原始值")
            return encrypted_or_plaintext
    else:
        # 本身就是明文（历史数据未加密）
        return encrypted_or_plaintext


def backfill_connect_info_hash():
    """
    回填 connect_info_hash 字段

    逻辑：
    1. 遍历 datasource_infos 表中的所有记录
    2. 解密 connect_info，计算哈希值
    3. 更新 datasource_infos 表的 connect_info_hash
    4. 遍历 user_datasource_schemas 表，解密每条记录的 connect_info，计算哈希值
    5. 如果 user_datasource_schemas 中某条记录的解密后哈希值等于 datasource_infos 的哈希值，
       且 (user_id, schema_name) 匹配，则更新该记录的 connect_info_hash
    """
    print("=" * 60)
    print("开始回填 connect_info_hash 字段")
    print("=" * 60)

    # ========== 步骤1: 处理 datasource_infos ==========
    print("\n[步骤1] 处理 datasource_infos 表...")

    all_datasources = db.session.query(DatasourceInfo).all()
    print(f"  找到 {len(all_datasources)} 条 datasource_infos 记录")

    if not all_datasources:
        print("  没有需要处理的数据源记录")

    # 建立 (user_id, schema_name) -> hash 的映射
    ds_hash_map = {}  # key: (user_id, schema_name), value: hash
    updated_ds_count = 0
    error_count = 0
    skipped_count = 0

    for ds in all_datasources:
        try:
            if not ds.connect_info:
                print(f"  [跳过] datasource_id={ds.id}, connect_info 为空")
                skipped_count += 1
                continue

            # 解密并计算哈希
            plaintext = decrypt_connect_info_safe(ds.connect_info)
            new_hash = get_connect_info_hash(plaintext)

            old_hash = ds.connect_info_hash
            if old_hash != new_hash:
                ds.connect_info_hash = new_hash
                updated_ds_count += 1
                print(f"  [更新] datasource_id={ds.id}, hash: {old_hash[:16] if old_hash else 'None'}... -> {new_hash[:16]}...")
            else:
                print(f"  [无需更新] datasource_id={ds.id}, hash 未变化")

            # 记录到映射表中
            key = (str(ds.user_id), ds.schema_name)
            ds_hash_map[key] = new_hash

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            error_count += 1
            print(f"  [错误] datasource_id={ds.id}, 错误: {str(e)}")
            continue

    print(f"  datasource_infos 更新完成: {updated_ds_count} 条更新, {skipped_count} 条跳过, {error_count} 条错误")

    # ========== 步骤2: 处理 user_datasource_schemas ==========
    print("\n[步骤2] 处理 user_datasource_schemas 表...")

    all_schemas = db.session.query(UserDatasourceSchema).all()
    print(f"  找到 {len(all_schemas)} 条 user_datasource_schemas 记录")

    updated_schema_count = 0
    schema_error_count = 0
    schema_skipped_count = 0

    for schema in all_schemas:
        try:
            if not schema.connect_info:
                print(f"  [跳过] schema_id={schema.id}, connect_info 为空")
                schema_skipped_count += 1
                continue

            # 解密并计算哈希
            plaintext = decrypt_connect_info_safe(schema.connect_info)
            new_hash = get_connect_info_hash(plaintext)

            old_hash = schema.connect_info_hash
            if old_hash != new_hash:
                schema.connect_info_hash = new_hash
                updated_schema_count += 1
                print(f"  [更新] schema_id={schema.id}, hash: {old_hash[:16] if old_hash else 'None'}... -> {new_hash[:16]}...")
            else:
                print(f"  [无需更新] schema_id={schema.id}, hash 未变化")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            schema_error_count += 1
            print(f"  [错误] schema_id={schema.id}, 错误: {str(e)}")
            continue

    print(f"  user_datasource_schemas 更新完成: {updated_schema_count} 条更新, {schema_skipped_count} 条跳过, {schema_error_count} 条错误")

    # ========== 总结 ==========
    print("\n" + "=" * 60)
    print("回填完成！")
    print("=" * 60)
    print(f"  datasource_infos: {updated_ds_count} 条更新, {skipped_count} 条跳过, {error_count} 条错误")
    print(f"  user_datasource_schemas: {updated_schema_count} 条更新, {schema_skipped_count} 条跳过, {schema_error_count} 条错误")


def verify_backfill():
    """
    验证回填结果：
    正确的验证方式是：对于每条 datasource_infos 记录，检查是否存在 user_datasource_schemas 记录的哈希值与它相同。
    因为一个 datasource_infos 记录对应多个 user_datasource_schemas 记录（同一数据源的不同表）
    """
    print("\n" + "=" * 60)
    print("开始验证回填结果...")
    print("=" * 60)

    # 构建 schema 哈希值集合
    all_schema_hashes = set()
    for schema in db.session.query(UserDatasourceSchema).filter(
        UserDatasourceSchema.connect_info_hash.isnot(None)
    ):
        all_schema_hashes.add(schema.connect_info_hash)

    print(f"  共有 {len(all_schema_hashes)} 个不同的 schema 哈希值")

    # 验证每个 datasource_infos 的哈希值是否在 schema 中存在
    inconsistent_ds_count = 0
    verified_ds_count = 0
    orphan_schemas = []

    # 收集所有 datasource 哈希值
    all_ds_hashes = {}
    for ds in db.session.query(DatasourceInfo).filter(
        DatasourceInfo.connect_info_hash.isnot(None)
    ):
        all_ds_hashes[ds.connect_info_hash] = ds

    # 检查每个 datasource 是否有对应的 schema
    for ds_hash, ds in all_ds_hashes.items():
        if ds_hash in all_schema_hashes:
            verified_ds_count += 1
        else:
            inconsistent_ds_count += 1
            print(f"  [孤立] datasource_id={ds.id}, user_id={ds.user_id}, schema_name={ds.schema_name}")
            print(f"    ds hash: {ds_hash[:16]}... 但没有找到对应的 schema")

    # 检查是否有 schema 没有对应的 datasource（可能是错误的数据）
    schema_hashes_by_ds = {}
    for ds_hash in all_ds_hashes.keys():
        schema_hashes_by_ds[ds_hash] = True

    orphaned_schema_count = 0
    for schema_hash in all_schema_hashes:
        if schema_hash not in schema_hashes_by_ds:
            orphaned_schema_count += 1
            # 查找这个孤立 schema
            orphan_schema = db.session.query(UserDatasourceSchema).filter(
                UserDatasourceSchema.connect_info_hash == schema_hash
            ).first()
            if orphan_schema:
                print(f"  [孤立] schema_id={orphan_schema.id}, user_id={orphan_schema.user_id}")
                print(f"    schema hash: {schema_hash[:16]}... 但没有找到对应的 datasource")
                orphan_schemas.append(orphan_schema.id)

    print("\n" + "-" * 60)
    print(f"  验证完成: {verified_ds_count} 个 datasource 有对应 schema, {inconsistent_ds_count} 个孤立")
    print(f"  孤立 schema 数: {orphaned_schema_count}")

    if inconsistent_ds_count == 0 and orphaned_schema_count == 0:
        print("\n  [验证通过] 所有哈希值都能正确匹配！")
        return True
    else:
        print("\n  [警告] 存在孤立记录，但这可能是正常情况：")
        print("    - 孤立 datasource: 可能是新添加但还未提取表结构的数据源")
        print("    - 孤立 schema: 可能是旧数据，connect_info 内容与现有 datasource 都不同")
        return inconsistent_ds_count == 0


def show_statistics():
    """
    显示统计信息
    """
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)

    # datasource_infos 统计
    total_ds = db.session.query(DatasourceInfo).count()
    ds_with_hash = db.session.query(DatasourceInfo).filter(
        DatasourceInfo.connect_info_hash.isnot(None)
    ).count()
    ds_without_hash = total_ds - ds_with_hash

    print(f"\ndatasource_infos 表:")
    print(f"  总记录数: {total_ds}")
    print(f"  有哈希值: {ds_with_hash}")
    print(f"  无哈希值: {ds_without_hash}")

    # user_datasource_schemas 统计
    total_schema = db.session.query(UserDatasourceSchema).count()
    schema_with_hash = db.session.query(UserDatasourceSchema).filter(
        UserDatasourceSchema.connect_info_hash.isnot(None)
    ).count()
    schema_without_hash = total_schema - schema_with_hash

    print(f"\nuser_datasource_schemas 表:")
    print(f"  总记录数: {total_schema}")
    print(f"  有哈希值: {schema_with_hash}")
    print(f"  无哈希值: {schema_without_hash}")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        # 显示统计信息
        show_statistics()

        # 执行回填
        backfill_connect_info_hash()

        # 验证结果
        verify_backfill()

        # 再次显示统计信息
        show_statistics()
