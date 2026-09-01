#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对比两个 PostgreSQL 数据库中相同表的记录数是否一致

功能：
- 指定几张表名
- 分别连接两个数据库
- 查询 COUNT(*)
- 输出差异报告
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# =============================
# 1️⃣ 修改两个数据库连接信息
# =============================

DB_OLD = {
    "host": "8.134.183.233",
    "port": 55432,
    "database": "dev-db-connector",
    "user": "postgres",
    "password": "master_pz123",
}

DB_NEW = {
    "host": "8.134.183.233",
    "port": 55432,
    "database": "cqxtest",
    "user": "postgres",
    "password": "master_pz123",
}

SCHEMA = "public"

# =============================
# 2️⃣ 需要对比的表
# =============================
TABLES = [
    "datacards_datasource",
    "user_datasource_schemas",
    "datasource_infos",
    # 你可以继续加表
]


# =============================
# 3️⃣ 工具函数
# =============================

def connect(conn_info):
    return psycopg2.connect(**conn_info)


def get_count(conn, schema, table):
    sql = f'SELECT COUNT(*) AS c FROM "{schema}"."{table}";'
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchone()["c"]


# =============================
# 4️⃣ 主逻辑
# =============================

def main():
    print("====== 开始对比表记录数 ======")

    conn_old = connect(DB_OLD)
    conn_new = connect(DB_NEW)

    try:
        results = []

        for table in TABLES:
            try:
                count_old = get_count(conn_old, SCHEMA, table)
            except Exception as e:
                print(f"[OLD ERROR] {table}: {e}")
                count_old = None

            try:
                count_new = get_count(conn_new, SCHEMA, table)
            except Exception as e:
                print(f"[NEW ERROR] {table}: {e}")
                count_new = None

            status = "一致" if count_old == count_new else "❌ 不一致"

            print(f"{table:35} | OLD={count_old} | NEW={count_new} | {status}")

            results.append((table, count_old, count_new, status))

        # 汇总
        print("\n====== 汇总结果 ======")
        mismatch = [r for r in results if r[3] != "一致"]

        if not mismatch:
            print("✅ 所有表记录数一致")
        else:
            print("❌ 以下表记录数不一致：")
            for r in mismatch:
                print(f"   {r[0]}  OLD={r[1]}  NEW={r[2]}")

    finally:
        conn_old.close()
        conn_new.close()


if __name__ == "__main__":
    main()
