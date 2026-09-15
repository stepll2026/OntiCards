"""Recall each requirement independently and retain the union of its dependencies."""
import json
import re

from controllers.query.query_validation import QueryValidationError


MAX_QUERY_CARDS = 80


def recall_requirements(contract, retrieve, **kwargs):
    queries = [contract["original_question"], contract["expanded_question"]]
    # Separate recall keeps a new person/currency hit from displacing a project hit.
    queries.extend(item["text"] for item in contract["requirements"])
    queries = list(dict.fromkeys(query for query in queries if query))
    if len(queries) > 16:
        raise QueryValidationError(["查询需求过多，请拆分提问以便完整检索"])
    cards = {}
    usage = {}
    recalled_by = {}
    for query in queries:
        result = retrieve(query, **kwargs)
        doc_ids = result.get("doc_ids") or []
        results = result.get("data_card_results") or []
        if len(doc_ids) != len(results) or any(not isinstance(card, dict) for card in results):
            raise QueryValidationError(["检索返回的数据卡片不完整或格式无效"], "unverified")
        for doc_id, card in zip(doc_ids, results):
            cards[str(doc_id)] = card
            recalled_by.setdefault(str(doc_id), []).append(query)
        current = result.get("usage") or {}
        for name in ("embedding_tokens", "rerank_tokens", "rerank_ms", "reranked_count"):
            usage[name] = usage.get(name, 0) + current.get(name, 0)
        if len(cards) > MAX_QUERY_CARDS:
            raise QueryValidationError(["所需数据卡片超过查询容量，请缩小查询范围；未截断必要表"])
    return {"doc_ids": list(cards), "data_card_results": list(cards.values()), "usage": usage,
            "retrieval": {"queries": queries, "recalled_by": recalled_by}}


def _name(name):
    return str(name or "").replace('[', '').replace(']', '').replace('"', '').replace('`', '').lower()


def _table_names(card, schema):
    """Cards often store a bare table name and keep its schema in the ORM row."""
    meta = card.get("SQLMeta") or {}
    name = _name(meta.get("table") or schema.table_name)
    names = {name}
    if '.' not in name:
        namespace = _name(meta.get("schema") or getattr(schema, "schema_name", None))
        database = _name(getattr(schema, "database_name", None))
        if namespace:
            names.add(namespace + '.' + name)
            if database:
                names.add(database + '.' + namespace + '.' + name)
        if database and getattr(schema, "db_type", None) in {"mysql", "mariadb", "oceanbase"}:
            names.add(database + '.' + name)
    return names


def card_references(card):
    meta = card.get("SQLMeta") or {}
    names = set()
    for foreign_key in meta.get("foreign_keys") or []:
        name = foreign_key.get("ref_table") or foreign_key.get("referenced_table")
        if name:
            names.add(name)
    # Explicit table.column references in descriptions are useful even without DB FKs.
    descriptions = [str(card.get("Abstract") or "")]
    descriptions.extend(str(column.get("comment") or "") for column in meta.get("columns") or [])
    for match in re.finditer(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){1,3})\b", " ".join(descriptions)):
        names.add(match.group(1).rsplit('.', 1)[0])
    return names


def expand_dependencies(result, load_candidates):
    """load_candidates(card, refs) must enforce owner AND selected datasource boundaries."""
    cards = dict(zip(result["doc_ids"], result["data_card_results"]))
    pending = list(cards.values())
    expanded = []
    while pending:
        source = pending.pop(0)
        if not isinstance(source, dict):
            raise QueryValidationError(["数据卡片内容无效"])
        refs = card_references(source)
        if not refs:
            continue
        for doc_id, card in load_candidates(source, refs):
            doc_id = str(doc_id)
            if doc_id in cards:
                continue
            if len(cards) >= MAX_QUERY_CARDS:
                raise QueryValidationError(["关联依赖超过查询容量，请缩小范围；未静默丢弃关联表"])
            cards[doc_id] = card
            pending.append(card)
            expanded.append({"doc_id": doc_id, "table": (card.get("SQLMeta") or {}).get("table")})
    result.update(doc_ids=list(cards), data_card_results=list(cards.values()))
    result.setdefault("retrieval", {})["dependencies_added"] = expanded
    return result


def expand_owned_dependencies(result, user_id, datasource_filter):
    """Resolve exact references within the same authorized data source, including legacy cards."""
    from sqlalchemy import String, cast, or_, func
    from models.datacards_datasource import DataCardDataSource
    from models.user_datasource_schema import UserDatasourceSchema
    from models.datasource_infos import DatasourceInfo
    from extensions.ext_database import db

    owned_sources = DatasourceInfo.query.filter_by(user_id=user_id).all()
    selected_ids = None
    if datasource_filter:
        ids = datasource_filter if isinstance(datasource_filter, list) else [datasource_filter]
        selected_ids = {str(value) for value in ids}
    allowed = {row.connect_name: str(row.id) for row in owned_sources
               if selected_ids is None or str(row.id) in selected_ids}
    # The legacy execution path resolves a connection by its name. Refuse an
    # ambiguous name rather than silently choose a different connection.
    recalled_names = {(card.get("DocInfo") or {}).get("connect_name")
                      for card in result["data_card_results"] if isinstance(card, dict)}
    for name in recalled_names & allowed.keys():
        if sum(row.connect_name == name for row in owned_sources) > 1:
            raise QueryValidationError(["数据源连接名称重复，请使用唯一名称后重试：" + str(name)])

    def load(source, refs):
        connect_name = (source.get("DocInfo") or {}).get("connect_name")
        ds_id = allowed.get(connect_name)
        if not ds_id:
            return []
        simple_names = {_name(name).rsplit('.', 1)[-1] for name in refs}
        candidates = (db.session.query(DataCardDataSource, UserDatasourceSchema)
            .join(UserDatasourceSchema, DataCardDataSource.doc_id == cast(UserDatasourceSchema.id, String))
            .filter(UserDatasourceSchema.user_id == user_id)
            .filter(or_(DataCardDataSource.user_id == user_id, DataCardDataSource.user_id.is_(None)))
            .filter(or_(DataCardDataSource.datasource_id == ds_id, DataCardDataSource.datasource_id.is_(None)))
            .filter(or_(func.lower(DataCardDataSource.table_name).in_(simple_names),
                        func.lower(UserDatasourceSchema.table_name).in_(simple_names),
                        func.lower(DataCardDataSource.table_name).in_({_name(ref) for ref in refs}))))
        matches = {}
        matched_refs = {}
        for row, schema in candidates:
            try:
                card = json.loads(row.card_data)
            except (TypeError, ValueError):
                continue
            if (card.get("DocInfo") or {}).get("connect_name") != connect_name:
                continue
            names = _table_names(card, schema)
            for ref in refs:
                key = _name(ref)
                if not any(name == key or ('.' not in key and name.rsplit('.', 1)[-1] == key) for name in names):
                    continue
                if key in matched_refs and matched_refs[key] != row.doc_id:
                    raise QueryValidationError(["关联表名存在歧义，请在卡片中明确 schema.table：" + key])
                matched_refs[key] = row.doc_id
                matches[row.doc_id] = (row.doc_id, card)
        return list(matches.values())

    # Apply owner and source filtering to initial vector hits as well.
    owned = {str(row.id) for row in UserDatasourceSchema.query.filter_by(user_id=user_id)
             .filter(UserDatasourceSchema.id.in_(result["doc_ids"])).all()}
    selected = [(doc, card) for doc, card in zip(result["doc_ids"], result["data_card_results"])
                if str(doc) in owned and isinstance(card, dict)
                and (card.get("DocInfo") or {}).get("connect_name") in allowed]
    result.update(doc_ids=[doc for doc, _ in selected], data_card_results=[card for _, card in selected])
    return expand_dependencies(result, load)
