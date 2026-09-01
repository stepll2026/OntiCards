"""
 @File: sql_join_utils.py
 @Description: 关系抽取/簇构建/融合小工具
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-27 14:56
"""

from collections import defaultdict
from typing import Dict, List, Tuple, Any, Set
import json

from core.connect_info_encryptor import decrypt_connect_info

# -------- 数据卡解析 --------

def card_to_table_obj(schema_row, card_obj: dict, connect_info: str, ds_schema_name: str = None) -> dict:
    """
    将 ORM 行 + 数据卡对象 合并为簇内联查所需结构（优先读取卡片 SQLMeta）。

    参数:
        schema_row: UserDatasourceSchema ORM 对象
        card_obj: 数据卡 JSON 对象
        connect_info: 数据源连接字符串
        ds_schema_name: DatasourceInfo 中存储的 schema_name（优先级最高），
                        可覆盖 schema_row 中的 schema 信息。
    """
    sqlmeta = (card_obj or {}).get("SQLMeta", {}) or {}
    # 标准化 foreign_keys：统一为 [{column, ref_table, ref_column}]
    fks_raw = sqlmeta.get("foreign_keys") or []
    fks = []
    for fk in fks_raw:
        # 兼容两种结构键名：
        # 1) {"column":"", "ref_table":"", "ref_column":""}
        # 2) {"columns":[...], "referenced_table":"", "referenced_columns":[...]}
        if fk.get("column") and fk.get("ref_table") and fk.get("ref_column"):
            fks.append({
                "column": fk["column"],
                "ref_table": fk["ref_table"],
                "ref_column": fk["ref_column"],
            })
        else:
            cols = fk.get("columns") or []
            ref_tbl = fk.get("referenced_table") or fk.get("ref_table")
            ref_cols = fk.get("referenced_columns") or []
            if cols and ref_tbl and ref_cols:
                fks.append({
                    "column": cols[0],
                    "ref_table": ref_tbl,
                    "ref_column": ref_cols[0],
                })

    cols = []
    for c in (sqlmeta.get("columns") or []):
        if not c.get("name"):
            continue
        cols.append({
            "name": c["name"],
            "type": c.get("type", "unknown"),  # 保留字段类型信息
            "is_primary": bool(c.get("is_primary")),
            "is_foreign": bool(c.get("is_foreign")),
            "comment": c.get("comment", ""),  # 保留字段注释（包含枚举值等重要信息）
        })

    # 处理不同数据库类型的schema前缀
    table_name_raw = sqlmeta.get("table") or schema_row.table_name
    database_name = schema_row.database_name
    # 优先使用 DatasourceInfo 中传入的 schema_name，其次回退到 schema_row 的 schema_name
    schema_name = ds_schema_name or getattr(schema_row, 'schema_name', None)
    db_type = (schema_row.db_type or "").lower()

    # 检查表名是否包含点号
    if "." in table_name_raw:
        # 表名包含前缀，需要判断是否是正确格式
        parts = table_name_raw.split(".")

        if db_type in ("postgresql", "kingbase") and len(parts) == 2:
            # PostgreSQL/KingBase: 检查第一部分是否是database_name而不是schema_name
            # 如果第一部分等于database_name，说明格式错误，需要替换为schema
            if parts[0] == database_name:
                # 错误格式：database.table，需要改为 schema.table
                schema_to_use = schema_name or "public"
                full_table_name = f"{schema_to_use}.{parts[1]}"
                print(f"[card_to_table_obj] {db_type}表名格式错误(database.table)，已修正: {table_name_raw} -> {full_table_name}")
            else:
                # 假设已经是正确的 schema.table 格式
                full_table_name = table_name_raw
                print(f"[card_to_table_obj] {db_type}表名已包含schema前缀: {full_table_name}")

        elif db_type in ("mysql", "mariadb", "oceanbase") and len(parts) == 2:
            # MySQL: database.table格式，去掉database前缀，只保留table
            # OceanBase MySQL 模式与 MySQL 行为一致，复用同一处理方式
            full_table_name = parts[1]
            print(f"[card_to_table_obj] MySQL表名包含database前缀，已移除: {table_name_raw} -> {full_table_name}")

        else:
            # 其他情况：保持原样（可能是trino的catalog.schema.table等）
            full_table_name = table_name_raw
            print(f"[card_to_table_obj] 表名已包含前缀({db_type}): {full_table_name}")
    else:
        # 表名不包含点号，根据数据库类型决定是否添加schema前缀
        if db_type in ("postgresql", "kingbase"):
            # PostgreSQL/KingBase: 使用 schema.table 格式
            # 优先使用 schema_name，如果没有则使用默认值 public
            schema_to_use = schema_name or "public"
            full_table_name = f"{schema_to_use}.{table_name_raw}"
            print(f"[card_to_table_obj] {db_type}表添加schema前缀: {table_name_raw} -> {full_table_name}")

        elif db_type == "mssql":
            # SQL Server: 使用 schema.table 格式
            # 优先使用 schema_name，如果没有则使用默认值 dbo
            schema_to_use = schema_name or "dbo"
            full_table_name = f"{schema_to_use}.{table_name_raw}"
            print(f"[card_to_table_obj] MSSQL表添加schema前缀: {table_name_raw} -> {full_table_name}")

        elif db_type == "oracle" or db_type == "dm":
            # Oracle / 达梦 DM: 使用 schema.table 格式
            # schema通常是用户名（大写），优先使用 schema_name
            if schema_name:
                full_table_name = f"{schema_name}.{table_name_raw}"
                label = "达梦 DM" if db_type == "dm" else "Oracle"
                print(f"[card_to_table_obj] {label}表添加schema前缀: {table_name_raw} -> {full_table_name}")
            else:
                # 如果没有schema_name，直接使用表名
                full_table_name = table_name_raw
                label = "达梦 DM" if db_type == "dm" else "Oracle"
                print(f"[card_to_table_obj] {label}表无schema，使用原始表名: {table_name_raw}")

        elif db_type in ("mysql", "mariadb", "oceanbase"):
            # MySQL/MariaDB/OceanBase: 通常只需要表名，因为连接时已经指定了database
            # database_name和schema_name在MySQL中是等价的，通常不需要前缀
            full_table_name = table_name_raw
            print(f"[card_to_table_obj] MySQL表使用原始表名: {table_name_raw} (database={database_name or schema_name})")

        elif db_type == "trino":
            # Trino: catalog.schema.table 格式在专门的Trino处理逻辑中处理
            # 这里只使用原始表名
            full_table_name = table_name_raw
            print(f"[card_to_table_obj] Trino表使用原始表名: {table_name_raw} (将在Trino专用逻辑中处理)")

        else:
            # 其他数据库类型：默认只使用表名
            full_table_name = table_name_raw
            print(f"[card_to_table_obj] 其他数据库类型({db_type})使用原始表名: {table_name_raw}")

    return {
        "db_type": schema_row.db_type,
        "database_name": database_name,
        "schema_name": schema_name,
        "table_name": full_table_name,  # 对于PostgreSQL可能包含schema前缀
        "table_name_raw": table_name_raw,  # 保留原始表名
        "columns": cols,                 # 用于白名单 & 实体键推断
        "foreign_keys": fks,             # 用于 JOIN 关系抽取
        "schema": card_obj,              # 原始卡片（保留以便其他信息取用）
        "connect_name": (card_obj.get("DocInfo") or {}).get("connect_name"),
        "connect_info": connect_info,
        "schema_row_id": str(schema_row.id),
        "doc_id": (card_obj.get("DocInfo") or {}).get("doc_id"),
    }

# 优先使用外键，否则则推断
def guess_relations(tables: List[dict]) -> List[Tuple[str, str, str, str]]:
    """
    先用卡片中的 foreign_keys（inventory_stock.product_id -> product_catalog.product_id）
    无则回落到 *_id / id 的同名匹配启发式。
    返回: [(left_table, left_col, right_table, right_col), ...]
    """
    rels = []

    # 1) 用外键
    name_to_table = {t["table_name"]: t for t in tables}
    for t in tables:
        for fk in (t.get("foreign_keys") or []):
            lt = t["table_name"]
            lc = fk.get("column")
            rt = fk.get("ref_table")
            rc = fk.get("ref_column")
            if lt and lc and rt and rc:
                # 仅当目标表在本簇内才加入
                if rt in name_to_table:
                    rels.append((lt, lc, rt, rc))

    if rels:
        return rels

    # 2) 回落：*_id / user_id / product_id / id 启发式
    from collections import defaultdict
    index = defaultdict(list)  # col_lower -> [(table, col)]
    for t in tables:
        for c in (t.get("columns") or []):
            col = (c.get("name") or "").strip()
            if not col:
                continue
            cl = col.lower()
            if cl.endswith("_id") or cl in ("id", "user_id", "product_id"):
                index[cl].append((t["table_name"], col))
    for col_l, hits in index.items():
        if len(hits) >= 2:
            for i in range(len(hits)):
                for j in range(i+1, len(hits)):
                    lt, lc = hits[i]
                    rt, rc = hits[j]
                    if lt != rt:
                        rels.append((lt, lc, rt, rc))

    # 如果两个表各自只有一个 *_id 且同名，把它作为连接键候选
    def _only_one_id(cols: list[str]) -> str | None:
        cands = [c for c in cols if c.lower().endswith("_id")]
        return cands[0] if len(cands) == 1 else None

    for a in tables:
        for b in tables:
            if a is b:
                continue
            ida = _only_one_id([c["name"] for c in (a.get("columns") or [])])
            idb = _only_one_id([c["name"] for c in (b.get("columns") or [])])
            if ida and idb and ida.lower() == idb.lower():
                rels.append((a["table_name"], ida, b["table_name"], idb))

    return rels

# 基于卡片内容推断实体主键
def infer_entity_key_from_cards(table_objs: list[dict]) -> str:
    """
    根据 SQLMeta.pk / columns[].is_primary / is_foreign 统计，自动选全局实体键。
    在原有权重基础上额外考虑“出现在多少张表中”，避免因为某张表的高权重字段导致所有簇
    都使用一个冷门键（如 product_id），从而在其他表上无法命中实体。
    规则：
      1. 同一列在不同表中出现的次数优先级最高；
      2. 在出现次数相同的情况下，再比较权重；
      3. 若仍相同，则回落到常见偏好顺序（product_id / user_id / id），最后再比较名称。
    """
    from collections import Counter, defaultdict

    cnt = Counter()
    presence: dict[str, set[str]] = defaultdict(set)  # 列名 -> 出现过的表集合

    def record(col_name: str, score: int, table_name: str | None):
        name = (col_name or "").strip().lower()
        if not name:
            return
        cnt[name] += score
        if table_name:
            presence[name].add(table_name.lower())

    for t in table_objs:
        table_name = (t.get("table_name") or "").strip()
        card = t.get("schema") or {}
        sqlmeta = card.get("SQLMeta", {}) if card else {}
        # 1) 显式 pk
        pk = (sqlmeta.get("pk") or "").strip()
        if pk:
            record(pk, 5, table_name)
        # 2) columns 标注
        for c in (sqlmeta.get("columns") or []):
            name = c.get("name")
            if c.get("is_primary"):
                record(name, 3, table_name)
            elif c.get("is_foreign"):
                record(name, 1, table_name)
            elif name and name.lower().endswith("_id"):
                record(name, 1, table_name)

        # 3) 兼容 t["columns"] 上的 is_primary/is_foreign
        for c in (t.get("columns") or []):
            name = c.get("name")
            if c.get("is_primary"):
                record(name, 2, table_name)
            elif c.get("is_foreign"):
                record(name, 1, table_name)
            elif name and name.lower().endswith("_id"):
                record(name, 1, table_name)

    if not cnt:
        return "id"

    preference_rank = {"product_id": 3, "user_id": 2, "id": 1}

    def sort_key(item: tuple[str, int]):
        name, score = item
        presence_cnt = len(presence.get(name, set()))
        pref = preference_rank.get(name, 0)
        return (presence_cnt, score, pref, -len(name))  # 名称越短优先，便于复用 id

    best_name, _ = max(cnt.items(), key=sort_key)
    return best_name


# -------- 连接信息 --------

def map_connect_name_to_connect_info(
    connect_name: str,
    datasource_info_model,
    user_id: str = None
) -> str | None:
    """
    通过 connect_name 在 datasource_info 中找到 connect_info。

    Args:
        connect_name: 数据源连接名称
        datasource_info_model: DatasourceInfo 模型类
        user_id: 用户ID（可选，用于多用户隔离。如果不传则全局匹配）

    Returns:
        connect_info 字符串，或 None（未找到）
    """
    if not connect_name:
        return None

    query = datasource_info_model.query.filter_by(connect_name=connect_name)

    # 增加用户隔离，防止多用户环境下匹配到其他用户的同名数据源
    if user_id:
        query = query.filter_by(user_id=user_id)

    row = query.first()
    # 注意：数据库中存储的是加密后的 connect_info，需要解密后再返回
    return decrypt_connect_info(row.connect_info) if row else None

# -------- 分簇（db_type + connect_info） --------

def build_clusters(table_objs: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    clusters = defaultdict(list)
    for t in table_objs:
        key = (t["db_type"], t["connect_info"])
        clusters[key].append(t)
    return clusters

# -------- 表别名与白名单渲染（给提示词看） --------

def alias_tables(tables: List[dict]) -> Dict[str, str]:
    return { t["table_name"]: f"t{i+1}" for i, t in enumerate(tables) }

def render_whitelist_for_prompt(db_type: str, t: dict, alias: str) -> str:
    """
    渲染表字段白名单，包含字段类型信息和注释，帮助 LLM 选择正确的操作符和枚举值
    """
    columns = [c for c in (t.get("columns") or []) if c.get("name")]
    if not columns:
        return "(无)"
    
    # 根据数据库类型选择引用符
    # 人大金仓（KingBase）基于 PostgreSQL，复用 PostgreSQL 的引用符
    # OceanBase MySQL 模式与 MySQL 行为一致，使用反引号
    db_type_lower = (db_type or "").lower()
    if db_type_lower in ("mysql", "oceanbase"):
        quote = "`"
    elif db_type_lower == "mssql":
        quote = "["  # SQL Server方括号，但要成对使用
    elif db_type_lower in ("postgresql", "oracle", "trino", "kingbase"):
        quote = '"'
    else:
        quote = '"'  # 默认双引号
    
    # 格式：alias.column_name [类型] (注释)
    col_strs = []
    for c in columns:
        col_name = c["name"]
        col_type = c.get("type", "unknown")
        col_comment = c.get("comment", "")
        
        # 构建字段描述
        if db_type_lower == "mssql":
            col_desc = f'{alias}.[{col_name}] [{col_type}]'
        else:
            col_desc = f'{alias}.{quote}{col_name}{quote} [{col_type}]'
        
        # 如果有注释，添加到描述中，特别关注包含枚举值的注释
        if col_comment and col_comment.strip():
            col_desc += f' ({col_comment.strip()})'
        
        col_strs.append(col_desc)
    
    return ", ".join(col_strs)

def make_tables_block(db_type: str, tables: List[dict]) -> str:
    """
    构建传递给 LLM 的表白名单块，包含表名、别名、字段信息
    增强：包含表的中文标题（如果有），帮助 LLM 理解表的业务用途
    """
    aliases = alias_tables(tables)
    lines = []
    for t in tables:
        wl = render_whitelist_for_prompt(db_type, t, aliases[t["table_name"]])

        # 尝试获取表的中文标题/描述
        table_title = ""
        schema = t.get("schema") or {}
        doc_info = schema.get("DocInfo") or {}
        abstract = schema.get("Abstract") or ""

        # 优先使用 Abstract（LLM 生成的中文描述）
        if abstract and abstract.strip():
            table_title = f"（表用途说明：{abstract.strip()}）"
        # 其次使用 title
        elif doc_info.get("title"):
            title = doc_info.get("title", "")
            if title and title != f"数据表: {t['table_name']}":
                table_title = f"（{title}）"

        lines.append(f"- 表 {t['table_name']} AS {aliases[t['table_name']]} {table_title}: {wl}")
    return "\n".join(lines)

def make_rels_block(tables: List[dict]) -> str:
    aliases = alias_tables(tables)
    rels = guess_relations(tables)
    if not rels:
        return "（未推断到明确关系，可使用子查询/半连接策略）"
    return "\n".join([f"{aliases[lt]}.{lc} = {aliases[rt]}.{rc}" for (lt, lc, rt, rc) in rels])


# -------- 关系卡片辅助函数 --------

def fetch_relationship_cards(datasource_id: str, table_names: List[str], user_id: str) -> dict:
    """
    从数据库批量获取关系卡片

    Args:
        datasource_id: 数据源ID
        table_names: 表名列表
        user_id: 用户ID

    Returns:
        {
            "cards": {table_name: card_data, ...},
            "join_suggestions": [...],
            "missing_tables": [...]
        }
    """
    if not datasource_id or not table_names:
        return {"cards": {}, "join_suggestions": [], "missing_tables": table_names}

    try:
        from models.global_inventory import TableRelationshipCard
        from extensions.ext_database import db
        from uuid import UUID

        # 确保 datasource_id 是有效的 UUID 格式
        try:
            ds_uuid = UUID(str(datasource_id))
        except ValueError:
            return {"cards": {}, "join_suggestions": [], "missing_tables": table_names}

        # 批量查询关系卡片
        cards = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.datasource_id == ds_uuid,
            TableRelationshipCard.table_name.in_(table_names)
        ).all()

        cards_dict = {}
        found_tables = set()
        all_join_suggestions = []

        for card in cards:
            table_name = card.table_name
            found_tables.add(table_name)
            card_data = card.card_data or {}

            # 处理 card_data 可能是 JSON 字符串的情况
            if isinstance(card_data, str):
                try:
                    card_data = json.loads(card_data)
                except json.JSONDecodeError:
                    card_data = {}

            # 提取关系信息
            relationships = card_data.get("Relationships", [])

            # 只保留与查询表相关的关系
            relevant_relationships = []
            for rel in relationships:
                related_table = rel.get("related_table", "")
                if related_table in table_names:
                    relevant_relationships.append(rel)

                    # 提取JOIN建议
                    join_suggestion = rel.get("join_suggestion", {})
                    for field in rel.get("join_fields", []):
                        all_join_suggestions.append({
                            "from_table": table_name,
                            "to_table": related_table,
                            "from_column": field.get("local_field"),
                            "to_column": field.get("remote_field"),
                            "join_type": join_suggestion.get("join_type", "LEFT JOIN"),
                            "confidence": field.get("confidence", 0),
                            "relationship_type": rel.get("relationship_type", ""),
                            "business_relation": rel.get("business_relation", {})
                        })

            cards_dict[table_name] = {
                "table_name": table_name,
                "relationships": relevant_relationships,
                "all_relationships": relationships,
                "join_summary": card_data.get("JoinSummary", ""),
                "fusion_hints": card_data.get("FusionHints", {})
            }

        # 去重JOIN建议
        unique_joins = {}
        for sug in all_join_suggestions:
            key = tuple(sorted([sug["from_table"], sug["to_table"]]))
            if key not in unique_joins or sug["confidence"] > unique_joins[key]["confidence"]:
                unique_joins[key] = sug

        missing_tables = list(set(table_names) - found_tables)

        return {
            "cards": cards_dict,
            "join_suggestions": list(unique_joins.values()),
            "missing_tables": missing_tables
        }

    except Exception as e:
        print(f"[关系卡片] 获取失败: {e}")
        return {"cards": {}, "join_suggestions": [], "missing_tables": table_names}


def filter_relationship_data_by_tables(relationship_data: dict, table_names_set: set) -> dict:
    """
    按白名单表集合过滤关系卡片数据，过滤掉所有涉及非白名单表的关系。

    用途：
    - 融合阶段：LLM 融合提示词只能看到与实际融合任务相关的 JOIN/卡片，
      避免无关表的 JOIN 干扰 LLM 的语义对齐判断
    - 多源场景：聚合多个数据源的关系卡片后，按"实际参与融合的表集合"过滤

    Args:
        relationship_data: {
            "cards": {table_name: card_data, ...},
            "join_suggestions": [...],
            "missing_tables": [...]
        }
        table_names_set: 白名单表名集合（字符串集合）

    Returns:
        过滤后的关系数据，结构与原数据一致
    """
    if not relationship_data or not table_names_set:
        return {"cards": {}, "join_suggestions": [], "missing_tables": []}

    # 1. 过滤 cards：只保留白名单表对应的卡片
    filtered_cards = {}
    cards = relationship_data.get("cards", {}) or {}
    for tname, card_info in cards.items():
        if tname in table_names_set:
            # 进一步过滤卡片内的 relationships，确保只保留涉及白名单表的关系
            if card_info and isinstance(card_info, dict):
                all_rels = card_info.get("all_relationships") or []
                rels = card_info.get("relationships") or []
                filtered_rels = [
                    r for r in rels
                    if r.get("related_table", "") in table_names_set
                ]
                filtered_all_rels = [
                    r for r in all_rels
                    if r.get("related_table", "") in table_names_set
                ]
                new_card = dict(card_info)
                new_card["relationships"] = filtered_rels
                new_card["all_relationships"] = filtered_all_rels
                filtered_cards[tname] = new_card
            else:
                filtered_cards[tname] = card_info

    # 2. 过滤 join_suggestions：JOIN 两端都必须都在白名单内
    join_suggestions = relationship_data.get("join_suggestions", []) or []
    filtered_joins = []
    for sug in join_suggestions:
        from_t = sug.get("from_table", "")
        to_t = sug.get("to_table", "")
        if from_t in table_names_set and to_t in table_names_set:
            filtered_joins.append(sug)

    # 3. missing_tables 也过滤：只保留在白名单中但确实没找到卡片的表
    missing_tables = relationship_data.get("missing_tables", []) or []
    filtered_missing = [t for t in missing_tables if t in table_names_set]

    return {
        "cards": filtered_cards,
        "join_suggestions": filtered_joins,
        "missing_tables": filtered_missing
    }


def merge_relationship_data(*relationship_data_list: dict) -> dict:
    """
    合并多个关系卡片数据（用于跨数据源场景）

    合并策略：
    - cards：以 table_name 为 key 合并，后写覆盖前写（与原行为一致）
      ⚠️ 注意：跨源同名表可能 key 冲突，但本仓库里 TableRelationshipCard 是
      按 (datasource_id, schema_hash, table_name) 唯一约束存储的，
      所以"同名表来自不同数据源"的情况一般不会出现，这里保持原行为即可。
    - join_suggestions：按 (from_table, to_table, from_column, to_column) 去重，
      保留 confidence 最高的那条
    - missing_tables：取并集

    Args:
        *relationship_data_list: 多个 fetch_relationship_cards 返回的 dict

    Returns:
        合并后的关系数据
    """
    merged = {"cards": {}, "join_suggestions": [], "missing_tables": []}
    if not relationship_data_list:
        return merged

    join_key_to_sug = {}  # (from_t, to_t, from_c, to_c) -> suggestion
    for rd in relationship_data_list:
        if not rd:
            continue
        merged["cards"].update(rd.get("cards", {}) or {})
        for sug in (rd.get("join_suggestions", []) or []):
            key = (
                sug.get("from_table", ""),
                sug.get("to_table", ""),
                sug.get("from_column", ""),
                sug.get("to_column", "")
            )
            existing = join_key_to_sug.get(key)
            if existing is None or sug.get("confidence", 0) > existing.get("confidence", 0):
                join_key_to_sug[key] = sug
        for mt in (rd.get("missing_tables", []) or []):
            if mt not in merged["missing_tables"]:
                merged["missing_tables"].append(mt)

    merged["join_suggestions"] = list(join_key_to_sug.values())
    return merged


def format_relationship_cards_for_prompt(relationship_data: dict, tables: List[dict]) -> str:
    """
    将关系卡片信息格式化为提示词可用的文本

    Args:
        relationship_data: fetch_relationship_cards 返回的数据
        tables: 当前查询涉及的表对象列表

    Returns:
        格式化后的关系信息文本
    """
    cards = relationship_data.get("cards", {})
    join_suggestions = relationship_data.get("join_suggestions", [])

    if not cards and not join_suggestions:
        return "（未发现相关表之间的关系信息）"

    lines = []
    aliases = alias_tables(tables)
    table_name_to_alias = {t["table_name"]: aliases[t["table_name"]] for t in tables}

    # 1. 输出每张表的关系摘要
    lines.append("【表关系摘要】")
    for table_name, card_info in cards.items():
        alias = table_name_to_alias.get(table_name, table_name)
        join_summary = card_info.get("join_summary", "")
        if join_summary:
            lines.append(f"- {table_name} ({alias}): {join_summary}")

    # 2. 输出JOIN建议（按置信度排序）
    if join_suggestions:
        lines.append("")
        lines.append("【推荐的JOIN条件】（按置信度排序）")
        sorted_suggestions = sorted(join_suggestions, key=lambda x: x.get("confidence", 0), reverse=True)

        # ========== 防止泄露非白名单表：只保留召回表之间的关系 ==========
        table_names_in_whitelist = set(table_name_to_alias.keys())

        for sug in sorted_suggestions:
            from_table = sug.get("from_table", "")
            to_table = sug.get("to_table", "")

            # 关键：检查两张表是否都在召回列表中（白名单中）
            if from_table not in table_names_in_whitelist:
                print(f"[关系卡片过滤] 跳过非白名单表的JOIN建议: {from_table} (不在召回列表)")
                continue
            if to_table not in table_names_in_whitelist:
                print(f"[关系卡片过滤] 跳过非白名单表的JOIN建议: {from_table} -> {to_table} ({to_table}不在召回列表)")
                continue

            # 只有两张表都在召回列表中，才输出JOIN建议
            from_col = sug.get("from_column", "")
            to_col = sug.get("to_column", "")
            join_type = sug.get("join_type", "LEFT JOIN")
            confidence = sug.get("confidence", 0)
            rel_type = sug.get("relationship_type", "")

            from_alias = table_name_to_alias.get(from_table, from_table)
            to_alias = table_name_to_alias.get(to_table, to_table)

            # 业务关系描述
            business_rel = sug.get("business_relation", {})
            business_desc = business_rel.get("relation_description", "")

            line = f"- {from_alias}.{from_col} = {to_alias}.{to_col}"
            line += f" (置信度: {confidence:.2f}, {join_type}"
            if rel_type:
                line += f", {rel_type}"
            line += ")"
            if business_desc:
                line += f"\n  业务关系: {business_desc}"

            lines.append(line)

    # 3. 输出融合建议（如果有）
    fusion_hints_found = False
    for table_name, card_info in cards.items():
        fusion_hints = card_info.get("fusion_hints", {})
        if fusion_hints:
            if not fusion_hints_found:
                lines.append("")
                lines.append("【数据融合建议】")
                fusion_hints_found = True

            as_master = fusion_hints.get("as_master", [])
            as_detail = fusion_hints.get("as_detail", [])

            if as_master:
                lines.append(f"- {table_name} 作为主表: {'; '.join(as_master[:2])}")
            if as_detail:
                lines.append(f"- {table_name} 作为明细表: {'; '.join(as_detail[:2])}")

    return "\n".join(lines)


def make_rels_block_with_relationship_cards(tables: List[dict], relationship_data: dict) -> str:
    """
    基于关系卡片生成JOIN关系块（优先使用关系卡片，回退到传统推断）

    Args:
        tables: 表对象列表（当前簇的白名单表）
        relationship_data: 关系卡片数据

    Returns:
        JOIN关系文本块

    修复说明：
    - 关系卡片可能含有"当前簇白名单之外的表"的 JOIN 建议（同一数据源召回的其他表的卡片）
    - 必须按当前簇的白名单过滤，避免生成非白名单表别名导致 LLM 生成会被拦截的 SQL
    """
    join_suggestions = relationship_data.get("join_suggestions", [])

    if join_suggestions:
        # 使用关系卡片中的JOIN建议
        aliases = alias_tables(tables)
        # 物理表名集合（白名单），用于过滤掉非当前簇的 JOIN 建议
        whitelist_table_names = {t["table_name"] for t in tables}
        table_name_to_alias = {t["table_name"]: aliases[t["table_name"]] for t in tables}

        lines = []
        sorted_suggestions = sorted(join_suggestions, key=lambda x: x.get("confidence", 0), reverse=True)

        for sug in sorted_suggestions:
            from_table = sug.get("from_table", "")
            to_table = sug.get("to_table", "")
            from_col = sug.get("from_column", "")
            to_col = sug.get("to_column", "")

            # ✅ 白名单过滤：JOIN 两端必须都在当前簇白名单内
            # 修复：原来不过滤会把 from_table/to_table 不在白名单的 JOIN 也输出，
            # 导致 LLM 看到 from_alias 退化为原表名、最终生成的 SQL 会被第二层防护拦截。
            if from_table not in whitelist_table_names:
                print(f"[make_rels_block] 跳过非白名单表的JOIN建议: {from_table} (不在当前簇白名单)")
                continue
            if to_table not in whitelist_table_names:
                print(f"[make_rels_block] 跳过非白名单表的JOIN建议: {from_table} -> {to_table} ({to_table}不在当前簇白名单)")
                continue

            from_alias = table_name_to_alias[from_table]
            to_alias = table_name_to_alias[to_table]

            lines.append(f"{from_alias}.{from_col} = {to_alias}.{to_col}")

        if lines:
            return "\n".join(lines)

    # 回退到传统推断
    return make_rels_block(tables)
