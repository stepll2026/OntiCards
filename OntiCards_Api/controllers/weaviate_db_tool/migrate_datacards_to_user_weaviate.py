"""
 @File: migrate_datacards_to_user_weaviate.py
 @Description: 迁移用户的向量数据
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-12 11:31
"""

"""
迁移 datacards_datasource 中的向量到对应用户的 Weaviate 检索空间，并回写 w_uuid

关联规则：
- datacards_datasource.doc_id = user_datasource_schemas.id
- user_datasource_schemas.user_id -> users.weaviate_class_name

要求：
- users.weaviate_class_name 已回填（你已完成）
- 每个 users.weaviate_class_name 对应的 Weaviate collection 已创建（严格模式：不存在会报错）
- weaviate_api.add_vector 为严格模式（class_name 为空/不存在会报错）

运行方式：
- 设置环境变量 DATABASE_URL
  Windows(cmd):
    set DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
  PowerShell:
    $env:DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/dbname"

- 先 dry-run：
    python migrate_datacards_to_user_weaviate.py
- 确认没问题后把 DRY_RUN = False 再跑
"""

import json
import time
from typing import Optional

from sqlalchemy import create_engine, text

from app import create_app  # 注入上下文
# 直接复用项目里的写向量逻辑（会做 embedding + 写入 weaviate）
from controllers.weaviate_db_tool.weaviate_api import add_vector

# ========= 配置区 =========
DATABASE_URL = "postgresql+psycopg2://postgres:master_pz123@118.145.205.100:55432/dev-db-connector"

# 表名（按模型文件：users / user_datasource_schemas / datacards_datasource）
T_USERS = "users"
T_SCHEMAS = "user_datasource_schemas"
T_CARDS = "datacards_datasource"

# 建议第一次先 dry-run
# DRY_RUN = True   # 模拟运行，库中不生效
DRY_RUN = False   # 实际运行，库中生效

# 批处理参数
BATCH_SIZE = 200          # 每次从 DB 拉多少条进行迁移
SLEEP_SECONDS = 0.0       # 如果你担心 weaviate/embedding 压力，可设置 0.01~0.1

# 迁移过滤策略：
# - ONLY_WHEN_WUUID_IS_NULL=True：只迁移 w_uuid 为空的记录（适合“增量补齐”）
# - False：全量迁移（会重写所有向量并更新 w_uuid）
ONLY_WHEN_WUUID_IS_NULL = False


def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception:
        return None


def main():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "Please set env DATABASE_URL, e.g.\n"
            "  postgresql+psycopg2://user:pass@host:5432/dbname"
        )

    engine = create_engine(DATABASE_URL, future=True)

    # 选取待迁移记录：join cards -> schemas -> users
    # 取：card表主键id、doc_id、card_data、旧w_uuid、user_id、user_class
    where_extra = ""
    if ONLY_WHEN_WUUID_IS_NULL:
        where_extra = f" AND (c.w_uuid IS NULL OR c.w_uuid = '') "

    select_sql = text(f"""
        SELECT
            c.id              AS card_pk,
            c.doc_id          AS doc_id,
            c.card_data       AS card_data,
            c.w_uuid          AS old_w_uuid,
            s.user_id         AS user_id,
            u.weaviate_class_name AS user_class
        FROM "{T_CARDS}" c
        JOIN "{T_SCHEMAS}" s
          ON c.doc_id = CAST(s.id AS VARCHAR)
        JOIN "{T_USERS}" u
          ON s.user_id = u.id
        WHERE 1=1
          AND u.weaviate_class_name IS NOT NULL
          AND u.weaviate_class_name <> ''
          {where_extra}
        ORDER BY c.id
        LIMIT :limit OFFSET :offset
    """)

    update_sql = text(f"""
        UPDATE "{T_CARDS}"
        SET w_uuid = :new_w_uuid
        WHERE id = :card_pk
    """)

    # 统计总量（用于进度展示）
    count_sql = text(f"""
        SELECT COUNT(1)
        FROM "{T_CARDS}" c
        JOIN "{T_SCHEMAS}" s
          ON c.doc_id = CAST(s.id AS VARCHAR)
        JOIN "{T_USERS}" u
          ON s.user_id = u.id
        WHERE 1=1
          AND u.weaviate_class_name IS NOT NULL
          AND u.weaviate_class_name <> ''
          {where_extra}
    """)

    with engine.begin() as conn:
        total = conn.execute(count_sql).scalar_one()
    print(f"[INFO] total rows to migrate: {total} (dry_run={DRY_RUN}, batch={BATCH_SIZE}, only_null_wuuid={ONLY_WHEN_WUUID_IS_NULL})")

    migrated = 0
    failed = 0
    offset = 0

    while True:
        with engine.begin() as conn:
            rows = conn.execute(select_sql, {"limit": BATCH_SIZE, "offset": offset}).fetchall()

        if not rows:
            break

        for r in rows:
            card_pk = r.card_pk
            doc_id = str(r.doc_id)
            card_data_str = r.card_data
            old_w_uuid = r.old_w_uuid
            user_id = str(r.user_id)
            user_class = r.user_class

            # 1) 解析 card_data
            card_obj = _safe_json_loads(card_data_str or "")
            if not isinstance(card_obj, dict):
                print(f"[FAIL] card_pk={card_pk} doc_id={doc_id} user_id={user_id} reason=card_data_not_json")
                failed += 1
                continue

            # 2) 强一致：确保 DocInfo.doc_id 存在（你生成卡片时本来就会带）
            docinfo = card_obj.get("DocInfo")
            if not isinstance(docinfo, dict):
                card_obj["DocInfo"] = {"doc_id": doc_id}
            else:
                if not docinfo.get("doc_id"):
                    docinfo["doc_id"] = doc_id

            # 3) 写入目标用户 class（严格模式：class 不存在会直接抛错）
            try:
                if DRY_RUN:
                    new_uuid = "DRY_RUN_UUID"
                else:
                    new_uuid = add_vector(card_obj, class_name=user_class)
                    new_uuid = str(new_uuid)
            except Exception as e:
                print(f"[FAIL] card_pk={card_pk} doc_id={doc_id} user_id={user_id} class={user_class} old_w_uuid={old_w_uuid} err={e}")
                failed += 1
                continue

            # 4) 回写 DB 的 w_uuid
            try:
                if not DRY_RUN:
                    with engine.begin() as conn:
                        conn.execute(update_sql, {"new_w_uuid": new_uuid, "card_pk": card_pk})
                migrated += 1
                print(f"[OK] card_pk={card_pk} doc_id={doc_id} user_id={user_id} class={user_class} old={old_w_uuid} new={new_uuid}")
            except Exception as e:
                print(f"[FAIL_DB] card_pk={card_pk} doc_id={doc_id} new_uuid={new_uuid} err={e}")
                failed += 1
                continue

            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)

        offset += BATCH_SIZE
        print(f"[PROGRESS] migrated={migrated} failed={failed} / total={total}")

    print(f"[DONE] migrated={migrated} failed={failed} total={total} dry_run={DRY_RUN}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        main()
