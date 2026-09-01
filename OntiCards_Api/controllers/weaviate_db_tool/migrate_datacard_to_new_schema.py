"""
@DataCard 完整迁移脚本 - 适配新版 schema

功能：
1. 检查：对所有用户进行全面检查
2. 迁移：补全 card_data 中的 datasource_id，重建向量库，更新 w_uuid
3. 校验：最终一致性校验，确保数据库和向量库完全一致

使用方式：
    python test/migrate_datacard_to_new_schema.py --mode check          # 仅校验
    python test/migrate_datacard_to_new_schema.py --mode migrate        # 执行迁移
    python test/migrate_datacard_to_new_schema.py --mode migrate --dry-run  # 模拟迁移
    python test/migrate_datacard_to_new_schema.py --mode full            # 完整流程（检查+迁移+校验）

@Author: 韩小豪 849631113@qq.com
@Create: 2026-04-28
"""

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# 尝试导入配置，如果失败则使用默认值
try:
    from config import get_env
except ImportError:
    def get_env(key):
        return os.environ.get(key)


# ========================================
# 配置区
# ========================================

# 数据库连接 - 优先使用环境变量
DATABASE_URL = os.environ.get('DATABASE_URL') or "postgresql+psycopg2://postgres:master_hk123@10.8.2.45:55432/prod-ontiCards"

# 向量库配置
WEAVIATE_URL = os.environ.get('WEAVIATE_URL') or "http://10.8.2.45:8088"
WEAVIATE_GRPC_PORT = int(os.environ.get('GRPC_PORT') or 50051)

# 表名
T_USERS = "users"
T_DATASOURCE_INFOS = "datasource_infos"
T_DATACARDS = "datacards_datasource"

# 批处理参数
BATCH_SIZE = 100
SLEEP_SECONDS = 0.05


# ========================================
# 向量库客户端
# ========================================

from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams
from weaviate.classes.config import Property, DataType, Tokenization, Configure, VectorDistances


def _normalize_class_name(name: str) -> str:
    if not name:
        return ""
    return str(name).strip().replace("-", "_")


@contextmanager
def weaviate_client_local():
    client = WeaviateClient(connection_params=ConnectionParams.from_url(
        url=WEAVIATE_URL, grpc_port=WEAVIATE_GRPC_PORT
    ))
    client.connect()
    try:
        yield client
    finally:
        client.close()


# ========================================
# 向量库操作函数
# ========================================

def ensure_collection_with_datasource_id(class_name: str) -> str:
    """创建带 datasource_id 属性的 collection"""
    target = _normalize_class_name(class_name)

    with weaviate_client_local() as client:
        if client.collections.exists(target):
            # 检查现有属性
            col = client.collections.get(target)
            cfg = col.config.get()
            has_datasource_id = False

            if hasattr(cfg, "properties") and cfg.properties:
                for p in cfg.properties:
                    if hasattr(p, "name") and p.name == "datasource_id":
                        has_datasource_id = True
                        break

            if has_datasource_id:
                print(f"    [COLLECTION] {target} 已存在且包含 datasource_id 属性")
                return target
            else:
                # 删除旧 collection（缺少新属性）
                print(f"    [COLLECTION] {target} 缺少 datasource_id 属性，将重建")
                client.collections.delete(target)

        # 创建新 collection
        client.collections.create(
            name=target,
            description="数据卡片存储（新版，含 datasource_id）",
            properties=[
                Property(
                    name="doc_id",
                    data_type=DataType.TEXT,
                    description="卡片id",
                    tokenization=Tokenization.WHITESPACE,
                    index_filterable=True,
                    index_searchable=True
                ),
                Property(
                    name="abstract",
                    data_type=DataType.TEXT,
                    description="卡片摘要",
                    tokenization=Tokenization.WORD,
                    index_filterable=True,
                    index_searchable=True
                ),
                Property(
                    name="datasource_id",
                    data_type=DataType.TEXT,
                    description="数据源id",
                    tokenization=Tokenization.FIELD,
                    index_filterable=True,
                    index_searchable=False
                )
            ],
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE
                )
            )
        )
        print(f"    [COLLECTION] 创建新 collection: {target}")
        return target


def delete_collection(class_name: str) -> bool:
    """删除 collection"""
    target = _normalize_class_name(class_name)
    try:
        with weaviate_client_local() as client:
            if client.collections.exists(target):
                client.collections.delete(target)
                print(f"    [COLLECTION] 已删除: {target}")
                return True
            else:
                print(f"    [COLLECTION] 不存在，跳过: {target}")
                return True
    except Exception as e:
        print(f"    [COLLECTION] 删除失败: {e}")
        return False


def get_weaviate_count(class_name: str) -> int:
    """获取 collection 中的记录数"""
    target = _normalize_class_name(class_name)
    try:
        with weaviate_client_local() as client:
            if not client.collections.exists(target):
                return 0
            col = client.collections.get(target)
            result = col.aggregate.over_all(total_count=True)
            return result.total_count
    except Exception:
        return 0


def list_weaviate_collections() -> Set[str]:
    """列出所有 collection"""
    try:
        with weaviate_client_local() as client:
            return set(client.collections.list_all().keys())
    except Exception:
        return set()


def insert_vector(data_card_obj: dict, class_name: str):
    """
    将卡片数据写入向量库
    需要 Flask 应用上下文（用于 qwen_llm_embeddings）
    """
    from app import create_app
    from controllers.weaviate_db_tool.weaviate_api import add_vector

    app = create_app()
    with app.app_context():
        return add_vector(data_card_obj, class_name=class_name)


# ========================================
# 数据结构
# ========================================

@dataclass
class UserInfo:
    """用户信息"""
    user_id: str
    username: str
    email: str
    weaviate_class_name: str
    has_datasource: bool = False
    datacards_count: int = 0


@dataclass
class DatacardRecord:
    """数据卡片记录"""
    card_id: int
    doc_id: str
    w_uuid: str
    user_id: str
    datasource_id: str
    card_data: str
    card_data_obj: dict
    need_migration: bool = False
    new_w_uuid: Optional[str] = None


@dataclass
class MigrationResult:
    """迁移结果"""
    user_id: str
    username: str
    class_name: str
    total: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


# ========================================
# 数据库操作
# ========================================

def create_db_engine() -> Engine:
    """创建数据库引擎"""
    return create_engine(DATABASE_URL, future=True, pool_pre_ping=True)


def fetch_all_users(engine: Engine) -> List[UserInfo]:
    """获取所有用户"""
    sql = text(f"""
        SELECT
            u.id::text,
            COALESCE(u.username, ''),
            COALESCE(u.email, ''),
            COALESCE(u.weaviate_class_name, ''),
            CASE WHEN EXISTS (
                SELECT 1 FROM "{T_DATACARDS}" dc WHERE dc.user_id = u.id LIMIT 1
            ) THEN true ELSE false END as has_datacards
        FROM "{T_USERS}" u
        WHERE u.status = 'normal' OR u.status IS NULL
        ORDER BY u.created_at DESC NULLS LAST, u.username
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()

    users = []
    for r in rows:
        user = UserInfo(
            user_id=str(r[0]),
            username=str(r[1]),
            email=str(r[2]),
            weaviate_class_name=str(r[3]) if r[3] else "",
            has_datasource=r[4]
        )
        users.append(user)

    return users


def fetch_user_datacards(engine: Engine, user_id: str) -> List[DatacardRecord]:
    """获取用户的所有 datacards"""
    sql = text(f"""
        SELECT
            dc.id,
            dc.doc_id::text,
            dc.w_uuid::text,
            dc.user_id::text,
            dc.datasource_id::text,
            dc.card_data
        FROM "{T_DATACARDS}" dc
        WHERE dc.user_id = :user_id
        ORDER BY dc.id
    """)

    records = []
    with engine.begin() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).fetchall()

    for r in rows:
        card_id, doc_id, w_uuid, uid, datasource_id, card_data = r

        # 处理 datasource_id 为 NULL 的情况
        if datasource_id is None:
            datasource_id_str = ""
        else:
            datasource_id_str = str(datasource_id) if datasource_id else ""

        try:
            card_obj = json.loads(card_data) if card_data else {}
        except Exception:
            card_obj = {}

        # 检查是否需要迁移
        doc_info = card_obj.get("DocInfo", {})
        existing_ds_id = doc_info.get("datasource_id")

        # 需要迁移的条件：card_data中没有datasource_id 且 数据库中有有效的datasource_id
        record = DatacardRecord(
            card_id=int(card_id),
            doc_id=str(doc_id),
            w_uuid=str(w_uuid) if w_uuid else "",
            user_id=str(uid),
            datasource_id=datasource_id_str,
            card_data=card_data,
            card_data_obj=card_obj,
            need_migration=(not existing_ds_id and datasource_id_str)
        )
        records.append(record)

    return records


def fetch_user_datacards_count(engine: Engine, user_id: str) -> int:
    """获取用户的 datacards 数量"""
    sql = text(f'SELECT COUNT(*) FROM "{T_DATACARDS}" WHERE user_id = :user_id')
    with engine.begin() as conn:
        return conn.execute(sql, {"user_id": user_id}).scalar_one()


def update_card_data_and_wuuid(
    engine: Engine,
    card_id: int,
    new_card_data: str,
    new_w_uuid: str
) -> bool:
    """更新 datacard"""
    sql = text(f"""
        UPDATE "{T_DATACARDS}"
        SET card_data = :card_data,
            w_uuid = :w_uuid,
            updated_at = NOW()
        WHERE id = :card_id
    """)
    try:
        with engine.begin() as conn:
            conn.execute(sql, {
                "card_data": new_card_data,
                "w_uuid": new_w_uuid,
                "card_id": card_id
            })
        return True
    except Exception as e:
        print(f"      [DB ERROR] card_id={card_id}: {e}")
        return False


def ensure_user_has_weaviate_class(engine: Engine, user_id: str, username: str) -> str:
    """确保用户有 weaviate_class_name，如果没有则创建"""
    # 查询用户的 weaviate_class_name
    sql = text(f'SELECT weaviate_class_name FROM "{T_USERS}" WHERE id = :user_id')
    with engine.begin() as conn:
        result = conn.execute(sql, {"user_id": user_id}).fetchone()

    if result and result[0]:
        return str(result[0])

    # 创建新的 class name
    class_name = f"datacard_datasource__{user_id.replace('-', '_')}"

    # 更新数据库
    update_sql = text(f'UPDATE "{T_USERS}" SET weaviate_class_name = :class_name WHERE id = :user_id')
    with engine.begin() as conn:
        conn.execute(update_sql, {"class_name": class_name, "user_id": user_id})

    print(f"    [NEW CLASS] 为用户 {username} 创建新的 weaviate_class_name: {class_name}")
    return class_name


# ========================================
# 检查函数
# ========================================

def check_all_users(engine: Engine) -> Dict:
    """
    检查所有用户的数据状态
    """
    print("\n" + "=" * 80)
    print("【全量检查】检查所有用户的数据状态")
    print("=" * 80)

    users = fetch_all_users(engine)
    existing_collections = list_weaviate_collections()

    stats = {
        "total_users": len(users),
        "users_with_class": 0,
        "users_without_class": 0,
        "users_with_datacards": 0,
        "users_need_migration": 0,
        "total_datacards": 0,
        "datacards_need_migration": 0,
        "users_with_weaviate_mismatch": 0,
    }

    user_details = []

    for user in users:
        detail = {
            "user_id": user.user_id,
            "username": user.username,
            "has_class": bool(user.weaviate_class_name),
            "class_exists": user.weaviate_class_name in existing_collections,
            "has_datacards": user.has_datasource,
            "datacards_count": 0,
            "need_migration": False,
            "weaviate_count": 0,
            "issues": []
        }

        if user.weaviate_class_name:
            stats["users_with_class"] += 1
            if user.weaviate_class_name in existing_collections:
                detail["weaviate_count"] = get_weaviate_count(user.weaviate_class_name)
            else:
                detail["issues"].append("class_not_in_weaviate")
                stats["users_with_weaviate_mismatch"] += 1
        else:
            stats["users_without_class"] += 1

        if user.has_datasource:
            stats["users_with_datacards"] += 1
            datacards = fetch_user_datacards(engine, user.user_id)
            detail["datacards_count"] = len(datacards)
            stats["total_datacards"] += len(datacards)

            # 检查是否需要迁移
            need_migration = [d for d in datacards if d.need_migration]
            if need_migration:
                detail["need_migration"] = True
                detail["need_migration_count"] = len(need_migration)
                stats["datacards_need_migration"] += len(need_migration)
                stats["users_need_migration"] += 1

            # 检查数据对齐
            if user.weaviate_class_name and user.weaviate_class_name in existing_collections:
                if detail["weaviate_count"] != detail["datacards_count"]:
                    detail["issues"].append(f"count_mismatch_db{detail['datacards_count']}_weaviate{detail['weaviate_count']}")

        user_details.append(detail)

    # 打印统计
    print(f"\n总体统计：")
    print(f"  - 总用户数: {stats['total_users']}")
    print(f"  - 有 weaviate_class_name 的用户: {stats['users_with_class']}")
    print(f"  - 无 weaviate_class_name 的用户: {stats['users_without_class']}")
    print(f"  - 有 datacards 的用户: {stats['users_with_datacards']}")
    print(f"  - 有 datacards 的总记录数: {stats['total_datacards']}")
    print(f"  - 需要迁移的用户: {stats['users_need_migration']}")
    print(f"  - 需要迁移的记录: {stats['datacards_need_migration']}")
    print(f"  - 向量库不存在的用户: {stats['users_with_weaviate_mismatch']}")

    # 列出需要迁移的用户
    users_to_migrate = [u for u in user_details if u["need_migration"]]
    if users_to_migrate:
        print(f"\n需要迁移的用户列表：")
        for u in users_to_migrate[:20]:
            print(f"  - {u['username']} ({u['user_id']}): {u.get('need_migration_count', 0)} 条需要迁移")
        if len(users_to_migrate) > 20:
            print(f"  ... 还有 {len(users_to_migrate) - 20} 个用户")

    # 列出有问题的用户
    users_with_issues = [u for u in user_details if u["issues"]]
    if users_with_issues:
        print(f"\n存在问题的用户：")
        for u in users_with_issues[:20]:
            print(f"  - {u['username']} ({u['user_id']}): {', '.join(u['issues'])}")
        if len(users_with_issues) > 20:
            print(f"  ... 还有 {len(users_with_issues) - 20} 个用户")

    return {
        "stats": stats,
        "user_details": user_details
    }


# ========================================
# 迁移函数
# ========================================

def migrate_single_card(
    record: DatacardRecord,
    class_name: str,
    engine: Engine,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    迁移单条卡片记录
    返回: (success, error_message)
    """
    try:
        # 1. 修改 card_data，补上 datasource_id
        card_obj = record.card_data_obj.copy()
        if "DocInfo" not in card_obj:
            card_obj["DocInfo"] = {}
        card_obj["DocInfo"]["datasource_id"] = record.datasource_id
        new_card_data = json.dumps(card_obj, ensure_ascii=False)

        if dry_run:
            return True, ""

        # 2. 重新入向量库
        try:
            new_w_uuid = insert_vector(card_obj, class_name=class_name)
            new_w_uuid = str(new_w_uuid)
        except Exception as e:
            return False, f"vector_insert_failed: {e}"

        # 3. 更新数据库
        if not update_card_data_and_wuuid(engine, record.card_id, new_card_data, new_w_uuid):
            return False, "database_update_failed"

        return True, ""

    except Exception as e:
        return False, str(e)


def migrate_user_all(
    engine: Engine,
    user: UserInfo,
    dry_run: bool = False
) -> MigrationResult:
    """
    迁移单个用户的所有数据
    """
    result = MigrationResult(
        user_id=user.user_id,
        username=user.username,
        class_name=user.weaviate_class_name or f"datacard_datasource__{user.user_id.replace('-', '_')}"
    )

    print(f"\n{'=' * 60}")
    print(f"【迁移用户】{user.username} ({user.user_id})")
    print(f"{'=' * 60}")

    # 1. 确保用户有 weaviate_class_name
    class_name = user.weaviate_class_name
    if not class_name:
        print(f"[STEP 0] 用户没有 weaviate_class_name，创建中...")
        class_name = ensure_user_has_weaviate_class(engine, user.user_id, user.username)
        result.class_name = class_name
    else:
        print(f"[STEP 0] 用户已有 class_name: {class_name}")

    # 2. 获取所有 datacards
    print(f"[STEP 1] 获取 datacards...")
    datacards = fetch_user_datacards(engine, user.user_id)
    result.total = len(datacards)
    print(f"  总记录数: {result.total}")

    if not datacards:
        print(f"  无需迁移（没有 datacards）")
        return result

    # 3. 分离需要迁移和不需要迁移的记录
    to_migrate = [d for d in datacards if d.need_migration]
    already_ok = [d for d in datacards if not d.need_migration]

    print(f"  - 已完成（不需要迁移）: {len(already_ok)}")
    print(f"  - 需要迁移: {len(to_migrate)}")

    if not to_migrate:
        print(f"\n[RESULT] 所有记录已是最新的，无需迁移")
        result.ok = len(already_ok)
        result.skipped = len(already_ok)
        return result

    # 4. 重建向量库 collection
    print(f"\n[STEP 2] 重建向量库 collection: {class_name}")

    if not dry_run:
        try:
            # 删除旧的
            delete_collection(class_name)
            # 创建新的
            ensure_collection_with_datasource_id(class_name)
        except Exception as e:
            print(f"  [ERROR] 重建 collection 失败: {e}")
            result.failed = len(to_migrate)
            result.errors.append(f"collection_rebuild_failed: {e}")
            return result
    else:
        print(f"  [DRY-RUN] 跳过重建")

    # 5. 迁移记录
    print(f"\n[STEP 3] 迁移 {len(to_migrate)} 条记录...")

    for i, record in enumerate(to_migrate, 1):
        if i % 20 == 0:
            print(f"  进度: {i}/{len(to_migrate)}")

        success, error = migrate_single_card(record, class_name, engine, dry_run=dry_run)

        if success:
            result.ok += 1
            if not dry_run:
                print(f"    [OK] card_id={record.card_id} doc_id={record.doc_id}")
        else:
            result.failed += 1
            result.errors.append(f"card_id={record.card_id}: {error}")
            print(f"    [FAIL] card_id={record.card_id}: {error}")

        if not dry_run and SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    # 6. 将已完成的记录重新入向量库
    if already_ok and not dry_run:
        print(f"\n[STEP 4] 重新入 {len(already_ok)} 条已完成的记录...")
        for i, record in enumerate(already_ok, 1):
            if i % 50 == 0:
                print(f"  进度: {i}/{len(already_ok)}")

            try:
                new_w_uuid = insert_vector(record.card_data_obj, class_name=class_name)
                update_card_data_and_wuuid(engine, record.card_id, record.card_data, str(new_w_uuid))
                result.ok += 1
            except Exception as e:
                result.errors.append(f"reinsert_card_id={record.card_id}: {e}")
                print(f"    [WARN] card_id={record.card_id} reinsert failed: {e}")

            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)

    print(f"\n[RESULT] ok={result.ok}, failed={result.failed}, total={result.total}")

    return result


def migrate_all_users(engine: Engine, dry_run: bool = False) -> List[MigrationResult]:
    """
    迁移所有用户
    """
    print("\n" + "#" * 80)
    print("# 【全量迁移】迁移所有用户的数据")
    print(f"# 模式: {'DRY-RUN (模拟)' if dry_run else '正式迁移'}")
    print("#" * 80)

    # 1. 获取所有用户
    print(f"\n[STEP 0] 获取所有用户...")
    users = fetch_all_users(engine)

    # 2. 筛选需要迁移的用户（有 datacards 且需要迁移）
    users_to_migrate = []
    for user in users:
        if user.has_datasource:
            datacards = fetch_user_datacards(engine, user.user_id)
            if any(d.need_migration for d in datacards):
                users_to_migrate.append(user)

    print(f"\n扫描结果：")
    print(f"  - 总用户数: {len(users)}")
    print(f"  - 有 datacards 的用户: {len([u for u in users if u.has_datasource])}")
    print(f"  - 需要迁移的用户: {len(users_to_migrate)}")

    if not users_to_migrate:
        print(f"\n所有数据已是最新的，无需迁移！")
        return []

    # 3. 逐个迁移用户
    print(f"\n{'=' * 80}")
    print(f"[STEP 1] 开始迁移 {len(users_to_migrate)} 个用户...")
    print(f"{'=' * 80}")

    all_results = []
    total_ok = 0
    total_failed = 0
    total_skipped = 0

    for i, user in enumerate(users_to_migrate, 1):
        print(f"\n\n{'#' * 60}")
        print(f"# 用户 {i}/{len(users_to_migrate)}: {user.username} ({user.user_id})")
        print(f"{'#' * 60}")

        result = migrate_user_all(engine, user, dry_run=dry_run)
        all_results.append(result)

        total_ok += result.ok
        total_failed += result.failed
        total_skipped += result.skipped

    # 4. 汇总
    print(f"\n" + "#" * 80)
    print(f"# 【迁移汇总】")
    print(f"#" + "=" * 78)
    print(f"# 处理用户数: {len(all_results)}")
    print(f"# 总记录数: {total_ok + total_failed + total_skipped}")
    print(f"# 成功: {total_ok}")
    print(f"# 失败: {total_failed}")
    print(f"# 跳过: {total_skipped}")
    print(f"# 模式: {'DRY-RUN' if dry_run else '正式迁移'}")
    print(f"#" + "=" * 78)

    if dry_run:
        print(f"\n[提示] 这是 DRY-RUN 模式，未执行任何实际变更。")
        print(f"[提示] 确认无误后，使用 --mode migrate 执行正式迁移。")

    return all_results


# ========================================
# 最终校验函数
# ========================================

def final_verification(engine: Engine) -> Dict:
    """
    最终一致性校验
    确保：
    1. 所有用户的 card_data.DocInfo.datasource_id 都已补全
    2. 所有用户的向量库都包含 datasource_id 属性
    3. 数据库记录数与向量库记录数完全一致
    """
    print("\n" + "#" * 80)
    print("# 【最终校验】数据一致性验证")
    print("#" + "=" * 78)

    users = fetch_all_users(engine)
    existing_collections = list_weaviate_collections()

    verification_results = {
        "total_users": len(users),
        "users_passed": 0,
        "users_failed": 0,
        "total_datacards": 0,
        "datacards_verified": 0,
        "datacards_failed": 0,
        "weaviate_db_matched": True,
        "details": []
    }

    failed_users = []

    for user in users:
        if not user.has_datasource:
            continue

        user_result = {
            "user_id": user.user_id,
            "username": user.username,
            "class_name": user.weaviate_class_name,
            "datacards_count": 0,
            "weaviate_count": 0,
            "card_data_issues": [],
            "status": "PASS"
        }

        # 获取 datacards
        datacards = fetch_user_datacards(engine, user.user_id)
        user_result["datacards_count"] = len(datacards)
        verification_results["total_datacards"] += len(datacards)

        # 检查 card_data
        for dc in datacards:
            doc_info = dc.card_data_obj.get("DocInfo", {})
            existing_ds_id = doc_info.get("datasource_id")

            if not existing_ds_id:
                user_result["card_data_issues"].append(f"card_id={dc.card_id}: 缺少 datasource_id")
                user_result["status"] = "FAIL"
                verification_results["datacards_failed"] += 1
            else:
                verification_results["datacards_verified"] += 1

        # 检查向量库
        if user.weaviate_class_name:
            weaviate_count = get_weaviate_count(user.weaviate_class_name)
            user_result["weaviate_count"] = weaviate_count

            if weaviate_count != len(datacards):
                user_result["status"] = "FAIL"
                verification_results["weaviate_db_matched"] = False
                user_result["card_data_issues"].append(
                    f"记录数不匹配: DB={len(datacards)}, Weaviate={weaviate_count}"
                )

        verification_results["details"].append(user_result)

        if user_result["status"] == "PASS":
            verification_results["users_passed"] += 1
        else:
            verification_results["users_failed"] += 1
            failed_users.append(user_result)

    # 打印结果
    print(f"\n校验结果：")
    print(f"  - 总用户数（带 datacards）: {len([u for u in users if u.has_datasource])}")
    print(f"  - 通过: {verification_results['users_passed']}")
    print(f"  - 失败: {verification_results['users_failed']}")
    print(f"  - 总 datacards: {verification_results['total_datacards']}")
    print(f"  - 已校验: {verification_results['datacards_verified']}")
    print(f"  - 有问题: {verification_results['datacards_failed']}")
    print(f"  - 向量库与数据库一致: {'是' if verification_results['weaviate_db_matched'] else '否'}")

    if failed_users:
        print(f"\n失败的用户详情：")
        for u in failed_users[:10]:
            print(f"\n  用户: {u['username']} ({u['user_id']})")
            print(f"    Class: {u['class_name']}")
            print(f"    DB记录数: {u['datacards_count']}")
            print(f"    Weaviate记录数: {u['weaviate_count']}")
            print(f"    问题:")
            for issue in u['card_data_issues']:
                print(f"      - {issue}")

        if len(failed_users) > 10:
            print(f"\n  ... 还有 {len(failed_users) - 10} 个用户有问题")

    # 打印通过的统计
    passed_users = [u for u in verification_results["details"] if u["status"] == "PASS"]
    if passed_users:
        print(f"\n通过的用户数: {len(passed_users)}")

    return verification_results


# ========================================
# 主入口
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description="数据卡片迁移脚本 - 适配新版 schema（全量）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 1. 检查所有用户的数据状态
  python test/migrate_datacard_to_new_schema.py --mode check

  # 2. 模拟迁移（不实际修改）
  python test/migrate_datacard_to_new_schema.py --mode migrate --dry-run

  # 3. 执行正式迁移
  python test/migrate_datacard_to_new_schema.py --mode migrate

  # 4. 完整流程（检查 + 迁移 + 校验）
  python test/migrate_datacard_to_new_schema.py --mode full

  # 5. 最终校验（验证数据一致性）
  python test/migrate_datacard_to_new_schema.py --mode verify

  # 6. 指定数据库
  python test/migrate_datacard_to_new_schema.py --mode check --database-url "postgresql+psycopg2://..."
"""
    )
    parser.add_argument(
        "--mode",
        choices=["check", "migrate", "full", "verify"],
        default="check",
        help="模式: check=检查, migrate=迁移, full=完整流程, verify=最终校验"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，不执行实际变更"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        help="数据库连接 URL（可选，默认使用环境变量）"
    )

    args = parser.parse_args()

    # 更新数据库连接
    global DATABASE_URL
    if args.database_url:
        DATABASE_URL = args.database_url
        print(f"[CONFIG] 使用指定的数据库: {DATABASE_URL[:50]}...")

    engine = create_db_engine()

    try:
        if args.mode == "check":
            check_all_users(engine)

        elif args.mode == "migrate":
            migrate_all_users(engine, dry_run=args.dry_run)

        elif args.mode == "full":
            print("\n" + "=" * 80)
            print("【完整流程】检查 + 迁移 + 校验")
            print("=" * 80)

            # Step 1: 检查
            print("\n\n" + "#" * 40)
            print("# 第一步：检查")
            print("#" * 40)
            check_all_users(engine)

            # 询问是否继续
            if not args.dry_run:
                response = input("\n检查完成，是否继续迁移？(y/N): ").strip().lower()
                if response != 'y':
                    print("已取消")
                    return

            # Step 2: 迁移
            print("\n\n" + "#" * 40)
            print("# 第二步：迁移")
            print("#" * 40)
            migrate_all_users(engine, dry_run=args.dry_run)

            # Step 3: 校验
            print("\n\n" + "#" * 40)
            print("# 第三步：最终校验")
            print("#" * 40)
            final_verification(engine)

        elif args.mode == "verify":
            final_verification(engine)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
