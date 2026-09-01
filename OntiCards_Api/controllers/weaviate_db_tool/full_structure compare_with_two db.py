import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Set
import sys

# =============================
# 1️⃣ 修改这里的数据库连接信息
# =============================

DB1 = {
    "host": "8.134.183.233",
    "port": 55432,
    "database": "init_test",
    "user": "postgres",
    "password": "master_pz123"
}

DB2 = {
    "host": "8.134.183.233",
    "port": 55432,
    "database": "prod-ontiCards",
    "user": "postgres",
    "password": "master_pz123"
}

SCHEMAS = ["public"]  # 支持多个 schema 对比，如 ["public","app"]

# ✅ 新增：是否忽略字段顺序差异（ordinal_position）
IGNORE_COLUMN_ORDER = True

# =============================
# 2️⃣ 工具函数
# =============================

def connect(conn_info):
    return psycopg2.connect(**conn_info)

def q(conn, sql: str, params: tuple = ()) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def norm_default(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()

def norm_bool(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip().upper()

def print_set_diff(title: str, only1: Set, only2: Set) -> bool:
    if only1 or only2:
        print(f"\n❌ {title} 不一致")
        if only1:
            print("  仅在 DB1:", *sorted(list(only1))[:200], sep="\n    - ")
            if len(only1) > 200:
                print(f"    ...（还有 {len(only1)-200} 条）")
        if only2:
            print("  仅在 DB2:", *sorted(list(only2))[:200], sep="\n    - ")
            if len(only2) > 200:
                print(f"    ...（还有 {len(only2)-200} 条）")
        return False
    else:
        print(f"✅ {title} 一致")
        return True


# =============================
# 3️⃣ 读取结构信息
# =============================

# column tuple（不包含 ordinal_position，顺序由查询 ORDER BY 决定）
ColumnDef = Tuple[
    str,  # column_name
    str,  # data_type
    str,  # udt_name
    str,  # is_nullable
    str,  # column_default
    Any,  # character_maximum_length
    Any,  # numeric_precision
    Any,  # numeric_scale
]

@dataclass
class TableStruct:
    columns_ordered: List[ColumnDef]   # 按 ordinal_position 排序的字段定义列表
    primary_key: Tuple[str, ...]       # PK 列名有序
    unique_constraints: Set[Tuple]     # (constraint_name, columns_tuple)
    foreign_keys: Set[Tuple]           # (fk_name, columns_tuple, ref_schema, ref_table, ref_columns_tuple, on_update, on_delete, match_type)
    indexes: Set[Tuple]                # (index_name, is_unique, is_primary, keys_tuple, predicate)

def get_tables(conn, schema: str) -> List[str]:
    rows = q(conn, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s AND table_type='BASE TABLE'
        ORDER BY table_name
    """, (schema,))
    return [r["table_name"] for r in rows]

def get_columns(conn, schema: str, table: str) -> List[ColumnDef]:
    rows = q(conn, """
        SELECT
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position
    """, (schema, table))

    out: List[ColumnDef] = []
    for r in rows:
        out.append((
            r["column_name"],
            r["data_type"],
            r["udt_name"],
            norm_bool(r["is_nullable"]),
            norm_default(r["column_default"]),
            r["character_maximum_length"],
            r["numeric_precision"],
            r["numeric_scale"],
        ))
    return out

def get_primary_key(conn, schema: str, table: str) -> Tuple[str, ...]:
    rows = q(conn, """
        SELECT kcu.column_name, kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type='PRIMARY KEY'
          AND tc.table_schema=%s AND tc.table_name=%s
        ORDER BY kcu.ordinal_position
    """, (schema, table))
    return tuple([r["column_name"] for r in rows])

def get_unique_constraints(conn, schema: str, table: str) -> Set[Tuple]:
    rows = q(conn, """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type='UNIQUE'
          AND tc.table_schema=%s AND tc.table_name=%s
        ORDER BY tc.constraint_name, kcu.ordinal_position
    """, (schema, table))

    m: Dict[str, List[Tuple[int, str]]] = {}
    for r in rows:
        m.setdefault(r["constraint_name"], []).append((int(r["ordinal_position"]), r["column_name"]))

    out: Set[Tuple] = set()
    for cname, lst in m.items():
        cols = tuple([c for _, c in sorted(lst, key=lambda x: x[0])])
        out.add((cname, cols))
    return out

def get_foreign_keys(conn, schema: str, table: str) -> Set[Tuple]:
    rows = q(conn, """
        SELECT
            tc.constraint_name AS fk_name,
            kcu.column_name AS fk_column,
            kcu.ordinal_position AS fk_pos,
            ccu.table_schema AS ref_schema,
            ccu.table_name AS ref_table,
            ccu.column_name AS ref_column,
            rc.update_rule AS on_update,
            rc.delete_rule AS on_delete,
            rc.match_option AS match_type
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
         AND rc.constraint_schema = tc.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = rc.unique_constraint_name
         AND ccu.constraint_schema = rc.unique_constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema=%s AND tc.table_name=%s
        ORDER BY tc.constraint_name, kcu.ordinal_position
    """, (schema, table))

    m: Dict[str, dict] = {}
    for r in rows:
        fk = r["fk_name"]
        if fk not in m:
            m[fk] = {
                "fk_cols": [],
                "ref_schema": r["ref_schema"],
                "ref_table": r["ref_table"],
                "ref_cols": [],
                "on_update": r["on_update"],
                "on_delete": r["on_delete"],
                "match_type": r["match_type"],
            }
        m[fk]["fk_cols"].append((int(r["fk_pos"]), r["fk_column"]))
        m[fk]["ref_cols"].append((int(r["fk_pos"]), r["ref_column"]))

    out: Set[Tuple] = set()
    for fk, info in m.items():
        fk_cols = tuple([c for _, c in sorted(info["fk_cols"], key=lambda x: x[0])])
        ref_cols = tuple([c for _, c in sorted(info["ref_cols"], key=lambda x: x[0])])
        out.add((
            fk,
            fk_cols,
            info["ref_schema"],
            info["ref_table"],
            ref_cols,
            info["on_update"],
            info["on_delete"],
            info["match_type"],
        ))
    return out

def get_indexes(conn, schema: str, table: str) -> Set[Tuple]:
    rows = q(conn, """
        SELECT
            idx.relname AS index_name,
            i.indisunique AS is_unique,
            i.indisprimary AS is_primary,
            pg_get_expr(i.indpred, i.indrelid) AS predicate,
            ARRAY(
                SELECT pg_get_indexdef(i.indexrelid, k + 1, true)
                FROM generate_subscripts(i.indkey, 1) AS k
                ORDER BY k
            ) AS keys
        FROM pg_index i
        JOIN pg_class tbl ON tbl.oid = i.indrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        JOIN pg_class idx ON idx.oid = i.indexrelid
        WHERE ns.nspname = %s AND tbl.relname = %s
        ORDER BY idx.relname
    """, (schema, table))

    out: Set[Tuple] = set()
    for r in rows:
        keys = tuple(r["keys"] or [])
        out.add((
            r["index_name"],
            bool(r["is_unique"]),
            bool(r["is_primary"]),
            keys,
            str(r["predicate"] or "").strip(),
        ))
    return out

def get_db_structure(conn_info) -> Dict[Tuple[str, str], TableStruct]:
    conn = connect(conn_info)
    try:
        result: Dict[Tuple[str, str], TableStruct] = {}
        for schema in SCHEMAS:
            tables = get_tables(conn, schema)
            for t in tables:
                result[(schema, t)] = TableStruct(
                    columns_ordered=get_columns(conn, schema, t),
                    primary_key=get_primary_key(conn, schema, t),
                    unique_constraints=get_unique_constraints(conn, schema, t),
                    foreign_keys=get_foreign_keys(conn, schema, t),
                    indexes=get_indexes(conn, schema, t),
                )
        return result
    finally:
        conn.close()


# =============================
# 4️⃣ 对比逻辑
# =============================

def strip_names_for_compare_unique(ucs: Set[Tuple]) -> Set[Tuple[str, ...]]:
    return set([uc[1] for uc in ucs])

def strip_names_for_compare_fk(fks: Set[Tuple]) -> Set[Tuple]:
    out = set()
    for fk in fks:
        _, fk_cols, ref_schema, ref_table, ref_cols, on_update, on_delete, match_type = fk
        out.add((fk_cols, ref_schema, ref_table, ref_cols, on_update, on_delete, match_type))
    return out

def strip_names_for_compare_index(idxs: Set[Tuple]) -> Set[Tuple]:
    out = set()
    for idx in idxs:
        _, is_unique, is_primary, keys, predicate = idx
        out.add((is_unique, is_primary, keys, predicate))
    return out

def coldef_by_name(cols: List[ColumnDef]) -> Dict[str, ColumnDef]:
    # 以 column_name 为 key，便于忽略顺序做字段定义比较
    return {c[0]: c for c in cols}

def compare_columns(schema: str, table: str, a_cols: List[ColumnDef], b_cols: List[ColumnDef]) -> Tuple[bool, bool]:
    """
    returns:
      defs_ok: 字段定义是否一致（忽略顺序）
      order_ok: 字段顺序是否一致（仅比较 column_name 顺序）
    """
    a_map = coldef_by_name(a_cols)
    b_map = coldef_by_name(b_cols)

    a_names = set(a_map.keys())
    b_names = set(b_map.keys())

    defs_ok = True
    if a_names != b_names:
        defs_ok = False
        print(f"\n❌ 字段集合不一致：{schema}.{table}")
        print("  仅在 DB1:", sorted(list(a_names - b_names))[:200])
        print("  仅在 DB2:", sorted(list(b_names - a_names))[:200])
        return defs_ok, False

    # 字段名一致，逐字段比定义（类型/nullable/default/精度等）
    diffs = []
    for name in sorted(a_names):
        if a_map[name] != b_map[name]:
            diffs.append((name, a_map[name], b_map[name]))

    if diffs:
        defs_ok = False
        print(f"\n❌ 字段定义不一致：{schema}.{table}")
        for name, d1, d2 in diffs[:200]:
            print(f"  - {name}")
            print(f"    DB1: {d1}")
            print(f"    DB2: {d2}")
        if len(diffs) > 200:
            print(f"    ...（还有 {len(diffs)-200} 个字段定义差异）")

    # 顺序对比（仅列名序列）
    a_order = [c[0] for c in a_cols]
    b_order = [c[0] for c in b_cols]
    order_ok = (a_order == b_order)

    if not order_ok:
        # 注意：这只是 warning（如果 IGNORE_COLUMN_ORDER=True）
        print(f"\n⚠️ 字段顺序不同（ordinal_position 不一致）：{schema}.{table}")
        print("  DB1 order:", a_order)
        print("  DB2 order:", b_order)

    return defs_ok, order_ok

def compare(db1: Dict[Tuple[str, str], TableStruct], db2: Dict[Tuple[str, str], TableStruct]) -> bool:
    ok = True
    only_warn = False

    t1 = set(db1.keys())
    t2 = set(db2.keys())

    print("========== 表集合对比 ==========")
    ok &= print_set_diff("表名（schema.table）", t1 - t2, t2 - t1)

    common = sorted(list(t1 & t2))
    print("\n========== 表级结构对比 ==========")

    for key in common:
        s, t = key
        a = db1[key]
        b = db2[key]

        # columns：字段定义忽略顺序对比；顺序差异仅 warning
        defs_ok, order_ok = compare_columns(s, t, a.columns_ordered, b.columns_ordered)
        if not defs_ok:
            ok = False
        elif not order_ok and IGNORE_COLUMN_ORDER:
            only_warn = True
        elif not order_ok and not IGNORE_COLUMN_ORDER:
            ok = False  # 如果你想把顺序也当作硬差异，可以关掉 IGNORE_COLUMN_ORDER

        # primary key：列顺序敏感
        if a.primary_key != b.primary_key:
            ok = False
            print(f"\n❌ 主键不一致：{s}.{t}")
            print("  DB1 PK:", a.primary_key)
            print("  DB2 PK:", b.primary_key)
        else:
            print(f"✅ {s}.{t} 主键一致")

        # unique：忽略约束名，只比列组合
        ua = strip_names_for_compare_unique(a.unique_constraints)
        ub = strip_names_for_compare_unique(b.unique_constraints)
        if ua != ub:
            ok = False
            print(f"\n❌ 唯一约束不一致：{s}.{t}")
            print("  仅在 DB1 (cols):", ua - ub)
            print("  仅在 DB2 (cols):", ub - ua)
        else:
            print(f"✅ {s}.{t} 唯一约束一致")

        # foreign keys：忽略 fk 名
        fa = strip_names_for_compare_fk(a.foreign_keys)
        fb = strip_names_for_compare_fk(b.foreign_keys)
        if fa != fb:
            ok = False
            print(f"\n❌ 外键不一致：{s}.{t}")
            print("  仅在 DB1:", fa - fb)
            print("  仅在 DB2:", fb - fa)
        else:
            print(f"✅ {s}.{t} 外键一致")

        # indexes：忽略 index 名
        ia = strip_names_for_compare_index(a.indexes)
        ib = strip_names_for_compare_index(b.indexes)
        if ia != ib:
            ok = False
            print(f"\n❌ 索引不一致：{s}.{t}")
            print("  仅在 DB1:", ia - ib)
            print("  仅在 DB2:", ib - ia)
        else:
            print(f"✅ {s}.{t} 索引一致")

    if ok and only_warn:
        print("\n⚠️ 仅发现字段顺序差异（ordinal_position），其余结构一致。")

    return ok


def main():
    print("读取 DB1 结构中...")
    db1 = get_db_structure(DB1)
    print(f"DB1 读取完成：{len(db1)} 张表\n")

    print("读取 DB2 结构中...")
    db2 = get_db_structure(DB2)
    print(f"DB2 读取完成：{len(db2)} 张表\n")

    print("开始对比...\n")
    ok = compare(db1, db2)

    print("\n================================")
    if ok:
        print("🎉 两个数据库结构【一致】（字段定义/PK/UK/FK/Index）")
        if IGNORE_COLUMN_ORDER:
            print("（已忽略字段顺序差异：ordinal_position）")
        sys.exit(0)
    else:
        print("⚠️ 两个数据库结构【存在差异】（字段定义/PK/UK/FK/Index 其中至少一项不一致）")
        sys.exit(2)


if __name__ == "__main__":
    main()