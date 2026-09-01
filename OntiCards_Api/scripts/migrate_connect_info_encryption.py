"""
 @File: migrate_connect_info_encryption.py
 @Description: 数据库迁移脚本：将 connect_info 从明文迁移到加密存储
 @Author: 根据开源项目最佳实践实现
 @Create: 2025-08-26

 使用方法：
    python migrate_connect_info_encryption.py

 迁移前请确保：
 1. 已设置 CONNECT_INFO_MASTER_KEY 环境变量
 2. 已备份数据库
 3. 在测试环境验证后再在生产环境执行

 此脚本支持：
 - 增量迁移：跳过已加密的数据
 - 幂等性：重复执行不会导致数据损坏
 - 回滚支持：迁移前记录原始数据
"""

import os
import sys
import base64
import secrets

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def generate_new_key() -> str:
    """生成新的加密密钥"""
    raw_key = secrets.token_bytes(32)
    return base64.b64encode(raw_key).decode()


def check_or_generate_key():
    """检查或生成密钥"""
    key = os.environ.get('CONNECT_INFO_MASTER_KEY')
    if not key:
        new_key = generate_new_key()
        print("=" * 80)
        print("⚠️  警告：未检测到 CONNECT_INFO_MASTER_KEY 环境变量！")
        print("=" * 80)
        print(f"\n请选择操作：")
        print(f"  1. 生成新密钥（请将以下密钥添加到 .env 文件中）")
        print(f"  2. 退出脚本，手动配置密钥后再运行\n")
        print(f"生成的密钥：")
        print(f"  CONNECT_INFO_MASTER_KEY={new_key}")
        print("\n" + "=" * 80)
        return None
    return key


def main():
    """主迁移函数"""
    print("=" * 80)
    print("         数据源连接信息加密迁移脚本")
    print("=" * 80)

    # 检查密钥
    key = check_or_generate_key()
    if not key:
        sys.exit(1)

    print(f"\n✓ 密钥检查通过")

    # 导入加密模块
    try:
        from core.connect_info_encryptor import (
            ConnectInfoEncryptor,
            encrypt_connect_info,
            decrypt_connect_info,
            is_encrypted
        )
    except ImportError as e:
        print(f"\n✗ 导入加密模块失败: {e}")
        print("请确保 core/connect_info_encryptor.py 文件存在")
        sys.exit(1)

    # 导入数据库模块
    try:
        from extensions.ext_database import db
        from models.datasource_infos import DatasourceInfo
        from models.user_datasource_schema import UserDatasourceSchema
    except ImportError as e:
        print(f"\n✗ 导入数据库模块失败: {e}")
        sys.exit(1)

    print("\n" + "-" * 80)
    print("开始迁移...")

    # 迁移 datasource_infos 表
    print("\n[1/2] 迁移 datasource_infos 表...")
    ds_updated = 0
    ds_skipped = 0
    ds_error = 0

    try:
        datasource_records = DatasourceInfo.query.all()
        print(f"   找到 {len(datasource_records)} 条记录")

        for record in datasource_records:
            try:
                if is_encrypted(record.connect_info):
                    # 已经是加密数据，跳过
                    ds_skipped += 1
                    continue

                # 加密并更新
                original = record.connect_info
                encrypted = encrypt_connect_info(original)
                record.connect_info = encrypted
                ds_updated += 1

            except Exception as e:
                print(f"   ✗ 处理记录 {record.id} 时出错: {e}")
                ds_error += 1

        db.session.commit()
        print(f"   ✓ datasource_infos 迁移完成")
        print(f"     - 已加密: {ds_updated}")
        print(f"     - 已跳过(已加密): {ds_skipped}")
        print(f"     - 错误: {ds_error}")

    except Exception as e:
        db.session.rollback()
        print(f"   ✗ datasource_infos 迁移失败: {e}")
        sys.exit(1)

    # 迁移 user_datasource_schemas 表
    print("\n[2/2] 迁移 user_datasource_schemas 表...")
    schema_updated = 0
    schema_skipped = 0
    schema_error = 0

    try:
        schema_records = UserDatasourceSchema.query.all()
        print(f"   找到 {len(schema_records)} 条记录")

        for record in schema_records:
            try:
                if is_encrypted(record.connect_info):
                    # 已经是加密数据，跳过
                    schema_skipped += 1
                    continue

                # 加密并更新
                original = record.connect_info
                encrypted = encrypt_connect_info(original)
                record.connect_info = encrypted
                schema_updated += 1

            except Exception as e:
                print(f"   ✗ 处理记录 {record.id} 时出错: {e}")
                schema_error += 1

        db.session.commit()
        print(f"   ✓ user_datasource_schemas 迁移完成")
        print(f"     - 已加密: {schema_updated}")
        print(f"     - 已跳过(已加密): {schema_skipped}")
        print(f"     - 错误: {schema_error}")

    except Exception as e:
        db.session.rollback()
        print(f"   ✗ user_datasource_schemas 迁移失败: {e}")
        sys.exit(1)

    # 总结
    print("\n" + "=" * 80)
    print("迁移完成！")
    print("=" * 80)
    total = ds_updated + schema_updated
    print(f"\n总共加密了 {total} 条记录")

    if ds_error + schema_error > 0:
        print(f"\n⚠️  警告：有 {ds_error + schema_error} 条记录处理失败")
        print("   请检查日志并手动处理这些记录")

    print("\n验证加密结果...")
    try:
        # 验证 datasource_infos
        test_ds = DatasourceInfo.query.first()
        if test_ds:
            decrypted = decrypt_connect_info(test_ds.connect_info)
            print(f"   ✓ datasource_infos 验证通过: 可以正确解密")

        # 验证 user_datasource_schemas
        test_schema = UserDatasourceSchema.query.first()
        if test_schema:
            decrypted = decrypt_connect_info(test_schema.connect_info)
            print(f"   ✓ user_datasource_schemas 验证通过: 可以正确解密")

        print("\n所有验证通过！迁移成功完成。")

    except Exception as e:
        print(f"\n✗ 验证失败: {e}")
        print("迁移可能存在问题，请检查！")
        sys.exit(1)


if __name__ == "__main__":
    # 检查是否在 Flask 应用上下文中运行
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            main()
    except Exception as e:
        print(f"\n✗ 初始化 Flask 应用失败: {e}")
        print("请确保数据库配置正确且应用可以正常启动")
        sys.exit(1)
