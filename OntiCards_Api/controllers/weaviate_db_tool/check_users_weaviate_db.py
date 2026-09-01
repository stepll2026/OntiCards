"""
check_users_datasource_alignment_text_final.py

文本友好输出：
- 覆盖所有 users.weaviate_class_name 非空用户
- 每用户：列出数据源数量、每数据源四方对齐情况（table_num / schemas / datacards / weaviate）
- “有 class 但无 datasource”视为正常：未接入数据源用户
- 总结更直观：按用户/数据源维度汇总对齐情况
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams


# ========= 配置区：按你环境修改 =========
# DATABASE_URL = "postgresql+psycopg2://postgres:master_pz123@8.134.183.233:55432/dev-db-connector"
DATABASE_URL = "postgresql+psycopg2://postgres:master_pz123@8.134.183.233:55432/init_test"

WEAVIATE_URL = "http://8.134.183.233:8088"
WEAVIATE_GRPC_PORT = 50051

USERS_TABLE = "users"
DATASOURCE_TABLE = "datasource_infos"
SCHEMAS_TABLE = "user_datasource_schemas"
DATACARDS_TABLE = "datacards_datasource"

WEAVIATE_DOC_ID_CANDIDATES = ["doc_id", "docId", "docid", "docID", "schema_id", "schemaId"]
# ======================================


def normalize_class_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return str(name).strip().replace("-", "_")


@contextmanager
def weaviate_client():
    client = WeaviateClient(
        connection_params=ConnectionParams.from_url(url=WEAVIATE_URL, grpc_port=WEAVIATE_GRPC_PORT)
    )
    client.connect()
    try:
        yield client
    finally:
        client.close()


@dataclass
class UserRow:
    user_id: str
    username: str
    class_name: str


@dataclass
class DatasourceRow:
    datasource_id: str
    user_id: str
    connect_info: str
    connect_name: str
    db_type: str
    database_name: str
    catalog_type: Optional[str]
    table_num: int


def fetch_users_with_class(engine: Engine) -> List[UserRow]:
    sql = text(f"""
        SELECT id, username, weaviate_class_name
        FROM "{USERS_TABLE}"
        WHERE weaviate_class_name IS NOT NULL AND weaviate_class_name <> ''
        ORDER BY username
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()
    return [UserRow(str(uid), str(username), normalize_class_name(str(cls))) for uid, username, cls in rows]


def fetch_datasources(engine: Engine) -> List[DatasourceRow]:
    sql = text(f"""
        SELECT
          id AS datasource_id,
          user_id,
          connect_info,
          connect_name,
          db_type,
          database_name,
          catalog_type,
          table_num
        FROM "{DATASOURCE_TABLE}"
        ORDER BY user_id, connect_name, database_name
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()

    out: List[DatasourceRow] = []
    for r in rows:
        out.append(
            DatasourceRow(
                datasource_id=str(r[0]),
                user_id=str(r[1]),
                connect_info=str(r[2]),
                connect_name=str(r[3]),
                db_type=str(r[4]),
                database_name=str(r[5]),
                catalog_type=(str(r[6]) if r[6] is not None else None),
                table_num=int(r[7]),
            )
        )
    return out


def fetch_schema_ids_by_datasource(engine: Engine) -> Dict[str, Set[str]]:
    """
    datasource_infos 与 user_datasource_schemas 归属匹配：
      使用 connect_info_hash 进行关联（因为加密值每次不同）
      匹配条件：user_id + connect_info_hash + schema_name

    注意：需要先运行回填脚本填充 connect_info_hash 字段

    返回：{datasource_id: set(schema_uuid_str)}
    """
    # 优先使用 connect_info_hash 关联
    sql_hash = text(f"""
        SELECT
          di.id AS datasource_id,
          uds.id AS schema_id
        FROM "{DATASOURCE_TABLE}" di
        JOIN "{SCHEMAS_TABLE}" uds
          ON uds.user_id = di.user_id
         AND uds.connect_info_hash = di.connect_info_hash
         AND (uds.schema_name IS NOT DISTINCT FROM di.schema_name)
        WHERE di.connect_info_hash IS NOT NULL AND uds.connect_info_hash IS NOT NULL
    """)

    # 回退方案：如果 connect_info_hash 为 NULL，则使用原始逻辑（解密后比较）
    # 注意：这种方式性能较差，仅用于处理历史数据
    sql_legacy = text(f"""
        SELECT
          di.id AS datasource_id,
          uds.id AS schema_id
        FROM "{DATASOURCE_TABLE}" di
        JOIN "{SCHEMAS_TABLE}" uds
          ON uds.user_id = di.user_id
         AND uds.db_type = di.db_type
         AND uds.database_name = di.database_name
         AND uds.connect_name = di.connect_name
         AND (uds.catalog_type IS NOT DISTINCT FROM di.catalog_type)
        WHERE di.connect_info_hash IS NULL OR uds.connect_info_hash IS NULL
    """)

    out: Dict[str, Set[str]] = {}

    # 使用 connect_info_hash 的记录
    with engine.begin() as conn:
        for dsid, sid in conn.execute(sql_hash):
            out.setdefault(str(dsid), set()).add(str(sid))

    # 回退：没有哈希值的记录（历史数据）
    with engine.begin() as conn:
        for dsid, sid in conn.execute(sql_legacy):
            out.setdefault(str(dsid), set()).add(str(sid))

    return out


def fetch_datacards_counts_by_datasource(engine: Engine) -> Dict[str, int]:
    """
    datacards_datasource.doc_id == user_datasource_schemas.id::text
    直接按 datasource_id 聚合 count

    使用 connect_info_hash 进行关联
    """
    # 优先使用 connect_info_hash 的记录
    sql_hash = text(f"""
        SELECT
          di.id AS datasource_id,
          COUNT(dc.id) AS cnt
        FROM "{DATASOURCE_TABLE}" di
        JOIN "{SCHEMAS_TABLE}" uds
          ON uds.user_id = di.user_id
         AND uds.connect_info_hash = di.connect_info_hash
         AND (uds.schema_name IS NOT DISTINCT FROM di.schema_name)
        JOIN "{DATACARDS_TABLE}" dc
          ON dc.doc_id = uds.id::text
        WHERE di.connect_info_hash IS NOT NULL AND uds.connect_info_hash IS NOT NULL
        GROUP BY di.id
    """)

    # 回退方案：没有哈希值的记录
    sql_legacy = text(f"""
        SELECT
          di.id AS datasource_id,
          COUNT(dc.id) AS cnt
        FROM "{DATASOURCE_TABLE}" di
        JOIN "{SCHEMAS_TABLE}" uds
          ON uds.user_id = di.user_id
         AND uds.db_type = di.db_type
         AND uds.database_name = di.database_name
         AND uds.connect_name = di.connect_name
         AND (uds.catalog_type IS NOT DISTINCT FROM di.catalog_type)
        JOIN "{DATACARDS_TABLE}" dc
          ON dc.doc_id = uds.id::text
        WHERE di.connect_info_hash IS NULL OR uds.connect_info_hash IS NULL
        GROUP BY di.id
    """)

    out: Dict[str, int] = {}
    with engine.begin() as conn:
        for dsid, cnt in conn.execute(sql_hash):
            out[str(dsid)] = int(cnt or 0)

    # 回退：累加 legacy 结果（避免覆盖已有的）
    with engine.begin() as conn:
        for dsid, cnt in conn.execute(sql_legacy):
            dsid_str = str(dsid)
            if dsid_str not in out:
                out[dsid_str] = int(cnt or 0)

    return out


def detect_weaviate_doc_id_prop(client: WeaviateClient, class_name: str) -> Optional[str]:
    try:
        col = client.collections.get(class_name)
        cfg = col.config.get()
        props = []
        if hasattr(cfg, "properties") and cfg.properties:
            for p in cfg.properties:
                if hasattr(p, "name"):
                    props.append(p.name)
        for cand in WEAVIATE_DOC_ID_CANDIDATES:
            if cand in props:
                return cand
    except Exception:
        pass
    return None


def iter_weaviate_objects(collection):
    # iterator 优先
    if hasattr(collection, "iterator"):
        try:
            return collection.iterator()
        except Exception:
            pass

    # fallback：分页 fetch_objects
    def _gen():
        after = None
        while True:
            resp = collection.query.fetch_objects(limit=200, after=after)
            objs = getattr(resp, "objects", None)
            if not objs:
                break
            for o in objs:
                yield o
            after = getattr(resp, "next_after", None) or getattr(resp, "nextAfter", None)
            if not after:
                break

    return _gen()


def get_obj_properties(obj) -> Dict:
    if hasattr(obj, "properties") and isinstance(obj.properties, dict):
        return obj.properties
    d = getattr(obj, "__dict__", {})
    p = d.get("properties")
    return p if isinstance(p, dict) else {}


def build_weaviate_counts_for_user(
    client: WeaviateClient,
    class_name: str,
    user_ds_schema_ids: Dict[str, Set[str]],
) -> Tuple[Dict[str, int], str, Optional[str]]:
    """
    遍历用户 collection，把对象按 doc_id 归属到 datasource
    """
    if not client.collections.exists(class_name):
        return {}, "N/A", "MISSING_COLLECTION"

    col = client.collections.get(class_name)
    doc_prop = detect_weaviate_doc_id_prop(client, class_name) or "auto"

    schema_to_ds: Dict[str, str] = {}
    for dsid, sids in user_ds_schema_ids.items():
        for sid in sids:
            schema_to_ds[sid] = dsid

    counts: Dict[str, int] = {dsid: 0 for dsid in user_ds_schema_ids.keys()}

    try:
        for obj in iter_weaviate_objects(col):
            props = get_obj_properties(obj)

            doc_val = None
            if doc_prop != "auto" and doc_prop in props:
                doc_val = props.get(doc_prop)
            else:
                for cand in WEAVIATE_DOC_ID_CANDIDATES:
                    if cand in props:
                        doc_val = props.get(cand)
                        break

            if not doc_val:
                continue

            sid = str(doc_val)
            dsid = schema_to_ds.get(sid)
            if dsid:
                counts[dsid] += 1

        return counts, doc_prop, None
    except Exception as e:
        return {}, doc_prop, f"WEAVIATE_SCAN_ERROR: {e}"


def fmt_cat(cat: Optional[str]) -> str:
    return cat if cat is not None else "NULL"


def main():
    engine = create_engine(DATABASE_URL, future=True)

    users = fetch_users_with_class(engine)
    datasources = fetch_datasources(engine)

    ds_by_user: Dict[str, List[DatasourceRow]] = {}
    for ds in datasources:
        ds_by_user.setdefault(ds.user_id, []).append(ds)

    schema_ids_by_ds = fetch_schema_ids_by_datasource(engine)
    datacards_cnt_by_ds = fetch_datacards_counts_by_datasource(engine)

    users_no_datasource: List[UserRow] = []

    # ===== 统计汇总（更直观）=====
    total_users_with_class = len(users)

    users_with_datasource = 0
    total_ds_rows = 0

    ok_rows = 0
    mismatch_rows = 0
    weaviate_error_rows = 0  # 按“数据源行”计数的 weaviate error（更直观）
    weaviate_error_users = 0  # 按“用户”计数的 weaviate error

    with weaviate_client() as client:
        for u in users:
            user_ds_list = ds_by_user.get(u.user_id, [])

            print("\n" + "=" * 88)
            print(f"用户：{u.username} ({u.user_id})")
            print(f"Weaviate Class：{u.class_name}")
            print(f"数据源数量：{len(user_ds_list)}")

            # ✅ 这里视为正常：未接入数据源
            if not user_ds_list:
                print("状态：未接入数据源（正常）")
                users_no_datasource.append(u)
                continue

            users_with_datasource += 1
            total_ds_rows += len(user_ds_list)

            # 该用户每个 datasource 的 schema_id 集合
            user_ds_schema_ids = {ds.datasource_id: schema_ids_by_ds.get(ds.datasource_id, set()) for ds in user_ds_list}

            w_counts, doc_prop_used, w_err = build_weaviate_counts_for_user(client, u.class_name, user_ds_schema_ids)
            print(f"Weaviate 扫描：doc_id 字段={doc_prop_used}；状态={'OK' if not w_err else w_err}")

            if w_err:
                weaviate_error_users += 1

            for i, ds in enumerate(user_ds_list, start=1):
                schema_cnt = len(schema_ids_by_ds.get(ds.datasource_id, set()))
                datacards_cnt = int(datacards_cnt_by_ds.get(ds.datasource_id, 0))
                wcnt = None if w_err else int(w_counts.get(ds.datasource_id, 0))

                if w_err:
                    status = "WEAVIATE_ERROR"
                    weaviate_error_rows += 1
                else:
                    status = "OK" if (ds.table_num == schema_cnt == datacards_cnt == wcnt) else "MISMATCH"

                if status == "OK":
                    ok_rows += 1
                elif status == "MISMATCH":
                    mismatch_rows += 1

                print(f"\n  [{i}] 数据源：{ds.connect_name} | {ds.db_type} | {ds.database_name} | catalog_type={fmt_cat(ds.catalog_type)}")
                print(f"      datasource_id = {ds.datasource_id}")
                print(f"      table_num     = {ds.table_num}")
                print(f"      schemas_cnt   = {schema_cnt}")
                print(f"      datacards_cnt = {datacards_cnt}")
                print(f"      weaviate_cnt  = {'' if wcnt is None else wcnt}")
                print(f"      => {status}")

    # ===== 总结（按你的口径：无数据源用户算正常）=====
    print("\n" + "#" * 88)
    print("校验结果总结（更直观）")
    print("#" * 88)

    users_without_datasource = len(users_no_datasource)

    print(f"- 用户总数（有 Weaviate Class）：{total_users_with_class}")
    print(f"- 已接入数据源用户：{users_with_datasource}")
    print(f"- 未接入数据源用户（正常）：{users_without_datasource}")
    print(f"- 数据源总数：{total_ds_rows}")

    if total_ds_rows == 0:
        print("\nℹ️ 当前所有用户均未接入数据源（正常），无可校验的数据源对齐项。")
    else:
        if mismatch_rows == 0 and weaviate_error_rows == 0:
            print("\n✅ 已接入的数据源全部对齐：table_num = schemas_cnt = datacards_cnt = weaviate_cnt")
        else:
            print("\n❌ 已接入的数据源存在异常：")
            if mismatch_rows > 0:
                print(f"  - 未对齐数据源数（MISMATCH）：{mismatch_rows}")
            if weaviate_error_rows > 0:
                print(f"  - Weaviate 扫描异常影响的数据源数：{weaviate_error_rows}")
                print(f"  - Weaviate 扫描异常用户数：{weaviate_error_users}")

    # ✅ 按你要求保留清单输出（但它是“正常未接入”，不是异常）
    if users_no_datasource:
        print("\n未接入数据源的用户清单（正常）：")
        for u in users_no_datasource:
            print(f"- {u.username} ({u.user_id}) class={u.class_name}")


if __name__ == "__main__":
    main()