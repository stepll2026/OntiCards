"""
 @File: backfill_weaviate_class_name.py
 @Description: 生成用户的独立向量检索空间-回填到数据库中的 weaviate_class_name 字段
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-12 11:03
"""

from sqlalchemy import create_engine, text

PREFIX = "datacard_datasource__"

DATABASE_URL = "postgresql+psycopg2://postgres:master_pz123@118.145.205.100:55432/dev-db-connector"


def build_weaviate_class_name(user_id: str) -> str:
    return f"{PREFIX}{str(user_id).replace('-', '_')}"


def main(dry_run: bool = True, table_name: str = "users"):
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Please set env DATABASE_URL, e.g.\n"
            "  set DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname"
        )

    engine = create_engine(DATABASE_URL, future=True)

    # 注意：如果你的用户表不是 "users"，把 table_name 改成实际表名（比如 users）
    select_sql = text(f"""
        SELECT id, weaviate_class_name
        FROM "{table_name}"
        WHERE weaviate_class_name IS NULL OR weaviate_class_name = ''
        ORDER BY id
    """)

    update_sql = text(f"""
        UPDATE "{table_name}"
        SET weaviate_class_name = :class_name
        WHERE id = :user_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(select_sql).fetchall()
        print(f"[INFO] rows to backfill: {len(rows)} (table={table_name})")

        updated = 0
        for user_id, current_val in rows:
            new_val = build_weaviate_class_name(user_id)
            print(f"[PLAN] user_id={user_id} -> {new_val}")

            if not dry_run:
                conn.execute(update_sql, {"class_name": new_val, "user_id": user_id})
                updated += 1

        if dry_run:
            print("[DRY-RUN] no database changes applied")
        else:
            print(f"[DONE] updated={updated}")


if __name__ == "__main__":
    # 第一次建议 dry_run=True，确认输出没问题后再改 False
    # main(dry_run=True, table_name="users")   # 模拟运行，库中不生效
    main(dry_run=False, table_name="users") # 实际运行，库中生效
