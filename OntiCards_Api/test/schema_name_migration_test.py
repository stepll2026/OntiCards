"""
schema_name 字段迁移验证脚本
验证数据库迁移后：
1. user_datasource_schemas 表结构正确（schema_name 列、约束、索引）
2. datasource_infos 表约束正确
3. schema_name 回填结果正确

使用方法：
1. 修改下方的 DB_CONFIG 配置
2. python test/schema_name_migration_test.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Tuple

# =============================
# 修改这里的数据库连接信息
# =============================

DB_CONFIG = {
    "host": "8.134.183.233",
    "port": 55432,
    "database": "init_test",  # TODO: 修改为你的数据库名
    "user": "postgres",
    "password": "master_pz123"
}

# 验证的 schema（PostgreSQL 通常是 public）
SCHEMA = "public"


# =============================
# 工具函数
# =============================

def connect():
    return psycopg2.connect(**DB_CONFIG)


def q(conn, sql: str, params: tuple = ()) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def check_table_exists(conn, table_name: str) -> bool:
    """检查表是否存在"""
    result = q(conn, """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
    """, (SCHEMA, table_name))
    return len(result) > 0


def check_column_exists(conn, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    result = q(conn, """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (SCHEMA, table_name, column_name))
    return len(result) > 0


def get_column_comment(conn, table_name: str, column_name: str) -> str:
    """获取列注释"""
    result = q(conn, """
        SELECT col_description((%s || '.' || %s)::regclass::oid, ordinal_position) as comment
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (SCHEMA, table_name, SCHEMA, table_name, column_name))
    return result[0]["comment"] if result else ""


def get_constraints(conn, table_name: str) -> List[dict]:
    """获取表的约束"""
    return q(conn, """
        SELECT
            tc.constraint_name,
            tc.constraint_type,
            string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = %s AND tc.table_name = %s
        GROUP BY tc.constraint_name, tc.constraint_type
        ORDER BY tc.constraint_name
    """, (SCHEMA, table_name))


def get_indexes(conn, table_name: str) -> List[dict]:
    """获取表的索引"""
    return q(conn, """
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = %s AND tablename = %s
        ORDER BY indexname
    """, (SCHEMA, table_name))


def get_table_data(conn, table_name: str, limit: int = 10) -> List[dict]:
    """获取表数据"""
    sql = f'SELECT * FROM "{SCHEMA}"."{table_name}" LIMIT %s'
    return q(conn, sql, (limit,))


# =============================
# 验证函数
# =============================

def verify_user_datasource_schemas(conn) -> bool:
    """验证 user_datasource_schemas 表"""
    print("\n" + "=" * 60)
    print("【验证 user_datasource_schemas 表】")
    print("=" * 60)

    all_ok = True

    # 1. 检查 schema_name 列是否存在
    print("\n1. 检查 schema_name 列...")
    if check_column_exists(conn, "user_datasource_schemas", "schema_name"):
        print("   [OK] schema_name 列存在")

        # 检查列注释
        comment = get_column_comment(conn, "user_datasource_schemas", "schema_name")
        if comment:
            print(f"   [OK] 列注释: {comment}")
        else:
            print("   [WARN] 列注释为空（建议添加）")
    else:
        print("   [FAIL] schema_name 列不存在")
        all_ok = False

    # 2. 检查约束
    print("\n2. 检查约束...")
    constraints = get_constraints(conn, "user_datasource_schemas")
    print(f"   找到 {len(constraints)} 个约束:")

    expected_constraint = "uq_userid_connectinfo_schema_tablename"
    found_constraint = False
    for c in constraints:
        marker = " ← [新约束]" if c["constraint_name"] == expected_constraint else ""
        print(f"   - {c['constraint_name']}: {c['constraint_type']} ({c['columns']}){marker}")
        if c["constraint_name"] == expected_constraint:
            if "schema_name" in c["columns"]:
                found_constraint = True
            else:
                print(f"     [FAIL] 约束列中缺少 schema_name")
                all_ok = False

    if found_constraint:
        print(f"   [OK] 新约束 {expected_constraint} 存在且包含 schema_name")
    else:
        print(f"   [FAIL] 缺少新约束 {expected_constraint}")
        all_ok = False

    # 3. 检查索引
    print("\n3. 检查索引...")
    indexes = get_indexes(conn, "user_datasource_schemas")
    print(f"   找到 {len(indexes)} 个索引:")

    expected_index = "idx_uds_user_conninfo_schema"
    found_index = False
    for idx in indexes:
        marker = " ← [新索引]" if idx["indexname"] == expected_index else ""
        print(f"   - {idx['indexname']}{marker}")
        print(f"     {idx['indexdef']}")
        if idx["indexname"] == expected_index:
            found_index = True

    if found_index:
        print(f"   [OK] 新索引 {expected_index} 存在")
    else:
        print(f"   [WARN] 新索引 {expected_index} 不存在（可能不影响功能）")

    return all_ok


def verify_datasource_infos(conn) -> bool:
    """验证 datasource_infos 表"""
    print("\n" + "=" * 60)
    print("【验证 datasource_infos 表】")
    print("=" * 60)

    all_ok = True

    # 1. 检查 schema_name 列是否存在
    print("\n1. 检查 schema_name 列...")
    if check_column_exists(conn, "datasource_infos", "schema_name"):
        print("   [OK] schema_name 列存在")

        # 检查列注释
        comment = get_column_comment(conn, "datasource_infos", "schema_name")
        if comment:
            print(f"   [OK] 列注释: {comment}")
        else:
            print("   [WARN] 列注释为空")
    else:
        print("   [FAIL] schema_name 列不存在")
        all_ok = False

    # 2. 检查约束
    print("\n2. 检查约束...")
    constraints = get_constraints(conn, "datasource_infos")
    print(f"   找到 {len(constraints)} 个约束:")

    expected_constraint = "uq_user_connect_name"
    found_constraint = False
    for c in constraints:
        marker = " ← [新约束]" if c["constraint_name"] == expected_constraint else ""
        print(f"   - {c['constraint_name']}: {c['constraint_type']} ({c['columns']}){marker}")
        if c["constraint_name"] == expected_constraint:
            found_constraint = True

    if found_constraint:
        print(f"   [OK] 新约束 {expected_constraint} 存在")
    else:
        print(f"   [FAIL] 缺少新约束 {expected_constraint}")
        all_ok = False

    return all_ok


def verify_backfill(conn) -> bool:
    """验证 schema_name 回填结果"""
    print("\n" + "=" * 60)
    print("【验证 schema_name 回填结果】")
    print("=" * 60)

    # 统计回填情况
    print("\n1. 统计 user_datasource_schemas 表...")
    result = q(conn, """
        SELECT
            COUNT(*) as total,
            COUNT(schema_name) as filled,
            COUNT(*) FILTER (WHERE schema_name IS NULL) as null_count
        FROM "{schema}".user_datasource_schemas
    """.format(schema=SCHEMA))

    row = result[0]
    print(f"   总记录数: {row['total']}")
    print(f"   已回填: {row['filled']}")
    print(f"   未回填: {row['null_count']}")

    if row['null_count'] > 0:
        print(f"   [WARN] 有 {row['null_count']} 条记录未回填 schema_name")

    # 抽样检查回填正确性
    print("\n2. 抽样检查回填正确性...")
    result = q(conn, """
        SELECT
            uds.id as uds_id,
            uds.db_type,
            uds.connect_name,
            uds.database_name,
            uds.schema_name as uds_schema,
            di.schema_name as di_schema,
            CASE WHEN uds.schema_name = di.schema_name THEN 'OK' ELSE 'MISMATCH' END as status
        FROM "{schema}".user_datasource_schemas uds
        INNER JOIN "{schema}".datasource_infos di
            ON di.user_id = uds.user_id
            AND di.connect_info = uds.connect_info
            AND di.database_name = uds.database_name
        ORDER BY uds.db_type, uds.connect_name
        LIMIT 10
    """.format(schema=SCHEMA))

    if not result:
        print("   [WARN] 没有找到可以通过 (user_id, connect_info, database_name) 关联的记录")
        return False

    print(f"   抽样检查前 {len(result)} 条:")
    all_ok = True
    for row in result:
        marker = "[OK]" if row['status'] == 'OK' else "[FAIL]"
        print(f"   {marker} {row['db_type']}: {row['connect_name']}")
        print(f"        database: {row['database_name']}")
        print(f"        schema_name: {row['uds_schema']} (datasource_infos: {row['di_schema']})")
        if row['status'] != 'OK':
            all_ok = False

    # 统计匹配情况
    print("\n3. 统计关联匹配情况...")
    result = q(conn, """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN uds.schema_name = di.schema_name THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN uds.schema_name != di.schema_name OR uds.schema_name IS NULL THEN 1 ELSE 0 END) as mismatched
        FROM "{schema}".user_datasource_schemas uds
        INNER JOIN "{schema}".datasource_infos di
            ON di.user_id = uds.user_id
            AND di.connect_info = uds.connect_info
            AND di.database_name = uds.database_name
    """.format(schema=SCHEMA))

    row = result[0]
    print(f"   可关联记录总数: {row['total']}")
    print(f"   匹配（回填正确）: {row['matched']}")
    print(f"   不匹配/未回填: {row['mismatched']}")

    if row['mismatched'] > 0:
        print(f"   [FAIL] 有 {row['mismatched']} 条记录回填不正确")
        return False

    if row['total'] > 0 and row['matched'] == row['total']:
        print("   [OK] 所有可关联记录的 schema_name 回填正确")
        return True

    return all_ok


def verify_helper_functions() -> bool:
    """验证 Python 代码中的 helper 函数"""
    print("\n" + "=" * 60)
    print("【验证 Python 代码中的 helper 函数】")
    print("=" * 60)

    import os
    all_ok = True

    # 检查 database_schema_extractor.py
    print("\n1. 检查 database_schema_extractor.py...")
    extractor_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "controllers", "datasource", "database_schema_extractor.py"
    )

    if os.path.exists(extractor_path):
        with open(extractor_path, encoding="utf-8") as f:
            content = f.read()

        funcs = ["_resolve_schema_name", "_add_schema_filter", "_has_schema_dim"]
        for func in funcs:
            if f"def {func}" in content:
                print(f"   [OK] {func} 存在")
            else:
                print(f"   [FAIL] {func} 不存在")
                all_ok = False
    else:
        print("   [FAIL] 文件不存在")
        all_ok = False

    # 检查 datasource_tool.py 是否调用了 helper
    print("\n2. 检查 datasource_tool.py 调用...")
    tool_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "controllers", "datasource", "datasource_tool.py"
    )

    if os.path.exists(tool_path):
        with open(tool_path, encoding="utf-8") as f:
            content = f.read()

        # 检查是否 import 了 helper 函数
        if "_add_schema_filter" in content:
            print("   [OK] datasource_tool.py 使用了 _add_schema_filter")
        else:
            print("   [WARN] datasource_tool.py 可能未使用 _add_schema_filter")

        if "_has_schema_dim" in content:
            print("   [OK] datasource_tool.py 使用了 _has_schema_dim")
        else:
            print("   [WARN] datasource_tool.py 可能未使用 _has_schema_dim")
    else:
        print("   [FAIL] 文件不存在")
        all_ok = False

    return all_ok


def main():
    print("=" * 60)
    print("schema_name 字段迁移验证脚本")
    print("=" * 60)
    print(f"\n数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    conn = connect()
    try:
        # 1. 验证 user_datasource_schemas 表
        ok1 = verify_user_datasource_schemas(conn)

        # 2. 验证 datasource_infos 表
        ok2 = verify_datasource_infos(conn)

        # 3. 验证回填结果
        ok3 = verify_backfill(conn)

        # 4. 验证 Python 代码
        ok4 = verify_helper_functions()

        # 总结
        print("\n" + "=" * 60)
        print("【验证结果汇总】")
        print("=" * 60)
        print(f"user_datasource_schemas 表结构: {'[OK]' if ok1 else '[FAIL]'}")
        print(f"datasource_infos 表结构: {'[OK]' if ok2 else '[FAIL]'}")
        print(f"schema_name 回填结果: {'[OK]' if ok3 else '[FAIL]'}")
        print(f"Python 代码验证: {'[OK]' if ok4 else '[FAIL]'}")

        all_ok = ok1 and ok2 and ok3 and ok4
        print("\n" + "=" * 60)
        if all_ok:
            print("【全部验证通过】schema_name 字段迁移成功！")
        else:
            print("【部分验证失败】请检查上述失败的项")
        print("=" * 60)

        return 0 if all_ok else 1

    finally:
        conn.close()


if __name__ == "__main__":
    exit(main())