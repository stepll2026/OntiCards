"""
 @File: init_user_weaviate_collections.py
 @Description: 在 weaviate 中建立用户对应的独立检索class
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-12 13:39
"""

import os
import copy
from sqlalchemy import create_engine, text

from controllers.weaviate_db_tool.weaviate_api import weaviate_client, _normalize_class_name, schema as BASE_SCHEMA

DATABASE_URL = "postgresql+psycopg2://postgres:master_pz123@118.145.205.100:55432/dev-db-connector"
T_USERS = "users"

def build_schema_for_class(class_name: str) -> dict:
    # 深拷贝：保证不污染 BASE_SCHEMA
    s = copy.deepcopy(BASE_SCHEMA)
    s["class"] = class_name
    return s


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(DATABASE_URL, future=True)

    # 取出所有已有的 weaviate_class_name
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT weaviate_class_name
            FROM "{T_USERS}"
            WHERE weaviate_class_name IS NOT NULL AND weaviate_class_name <> ''
        """)).fetchall()

    # 规范化（- -> _）并去重
    class_names = sorted({_normalize_class_name(r[0]) for r in rows if r[0]})
    print(f"[INFO] total class_names in users: {len(class_names)}")

    created = 0
    existed = 0
    failed = 0

    with weaviate_client() as client:
        for c in class_names:
            try:
                if client.collections.exists(c):
                    existed += 1
                    continue

                s = build_schema_for_class(c)
                client.collections.create_from_dict(s)
                created += 1
                print(f"[CREATE] {c}")

            except Exception as e:
                failed += 1
                print(f"[FAIL] create collection {c} err={e}")

    print(f"[DONE] created={created}, existed={existed}, failed={failed}")


if __name__ == "__main__":
    main()