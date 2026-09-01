"""
 @File: fill_filed_comment_excel.py
 @Description: 将从excel中提取到的字段描述匹配进抽取到的表结构信息中
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-22 15:05
"""

import json
import math

def _is_nan(x):
    return isinstance(x, float) and math.isnan(x)

def _norm_key(k):
    """把键标准化：去首尾空格并大写；None/NaN -> None"""
    if k is None or _is_nan(k):
        return None
    return str(k).strip().upper()

def _clean_val(v):
    """清洗值：字符串去首尾空格，其它类型原样返回"""
    if v is None or _is_nan(v):
        return None
    return v.strip() if isinstance(v, str) else v

# 获取被更新过的目标数据表
def get_common_tables(result: dict, excel_filed_data: list) -> list:
    """
    从 result['tables'] 和 excel_filed_data 中找出 table_name 匹配的表对象
    - 匹配规则：忽略大小写、去除首尾空格
    - 返回: target_tables 列表（同时存在的表对象）
    """
    def norm_name(x):
        if not x or not isinstance(x, str):
            return None
        return x.strip().upper()

    # 1. 提取 result 里的表名映射
    result_tables = result.get("tables", []) or []
    result_map = {norm_name(t.get("table_name")): t for t in result_tables if norm_name(t.get("table_name"))}

    # 2. 遍历 excel 表
    target_tables = []
    for tbl in excel_filed_data:
        tname_norm = norm_name(tbl.get("table_name"))
        if not tname_norm:
            continue
        if tname_norm in result_map:
            # 两边同时存在的表 → 加入结果
            target_tables.append(result_map[tname_norm])

    return target_tables

def fill_field_comments_from_excel(db_schemas_json_data: dict, excel_filed_data: list) -> dict:
    """
    参数:
      - db_schemas_json_data: JSON对象(dict)，包含 tables[*].columns[*].name / comment
      - excel_filed_data: 列表，每个元素为一个 dict：
          {
            "table_name": "...",            # 表名（用于匹配，忽略大小写、自动trim）
            "description": "...",           # 可选：表描述
            "<FIELD_A>": "注释A",           # 其余键视为字段名 => 注释；忽略大小写匹配列名
            "<FIELD_B>": "注释B",
            ...
          }

    返回:
      - 新的JSON对象(深拷贝)，把匹配到的值填入各列的 comment，并在有给定时更新表的 description
    """
    import copy

    result = copy.deepcopy(db_schemas_json_data)

    # 容错：空列表直接返回拷贝
    if not excel_filed_data:
        return result

    # 统一把 excel_filed_data 的每个条目预处理成 {norm_key: cleaned_val} 的查找表
    preprocessed = []
    for item in excel_filed_data:
        if not isinstance(item, dict):
            continue
        # 规范化：表名/描述单独取，其它键当字段名使用
        tname_raw = item.get("table_name")
        tname_norm = _norm_key(tname_raw)  # None/NaN -> None；字符串 trim+upper
        if not tname_norm:
            continue

        desc_val = _clean_val(item.get("description"))

        # 建立字段注释查找表（忽略大小写键）
        lookup = {}
        for k, v in item.items():
            if k in ("table_name", "description"):
                continue
            nk = _norm_key(k)
            cv = _clean_val(v)
            # 只回填“非空注释”，空注释不覆盖
            if nk and cv not in (None, ""):
                lookup[nk] = cv

        preprocessed.append({
            "table_name_norm": tname_norm,
            "description": desc_val,
            "lookup": lookup
        })

    # 遍历 schema 中的每张表和视图；对每一表/视图，遍历 excel 列表找"同名表/视图"（忽略大小写）
    # 处理 tables
    for table in result.get("tables", []) or []:
        schema_tname_norm = _norm_key(table.get("table_name"))
        if not schema_tname_norm:
            continue

        # 可能有多个 Excel 项命中同一张表；后命中的覆盖先命中的（常见"下游覆盖"语义）
        for item in preprocessed:
            if item["table_name_norm"] != schema_tname_norm:
                continue

            # 先回填表描述（若有）
            if item["description"] not in (None, ""):
                table["description"] = item["description"]

            # 再按字段名（忽略大小写）回填列注释
            if not table.get("columns"):
                continue
            for col in table["columns"]:
                col_name_norm = _norm_key(col.get("name"))
                if not col_name_norm:
                    continue
                if col_name_norm in item["lookup"]:
                    col["comment"] = item["lookup"][col_name_norm]
    
    # 处理 views（与 tables 相同的逻辑）
    for view in result.get("views", []) or []:
        schema_tname_norm = _norm_key(view.get("table_name"))
        if not schema_tname_norm:
            continue

        # 可能有多个 Excel 项命中同一张视图；后命中的覆盖先命中的
        for item in preprocessed:
            if item["table_name_norm"] != schema_tname_norm:
                continue

            # 先回填视图描述（若有）
            if item["description"] not in (None, ""):
                view["description"] = item["description"]

            # 再按字段名（忽略大小写）回填列注释
            if not view.get("columns"):
                continue
            for col in view["columns"]:
                col_name_norm = _norm_key(col.get("name"))
                if not col_name_norm:
                    continue
                if col_name_norm in item["lookup"]:
                    col["comment"] = item["lookup"][col_name_norm]
    
    # 获取匹配的表和视图
    target_tables = get_common_tables(result, excel_filed_data)
    # 同时获取匹配的视图（需要构造一个包含views的临时字典）
    views_result = {"tables": result.get("views", [])} if result.get("views") else {"tables": []}
    target_views = get_common_tables(views_result, excel_filed_data)
    rs_tables_dict = {'tables': target_tables, 'views': target_views}
    
    print(f"[FILL] 匹配到的表和视图: 表数量={len(target_tables)}, 视图数量={len(target_views)}")
    if target_tables:
        print(f"[FILL] 匹配到的表: {[t.get('table_name') for t in target_tables if t.get('table_name')]}")
    if target_views:
        print(f"[FILL] 匹配到的视图: {[v.get('table_name') for v in target_views if v.get('table_name')]}")

    return rs_tables_dict
