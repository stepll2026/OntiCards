"""
check_and_clean_datasource_alignment.py

全方位校验所有用户的数据源相关数据的一致性：
1. 检查 datasource_infos.table_num 与实际 schemas/datacards 数量是否一致
2. 检查 user_datasource_schemas 与 datacards_datasource 之间的对应关系
3. 检查 datacards_datasource.w_uuid 与 Weaviate 向量库之间的对应关系
4. 列出所有脏数据（孤立记录、不一致记录）

关联关系（按用户描述）：
- datasource_infos.connect_info + database_name = user_datasource_schemas.connect_info + database_name
- user_datasource_schemas.id::text = datacards_datasource.doc_id
- datacards_datasource.w_uuid = Weaviate 中的 id
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams


# ========= 配置区 =========
DATABASE_URL = "postgresql+psycopg2://postgres:master_ds123@172.16.1.7:55432/prod-ontiCards"

WEAVIATE_URL = "http://172.16.1.7:8080"
WEAVIATE_GRPC_PORT = 50051

USERS_TABLE = "users"
DATASOURCE_TABLE = "datasource_infos"
SCHEMAS_TABLE = "user_datasource_schemas"
DATACARDS_TABLE = "datacards_datasource"

WEAVIATE_DOC_ID_CANDIDATES = ["doc_id", "docId", "docid", "docID", "schema_id", "schemaId"]
# =============================


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


@dataclass
class DatasourceCheckResult:
    """单个数据源的校验结果"""
    datasource_id: str
    connect_name: str
    db_type: str
    database_name: str

    table_num: int = 0
    schemas_cnt: int = 0
    datacards_cnt: int = 0
    datacards_via_join: int = 0
    weaviate_cnt: int = 0

    schemas_without_datacards: int = 0
    datacards_without_schemas: int = 0
    datacards_without_weaviate: int = 0
    weaviate_without_datacards: int = 0

    orphan_datacards: List[dict] = field(default_factory=list)
    orphan_schemas: List[dict] = field(default_factory=list)
    orphan_weaviate: List[dict] = field(default_factory=list)

    @property
    def is_aligned(self) -> bool:
        return (
            self.table_num == self.schemas_cnt ==
            self.datacards_cnt == self.weaviate_cnt ==
            self.datacards_via_join == self.schemas_cnt
        )


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


def fetch_schemas_for_datasource(engine: Engine, ds: DatasourceRow) -> List[dict]:
    """
    获取指定数据源的所有 schema 记录
    关联条件：datasource_infos.connect_info + database_name = user_datasource_schemas.connect_info + database_name
    """
    sql = text(f"""
        SELECT uds.id::text, uds.table_name, uds.connect_info, uds.database_name
        FROM "{SCHEMAS_TABLE}" uds
        WHERE uds.connect_info = :connect_info
          AND uds.database_name = :database_name
        ORDER BY uds.table_name
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"connect_info": ds.connect_info, "database_name": ds.database_name}).fetchall()
    return [{"id": str(r[0]), "table_name": str(r[1]), "connect_info": str(r[2]), "database_name": str(r[3])} for r in rows]


def fetch_datacards_for_datasource(engine: Engine, ds: DatasourceRow) -> Tuple[List[dict], List[dict]]:
    """
    获取指定数据源的所有 datacard 记录
    返回：(所有datacard列表, 有对应schema的datacard列表)
    """
    sql = text(f"""
        SELECT
            dc.id,
            dc.doc_id,
            dc.w_uuid,
            dc.table_name,
            CASE WHEN uds.id IS NOT NULL THEN 1 ELSE 0 END as has_schema
        FROM "{DATACARDS_TABLE}" dc
        LEFT JOIN "{SCHEMAS_TABLE}" uds ON dc.doc_id = uds.id::text
        WHERE dc.datasource_id = :datasource_id
        ORDER BY dc.id
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"datasource_id": ds.datasource_id}).fetchall()

    all_datacards = []
    datacards_with_schema = []
    for r in rows:
        dc = {
            "id": str(r[0]),
            "doc_id": str(r[1]),
            "w_uuid": str(r[2]) if r[2] else None,
            "table_name": str(r[3]) if r[3] else None,
            "has_schema": bool(r[4])
        }
        all_datacards.append(dc)
        if dc["has_schema"]:
            datacards_with_schema.append(dc)

    return all_datacards, datacards_with_schema


def fetch_datacards_via_join(engine: Engine, ds: DatasourceRow) -> int:
    """
    通过 JOIN 统计 datacards 数量（原有逻辑）
    """
    sql = text(f"""
        SELECT COUNT(*)
        FROM "{DATACARDS_TABLE}" dc
        JOIN "{SCHEMAS_TABLE}" uds ON dc.doc_id = uds.id::text
        WHERE dc.datasource_id = :datasource_id
    """)
    with engine.begin() as conn:
        result = conn.execute(sql, {"datasource_id": ds.datasource_id}).fetchone()
    return int(result[0]) if result else 0


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
    if hasattr(collection, "iterator"):
        try:
            return collection.iterator()
        except Exception:
            pass

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


def fetch_weaviate_records_by_datasource(
    client: WeaviateClient,
    class_name: str,
    datasource_id: str,
) -> Tuple[Dict[str, str], int, str, Optional[str]]:
    """
    遍历用户 collection，获取属于指定 datasource_id 的所有对象的 doc_id 和 w_uuid
    通过 properties.datasource_id 过滤
    返回：(uuid_to_doc_id, total_count, doc_prop, error_msg)
    """
    if not client.collections.exists(class_name):
        return {}, 0, "N/A", "MISSING_COLLECTION"

    col = client.collections.get(class_name)
    doc_prop = detect_weaviate_doc_id_prop(client, class_name) or "auto"

    uuid_to_doc_id: Dict[str, str] = {}
    total_count = 0

    try:
        for obj in iter_weaviate_objects(col):
            props = get_obj_properties(obj)

            # 通过 datasource_id 过滤，只取属于当前数据源的记录
            record_ds_id = props.get("datasource_id", "")
            if not record_ds_id or str(record_ds_id).lower() != str(datasource_id).lower():
                continue

            obj_uuid = getattr(obj, "uuid", None) or props.get("id", "")

            doc_val = None
            if doc_prop != "auto" and doc_prop in props:
                doc_val = props.get(doc_prop)
            else:
                for cand in WEAVIATE_DOC_ID_CANDIDATES:
                    if cand in props:
                        doc_val = props.get(cand)
                        break

            if obj_uuid:
                uuid_to_doc_id[str(obj_uuid)] = str(doc_val) if doc_val else None
                total_count += 1

        return uuid_to_doc_id, total_count, doc_prop, None
    except Exception as e:
        return {}, 0, doc_prop, f"WEAVIATE_SCAN_ERROR: {e}"


def check_datasource_alignment(
    engine: Engine,
    client: WeaviateClient,
    user: UserRow,
    ds: DatasourceRow,
) -> DatasourceCheckResult:
    """检查单个数据源的四方对齐情况"""
    result = DatasourceCheckResult(
        datasource_id=ds.datasource_id,
        connect_name=ds.connect_name,
        db_type=ds.db_type,
        database_name=ds.database_name,
        table_num=ds.table_num,
    )

    # 1. 获取 schemas
    schemas = fetch_schemas_for_datasource(engine, ds)
    result.schemas_cnt = len(schemas)
    schema_ids = {s["id"] for s in schemas}
    schema_id_to_info = {s["id"]: s for s in schemas}

    # 2. 获取 datacards（直接通过 datasource_id 关联）
    all_datacards, datacards_with_schema = fetch_datacards_for_datasource(engine, ds)
    result.datacards_cnt = len(all_datacards)
    result.datacards_via_join = len(datacards_with_schema)

    doc_ids = {dc["doc_id"] for dc in all_datacards if dc["doc_id"]}
    w_uuids = {dc["w_uuid"] for dc in all_datacards if dc["w_uuid"]}
    datacard_by_w_uuid = {dc["w_uuid"]: dc for dc in all_datacards if dc["w_uuid"]}

    # 3. 分析不一致
    # 3.1 schemas 有但 datacards 没有（missing datacard）
    for sid in schema_ids:
        if sid not in doc_ids:
            result.schemas_without_datacards += 1
            result.orphan_schemas.append(schema_id_to_info[sid])

    # 3.2 datacards 有但 schemas 没有（orphan datacard）
    for dc in all_datacards:
        if not dc["has_schema"]:
            result.datacards_without_schemas += 1
            result.orphan_datacards.append(dc)

    # 4. 获取 Weaviate 数据（按 datasource_id 过滤）
    uuid_to_doc_id, weaviate_total, doc_prop, w_err = fetch_weaviate_records_by_datasource(
        client, user.class_name, ds.datasource_id
    )
    result.weaviate_cnt = weaviate_total

    if not w_err:
        # 4.1 datacards 有但 weaviate 没有
        for w_uuid in w_uuids:
            if w_uuid not in uuid_to_doc_id:
                result.datacards_without_weaviate += 1
                dc_info = datacard_by_w_uuid.get(w_uuid, {})
                result.orphan_weaviate.append({
                    "w_uuid": w_uuid,
                    "doc_id": dc_info.get("doc_id"),
                })

        # 4.2 weaviate 有但 datacards 没有（通过 w_uuid 匹配）
        for w_uuid, doc_id in uuid_to_doc_id.items():
            if w_uuid not in w_uuids:
                result.weaviate_without_datacards += 1

    return result


def print_result(result: DatasourceCheckResult):
    """打印单个数据源的校验结果"""
    status = "OK" if result.is_aligned else "MISMATCH"

    print(f"\n{'─' * 88}")
    print(f"数据源：{result.connect_name} | {result.db_type} | {result.database_name}")
    print(f"datasource_id = {result.datasource_id}")
    print(f"{'─' * 88}")

    print(f"  数量统计：")
    print(f"    table_num          = {result.table_num}  (datasource_infos 中记录)")
    print(f"    schemas_cnt        = {result.schemas_cnt}  (user_datasource_schemas 中记录)")
    print(f"    datacards_cnt      = {result.datacards_cnt}  (datacards_datasource 中记录)")
    print(f"    datacards_via_join = {result.datacards_via_join}  (JOIN schemas 后的 datacards)")
    print(f"    weaviate_cnt       = {result.weaviate_cnt}  (向量库中记录)")
    print(f"  状态：{status}")

    has_issues = False

    if result.schemas_without_datacards > 0:
        has_issues = True
        print(f"\n  ⚠️  schemas 有但 datacards 缺失：{result.schemas_without_datacards} 条")
        for s in result.orphan_schemas[:10]:
            print(f"      - schema_id={s['id']}, table_name={s['table_name']}")
        if len(result.orphan_schemas) > 10:
            print(f"      ... 还有 {len(result.orphan_schemas) - 10} 条")

    if result.datacards_without_schemas > 0:
        has_issues = True
        print(f"\n  ⚠️  datacards 有但 schemas 缺失（孤儿 datacard）：{result.datacards_without_schemas} 条")
        for dc in result.orphan_datacards[:10]:
            print(f"      - datacard_id={dc['id']}, doc_id={dc['doc_id']}, w_uuid={dc['w_uuid']}, table_name={dc['table_name']}")
        if len(result.orphan_datacards) > 10:
            print(f"      ... 还有 {len(result.orphan_datacards) - 10} 条")

    if result.datacards_without_weaviate > 0:
        has_issues = True
        print(f"\n  ⚠️  datacards 有但 Weaviate 缺失：{result.datacards_without_weaviate} 条")
        for w in result.orphan_weaviate[:10]:
            print(f"      - w_uuid={w['w_uuid']}, doc_id={w['doc_id']}")
        if len(result.orphan_weaviate) > 10:
            print(f"      ... 还有 {len(result.orphan_weaviate) - 10} 条")

    if result.weaviate_without_datacards > 0:
        has_issues = True
        print(f"\n  ⚠️  Weaviate 有但 datacards 缺失（孤儿向量）：{result.weaviate_without_datacards} 条")

    if not has_issues:
        print(f"\n  ✅ 所有数据一致")


def main():
    engine = create_engine(DATABASE_URL, future=True)

    users = fetch_users_with_class(engine)
    datasources = fetch_datasources(engine)

    if not users:
        print("未找到有 Weaviate Class 的用户")
        return

    if not datasources:
        print("未找到任何数据源")
        return

    ds_by_user: Dict[str, List[DatasourceRow]] = defaultdict(list)
    for ds in datasources:
        ds_by_user[ds.user_id].append(ds)

    print("=" * 88)
    print("数据源全方位一致性校验")
    print("=" * 88)
    print(f"数据库：{DATABASE_URL.split('@')[-1]}")
    print(f"Weaviate：{WEAVIATE_URL}")
    print(f"用户数（有 Weaviate Class）：{len(users)}")
    print(f"数据源总数：{len(datasources)}")

    all_results: List[DatasourceCheckResult] = []
    total_issues = {"schemas_without_datacards": 0, "datacards_without_schemas": 0,
                    "datacards_without_weaviate": 0, "weaviate_without_datacards": 0}

    with weaviate_client() as client:
        for u in users:
            user_ds_list = ds_by_user.get(u.user_id, [])

            print(f"\n\n{'#' * 88}")
            print(f"# 用户：{u.username} ({u.user_id})")
            print(f"# Weaviate Class：{u.class_name}")
            print(f"# 数据源数量：{len(user_ds_list)}")

            if not user_ds_list:
                print("# 状态：未接入数据源")
                continue

            for ds in user_ds_list:
                result = check_datasource_alignment(engine, client, u, ds)
                all_results.append(result)
                print_result(result)

                total_issues["schemas_without_datacards"] += result.schemas_without_datacards
                total_issues["datacards_without_schemas"] += result.datacards_without_schemas
                total_issues["datacards_without_weaviate"] += result.datacards_without_weaviate
                total_issues["weaviate_without_datacards"] += result.weaviate_without_datacards

    # ===== 总结 =====
    print(f"\n\n{'#' * 88}")
    print("# 校验结果总结")
    print(f"{'#' * 88}")

    mismatch_count = sum(1 for r in all_results if not r.is_aligned)
    ok_count = sum(1 for r in all_results if r.is_aligned)

    print(f"\n总体统计：")
    print(f"  - 数据源总数：{len(all_results)}")
    print(f"  - 对齐（OK）：{ok_count}")
    print(f"  - 不对齐（MISMATCH）：{mismatch_count}")

    print(f"\n脏数据汇总：")
    print(f"  - schemas 有但 datacards 缺失：{total_issues['schemas_without_datacards']} 条")
    print(f"  - datacards 有但 schemas 缺失（孤儿datacard）：{total_issues['datacards_without_schemas']} 条")
    print(f"  - datacards 有但 Weaviate 缺失：{total_issues['datacards_without_weaviate']} 条")
    print(f"  - Weaviate 有但 datacards 缺失（孤儿向量）：{total_issues['weaviate_without_datacards']} 条")

    total_dirty = sum(total_issues.values())
    if total_dirty > 0:
        print(f"\n  ❌ 发现 {total_dirty} 条脏数据，需要清理！")
    else:
        print(f"\n  ✅ 所有数据完全一致，无脏数据")

    problem_ds = [r for r in all_results if not r.is_aligned]
    if problem_ds:
        print(f"\n有问题的数据源清单：")
        for r in problem_ds:
            issues = []
            if r.schemas_without_datacards > 0:
                issues.append(f"schemas缺失datacards:{r.schemas_without_datacards}")
            if r.datacards_without_schemas > 0:
                issues.append(f"datacards孤儿:{r.datacards_without_schemas}")
            if r.datacards_without_weaviate > 0:
                issues.append(f"datacards缺失向量:{r.datacards_without_weaviate}")
            if r.weaviate_without_datacards > 0:
                issues.append(f"向量孤儿:{r.weaviate_without_datacards}")
            print(f"  - {r.connect_name} ({r.db_type}/{r.database_name}): {', '.join(issues)}")


if __name__ == "__main__":
    main()
