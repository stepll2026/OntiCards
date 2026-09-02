"""
 @File: extract_field_data_excel.py
 @Description: 从excel中提取对应数据库表的字段描述数据
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-12 15:25
"""
import json
import math
import os
from pathlib import Path

import flask_login
import pandas as pd
from flask import request, Blueprint
from flask_login import login_required
from flask_restful import Api, Resource
from werkzeug.utils import secure_filename

from controllers.datacard.data_card_db_api import delete_records_by_ids
from controllers.datacard.datacard_generator import generate_datacards_for_schema
from controllers.datasource.filedfill.fill_field_by_llm import enrich_table_before_insert, check_tables_health_batch
from controllers.datasource.filedfill.fill_filed_comment_excel import fill_field_comments_from_excel
from controllers.weaviate_db_tool.weaviate_api import batch_delete_by_uuids
from core.connect_info_encryptor import get_connect_info_hash, decrypt_connect_info, is_encrypted
from extensions.ext_database import db
from models.user_datasource_schema import UserDatasourceSchema
from models.datacards_datasource import DataCardDataSource

'''
    file_path：excel表格文件路径
    sheet_name数据库表字段描述所在的excel子工作表名
    field_data：存放表名tb_name_column、表描述tb_desc_column、字段名field_name_column、字段描述field_desc_column、取值附加描述field_value_desc_column的列映射及是否包含表头has_title

    作用：针对单数据库表，提取表描述和所有字段描述，返回字典
'''

# 基础配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 回到 datasource 目录
UPLOAD_FOLDER = os.path.join(BASE_DIR, "yploads")  # 固定存到项目内的 yploads
# 允许的文件，后面做拓展，目前支持excel
ALLOWED_EXTENSIONS = {"xlsx", "xls"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 最大20 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# === 注册 Flask Blueprint 和 API ===
extract_field_data_excel = Blueprint('extract_field_data_excel', __name__)
api = Api(extract_field_data_excel)


# 校验文件类型是否合法
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# 校验文件大小
def too_large(stream) -> bool:
    """仅本接口的大小限制，不影响全局。"""
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size > MAX_FILE_SIZE


# 获取数据所在列的pandas索引：实际列数-1   A:0，B:1...Z:25 以此类推。 例外 AA:26
def convert_excel_dict(input_dict: dict) -> dict:
    """将Excel列字母转换为从0开始的索引，并生成新字典"""

    def excel_col_to_index(col_letter: str) -> int:
        col_letter = col_letter.upper()
        result = 0
        for char in col_letter:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1  # pandas 索引从0开始

    output_dict = {}
    for key, value in input_dict.items():
        # 如果是纯字母字符串（比如 "A", "AA"），就转换
        if isinstance(value, str) and value.isalpha():
            output_dict[key] = excel_col_to_index(value)
        else:
            # 数字、字符串数字（"0"）、其他类型，保持原样但尽量转成 int
            if isinstance(value, str) and value.isdigit():
                output_dict[key] = int(value)
            else:
                output_dict[key] = value
    return output_dict


def is_empty(x):
    """把 None、NaN、''、'   ' 都视为空"""
    if x is None:
        return True
    # NaN (包括 numpy.float 的 NaN)
    try:
        if math.isnan(x):
            return True
    except TypeError:
        pass
    # 其它转成字符串再判断空白
    return str(x).strip() == ""


def first_index(lst, predicate, start=0):
    for i in range(start, len(lst)):
        if predicate(lst[i]):
            return i
    return -1


def gap_after_anchor_to_next_nonempty(lst, anchor_marker):
    """从锚点（如 'TDTPRD'）后一行起，直到下一个非空值之间的长度"""

    def norm(v):
        return None if is_empty(v) else str(v).strip().upper()

    i = first_index(lst, lambda v: norm(v) == str(anchor_marker).strip().upper())
    if i == -1:
        raise ValueError(f"未找到锚点 {anchor_marker!r}")
    j = first_index(lst, lambda v: not is_empty(v), i + 1)
    if j == -1:
        return len(lst) - i - 1
    return max(0, j - i - 1)


# 获取字段内容
def get_field_content_for_excel(file_path: str, sheet_name: str, field_data: dict, schema: dict):
    # 获取字段数据的映射字典【目标键：pandas列索引】
    field_data_index_dict = convert_excel_dict(field_data)
    print(field_data_index_dict)

    ext = os.path.splitext(file_path)[1].lower()

    # 关键修复：用 with 管理 ExcelFile，确保底层文件句柄被关闭
    with pd.ExcelFile(file_path) as xls:
        # --- 如果 sheet_name 为空，则使用第一个工作表 ---
        if not sheet_name:
            sheet_name = xls.sheet_names[0]
            print(f"[INFO] 未指定 sheet_name，默认使用第一个工作表: {sheet_name}")
        elif sheet_name not in xls.sheet_names:
            raise ValueError(f"指定的工作表名 {sheet_name!r} 不存在，文件中可选工作表: {xls.sheet_names}")
        print(f"[INFO] 使用工作表: {sheet_name}")

        # 读取 Excel 文件（用同一个 ExcelFile 句柄读，避免重复打开文件）
        if ext == ".xls":
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None, engine="xlrd")
        elif ext == ".xlsx":
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None, engine="openpyxl")
        else:
            raise ValueError("不支持的 Excel 格式: " + ext)

        # 获取表名列数据
        tb_name_col_data = df.iloc[field_data_index_dict['has_title']:, field_data_index_dict['tb_name_index']].tolist()
        print(tb_name_col_data)

        tb_names = [
            v for v in tb_name_col_data
            if v is not None and str(v).strip().lower() not in ('', 'null', 'none', 'nan')
        ]
        print("该工作表含数据库表数为：:" + str(len(tb_names)))
        print(tb_names)

        results = []
        for db_table_name in tb_names:
            # —— 你下面原来的逻辑保持不变 —— #
            table_obj = next(
                (t for t in schema.get("tables", [])
                 if str(t.get("table_name", "")).strip().lower() == str(db_table_name).strip().lower()),
                None
            )
            if not table_obj:
                table_obj = next(
                    (v for v in schema.get("views", [])
                     if str(v.get("table_name", "")).strip().lower() == str(db_table_name).strip().lower()),
                    None
                )

            if table_obj:
                obj_type = "视图" if table_obj.get("is_view") else "表"
                print(f"[MATCH] Excel中的 '{db_table_name}' 匹配到数据库中的{obj_type}: {table_obj.get('table_name')}")
            else:
                print(f"[MATCH] Excel中的 '{db_table_name}' 未在数据库中找到匹配的表或视图")
                continue

            columns_len = len(table_obj.get("columns", []))
            obj_type = "视图" if table_obj.get("is_view") else "表"
            print(f"数据库{obj_type}【{db_table_name}】的字段数量:{columns_len}")
            excel_filed_length = gap_after_anchor_to_next_nonempty(tb_name_col_data, db_table_name)
            print("excel字段区间长度" + str(excel_filed_length))

            # 这里也改成用 xls 读取，而不是 pd.read_excel(file_path, ...)
            target_sheet = None
            anchor_idx = None
            for name in xls.sheet_names:
                df2 = pd.read_excel(xls, sheet_name=name, header=None)
                tb_name_col = df2.iloc[:, field_data_index_dict['tb_name_index']].astype(str).str.strip().str.upper()
                db_table_name_upper = str(db_table_name).strip().upper()
                hits = tb_name_col[tb_name_col == db_table_name_upper].index.tolist()
                if hits:
                    target_sheet = name
                    anchor_idx = hits[0]
                    break

            if target_sheet is None or anchor_idx is None:
                print(f"未在工作表中找到目标数据库表或视图: {db_table_name}")
                continue

            target_excel_row = anchor_idx + 1
            print("目标表所在行索引:" + str(anchor_idx) + "，行号:" + str(target_excel_row))

            # 同样使用 xls 读取
            df3 = pd.read_excel(xls, sheet_name=target_sheet, header=None)

            table_description = df3.iloc[anchor_idx, field_data_index_dict['tb_desc_index']]
            print("表描述:" + str(table_description))

            start = anchor_idx + 1
            end = min(start + excel_filed_length, df3.shape[0])

            raw_b_values = df3.iloc[start:end, field_data_index_dict['field_name_index']].tolist()
            e_values = df3.iloc[start:end, field_data_index_dict['field_desc_index']].tolist()
            f_values = df3.iloc[start:end, field_data_index_dict['field_value_desc_index']].tolist()

            b_values = []
            for b in raw_b_values:
                if b is None or (isinstance(b, float) and pd.isna(b)):
                    b_values.append("")
                else:
                    b_values.append(str(b).strip())

            ef_values = []
            for e, f in zip(e_values, f_values):
                e_clean = "" if (e is None or (isinstance(e, float) and pd.isna(e))) else str(e).strip()
                f_clean = "" if (f is None or (isinstance(f, float) and pd.isna(f))) else str(f).strip()
                f_clean = f_clean.replace("\n", ",") if f_clean else ""
                ef_values.append(e_clean + "." + f_clean if e_clean and f_clean else e_clean or f_clean)

            bef_dict = dict(zip(b_values, ef_values))
            bef_dict['description'] = table_description
            bef_dict['table_name'] = db_table_name

            results.append(bef_dict)

        print("所有表处理完成，总数:", len(results))
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return results


# 更新数据库中对应的数据库表字段描述
def update_schema_text(fill_rs_dict: dict, rs_table_names: list, user_id: str, connect_info: str,
                       original_schema_dict: dict):
    """
    遍历 rs_table_names，匹配 fill_rs 中的对象，更新数据库中 schema_text 字段
    :param fill_rs_dict: {'tables':[{'table_name': 'DDTCCY1', ...}, {...}], 'views':[...]}
    :param rs_table_names: ['DDTCCY1', 'TDTCONA', ...]
    :param user_id: 用户ID
    :param connect_info: 数据库连接信息
    :param original_schema_dict: 原始的schema字典（更新前），用于对比变更
    :return: 详细的变更信息字典
    """

    # 获取其中的tables和views列表，合并处理
    fill_tables = fill_rs_dict.get("tables", [])
    fill_views = fill_rs_dict.get("views", [])
    fill_rs = fill_tables + fill_views

    print(f"[UPDATE] 准备更新的表和视图: 表数量={len(fill_tables)}, 视图数量={len(fill_views)}, 总计={len(fill_rs)}")
    if fill_tables:
        print(f"[UPDATE] 待更新的表: {[t.get('table_name') for t in fill_tables if t.get('table_name')]}")
    if fill_views:
        print(f"[UPDATE] 待更新的视图: {[v.get('table_name') for v in fill_views if v.get('table_name')]}")

    # 构建原始schema的映射 {table_name: original_obj}
    original_tables_map = {}
    for t in (original_schema_dict.get("tables", []) or []):
        if "table_name" in t:
            original_tables_map[t["table_name"]] = t
    for v in (original_schema_dict.get("views", []) or []):
        if "table_name" in v:
            original_tables_map[v["table_name"]] = v

    # 在进行LLM填充前，先进行表健康检查，记录有问题的表
    health_check_result = None
    if fill_rs:
        try:
            health_check_result = check_tables_health_batch(
                tables=fill_rs,
                user_id=user_id,
                connect_info=connect_info
            )
        except Exception as e:
            # 健康检查失败不影响后续流程
            print(f"[HEALTH_CHECK][WARN] 健康检查失败: {e}")

    # 先构建一个 {table_name: obj} 的映射，加快匹配
    table_to_obj = {obj["table_name"]: obj for obj in fill_rs if "table_name" in obj}

    # ORM 查询符合条件的记录
    # 重要：UserDatasourceSchema.connect_info 已加密存储，必须用 connect_info_hash 稳定哈希匹配。
    # 同时兼容 connect_info 可能为密文（前端回传）或明文（直接传 DSN）两种情况：
    #   - 优先用传入明文计算 hash 直接匹配（性能最佳）
    #   - 若未命中，再尝试用解密后的明文计算 hash（兼容前端回传密文的链路）
    def _records_by_hash(user_id, connect_info):
        if not connect_info:
            return []
        # 直接用入参明文计算 hash
        direct_hash = get_connect_info_hash(connect_info)
        recs = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info_hash=direct_hash
        ).all()
        if recs:
            return recs
        # 入参可能是密文，解密后再算一次 hash 兜底
        try:
            plain = decrypt_connect_info(connect_info) if is_encrypted(connect_info) else connect_info
        except Exception:
            plain = connect_info
        if plain == connect_info:
            return recs
        plain_hash = get_connect_info_hash(plain)
        if plain_hash == direct_hash:
            return recs
        return UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info_hash=plain_hash
        ).all()

    records = _records_by_hash(user_id, connect_info)

    # 保存填充后的表对象，用于后续对比
    enriched_tables = []
    # 收集详细的变更信息
    table_change_details = []

    for record in records:
        if record.table_name not in rs_table_names:
            continue
        if record.table_name not in table_to_obj:
            continue

        table_name = record.table_name
        obj = table_to_obj[table_name]
        original_obj = original_tables_map.get(table_name, {})

        # 二次补全：把 Excel 回填后的对象再交给 LLM 做"只填空不覆盖"的补全
        try:
            enriched_obj, _changed = enrich_table_before_insert(obj)
        except Exception as e:
            # 失败不中断，降级为 obj
            enriched_obj = obj

        # 保存填充后的表对象
        enriched_tables.append(enriched_obj)

        # 收集字段级别的变更详情
        field_changes = []
        original_columns = {c.get("name"): c for c in (original_obj.get("columns", []) or []) if "name" in c}
        excel_filled_columns = {c.get("name"): c for c in (obj.get("columns", []) or []) if "name" in c}
        enriched_columns = {c.get("name"): c for c in (enriched_obj.get("columns", []) or []) if "name" in c}

        total_fields = len(enriched_columns)
        excel_filled_count = 0
        llm_filled_count = 0
        still_missing_count = 0

        for field_name, enriched_col in enriched_columns.items():
            original_comment = (original_columns.get(field_name, {}).get("comment") or "").strip()
            excel_filled_comment = (excel_filled_columns.get(field_name, {}).get("comment") or "").strip()
            final_comment = (enriched_col.get("comment") or "").strip()

            # 判断来源
            source = "unchanged"
            changed = False

            if not original_comment and not final_comment:
                # 仍然缺失
                source = "missing"
                still_missing_count += 1
            elif original_comment != final_comment:
                changed = True
                if excel_filled_comment and excel_filled_comment == final_comment:
                    # Excel填充
                    source = "excel"
                    excel_filled_count += 1
                elif not excel_filled_comment and final_comment:
                    # LLM补全
                    source = "llm"
                    llm_filled_count += 1
                elif excel_filled_comment and excel_filled_comment != original_comment:
                    # Excel覆盖
                    source = "excel"
                    excel_filled_count += 1

            field_changes.append({
                "field_name": field_name,
                "before_comment": original_comment,
                "after_comment": final_comment,
                "source": source,
                "changed": changed
            })

        # 表描述变更
        original_desc = (original_obj.get("description") or "").strip()
        final_desc = (enriched_obj.get("description") or "").strip()
        table_desc_updated = original_desc != final_desc

        table_change_details.append({
            "table_name": table_name,
            "table_description_updated": table_desc_updated,
            "table_description_before": original_desc,
            "table_description_after": final_desc,
            "total_fields": total_fields,
            "updated_fields": excel_filled_count + llm_filled_count,
            "excel_filled_fields": excel_filled_count,
            "llm_filled_fields": llm_filled_count,
            "still_missing_fields": still_missing_count,
            "field_changes": field_changes
        })

        # 最终写入 schema_text
        record.schema_text = json.dumps(enriched_obj, ensure_ascii=False)

    db.session.commit()

    # 在填充后，再次进行健康检查，对比填充前后的状态
    health_check_result_after = None
    if fill_rs and enriched_tables:
        try:
            health_check_result_after = check_tables_health_batch(
                tables=fill_rs,
                user_id=user_id,
                connect_info=connect_info,
                enriched_tables=enriched_tables
            )
        except Exception as e:
            # 健康检查失败不影响后续流程
            print(f"[HEALTH_CHECK][WARN] 填充后健康检查失败: {e}")

    # 将填充明细写入各表记录的 is_filled / filled_data 字段
    try:
        before_problem_map = {}
        try:
            for item in (health_check_result or {}).get("problematic_tables", []) or []:
                name = (item or {}).get("table_name")
                if name:
                    before_problem_map[name] = item
        except Exception:
            before_problem_map = {}

        after_problem_map = {}
        try:
            for item in (health_check_result_after or {}).get("problematic_tables", []) or []:
                name = (item or {}).get("table_name")
                if name:
                    after_problem_map[name] = item
        except Exception:
            after_problem_map = {}

        # 便于取到 LLM 填充后的表描述
        enriched_by_name = {}
        try:
            enriched_by_name = {
                (obj or {}).get("table_name"): obj
                for obj in (enriched_tables or [])
                if isinstance(obj, dict) and (obj or {}).get("table_name")
            }
        except Exception:
            enriched_by_name = {}

        for record in records:
            if record.table_name not in rs_table_names:
                continue
            # 依据“填充前是否存在缺失”来标记 is_filled；并将明细写入 filled_data
            before_entry = before_problem_map.get(record.table_name) or {}
            after_entry = after_problem_map.get(record.table_name) or {}

            # detailed_fill（和 JSON 报告一致的表级结构）
            detailed_fill = {}
            try:
                fill_result = (after_entry or {}).get("fill_result") or {}
                filled_map = {}
                for it in (fill_result.get("filled_fields") or []):
                    n = (it or {}).get("name")
                    c = (it or {}).get("comment")
                    if n and c is not None:
                        filled_map[n] = c
                still_missing_names = [
                    i.get("name")
                    for i in (fill_result.get("still_missing_fields") or [])
                    if i.get("name")
                ]
                detailed_fill = {
                    "table_name": record.table_name,
                    "filled_map": filled_map,
                    "still_missing_fields": still_missing_names,
                    # 由 LLM 补全后的表级描述
                    "filled_table_description": ((enriched_by_name.get(record.table_name) or {}).get("description"))
                }
            except Exception:
                detailed_fill = {
                    "table_name": record.table_name,
                    "filled_table_description": ((enriched_by_name.get(record.table_name) or {}).get("description"))
                }

            had_missing_before = bool(before_entry)
            per_table_payload = {
                "table_name": record.table_name,
                "before": before_entry or {},
                "fill_result": (after_entry or {}).get("fill_result") or {},
                "detailed_fill": detailed_fill
            }

            record.is_filled = had_missing_before
            record.filled_data = (json.dumps(per_table_payload, ensure_ascii=False) if had_missing_before else None)

        db.session.commit()
    except Exception as _e:
        print(f"[HEALTH_CHECK][WARN] 写入 is_filled/filled_data 失败: {_e}")

    # 返回详细的变更信息
    return {
        "message": "ok",
        "table_change_details": table_change_details
    }


class ExtractFieldDataFromExcel(Resource):
    """
        请求参数:
        {
            "file": 上传的file文件对象,
            "connect_info": 数据库连接信息,
            "sheet_name": 子工作表名,
            "field_data":{
                "has_title": '0',               是否含标题标志
                "tb_name_index": 'A',           表名所在列
                "tb_desc_index": 'B',           表描述所在列
                "field_name_index": 'B',        字段名所在列
                "field_desc_index": 'E',        字段描述所在列
                "field_value_desc_index": 'F'   字段取值附加描述所在列
            }
        }
    """

    @login_required
    def post(self):
        # 1、接收文件
        if "file" not in request.files:
            return {"error": "No file part"}, 400

        file = request.files["file"]

        # 2、校验文件类型、大小是否合法
        if not file or file.filename == "":
            return {"error": "缺少文件（字段名应为 file）"}, 400

        if not allowed_file(file.filename):
            return {"error": f"不支持的文件类型，仅允许: {sorted(ALLOWED_EXTENSIONS)}"}, 400

        if too_large(file.stream):
            return {"error": f"文件过大，最大支持 {MAX_FILE_SIZE // (1024 * 1024)}MB"}, 400

        # 2、接收表单中的其他配置参数
        try:
            field_data = json.loads(request.form.get("field_data", ""))
        except json.JSONDecodeError:
            return {"error": "field_data 不是合法 JSON"}, 400

        # 从表单接收其他字段
        connect_info = request.form.get("connect_info")
        sheet_name = request.form.get("sheet_name")

        # 检查必填字段
        if not connect_info:
            return {"error": "缺少必填字段: connect_info"}, 400

        # 3、文件保存
        # 1) 原始文件名（可能是中文）
        orig = file.filename or ""
        # 2) 先取扩展名（不动它）
        ext = Path(orig).suffix.lower()  # .xlsx / .xls / .csv / 或空串""
        # 3) 只净化“基名”，不动扩展名
        safe_base = secure_filename(Path(orig).stem) or "yile"
        # 4) 如果确实没有扩展名，再根据 mimetype 补齐（不默认 .xlsx，你说还可能是 xls/csv）
        if not ext:
            mime = (file.mimetype or "").lower()
            mime2ext = {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                "application/vnd.ms-excel": ".xls"  # 有些 CSV 也会被浏览器/Apifox 误报成这个
            }
            ext = mime2ext.get(mime, "")  # 真的判断不出就留空，让后续逻辑去兜底/报错
        unique_name = f"yile{ext}"  # 固定文件名，比如 yile.xlsx
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)
        # 如果之前有文件，会被覆盖
        file.save(save_path)

        # 关闭资源
        file.close()

        # 4、数据处理（提取字段描述）
        # (1)先根据 用户id+数据库连接信息 获取目标库中的所有表信息和视图信息
        tables = []
        views = []
        # 重要：UserDatasourceSchema.connect_info 已加密存储，AES-GCM nonce 随机，密文不可等值比较。
        # 统一改用 connect_info_hash 稳定哈希匹配。
        connect_info_hash = get_connect_info_hash(connect_info) if connect_info else ''
        records_q = UserDatasourceSchema.query.filter_by(
            user_id=flask_login.current_user.id,
            connect_info_hash=connect_info_hash
        )
        # 回退：若 hash 未命中，再用解密后的明文 connect_info 匹配（兼容历史未加密数据 / 密文入参）
        records = records_q.all()
        if not records and connect_info:
            try:
                plain = decrypt_connect_info(connect_info) if is_encrypted(connect_info) else connect_info
            except Exception:
                plain = connect_info
            if plain and plain != connect_info:
                records = UserDatasourceSchema.query.filter_by(
                    user_id=flask_login.current_user.id,
                    connect_info_hash=get_connect_info_hash(plain)
                ).all()
            if not records and plain:
                # 兜底：直接用明文等值匹配（覆盖历史 connect_info 未加密的数据）
                records = UserDatasourceSchema.query.filter_by(
                    user_id=flask_login.current_user.id,
                    connect_info=plain
                ).all()
        for record in records:
            s = record.schema_text
            if not s:
                continue
            try:
                obj = json.loads(s) if isinstance(s, str) else s
            except json.JSONDecodeError:
                # 记录日志后跳过这条脏数据
                continue
            # 最好校验关键键是否存在
            if isinstance(obj, dict) and "table_name" in obj:
                # 根据 is_view 字段区分表和视图
                if record.is_view or obj.get("is_view"):
                    views.append(obj)
                else:
                    tables.append(obj)

        schema_dict = {"tables": tables, "views": views}
        print(f"数据库中的所有表信息: 表数量={len(tables)}, 视图数量={len(views)}")

        # 保存原始schema（用于对比变更）
        import copy
        original_schema_dict = copy.deepcopy(schema_dict)

        # (2)获取字段提取结果【多个obj的列表】
        excel_filed_datas = get_field_content_for_excel(save_path, sheet_name, field_data, schema_dict)
        print("字段提取结果:", excel_filed_datas)  # 只含目标表的字段描述

        # 收集Excel中的所有表名
        excel_table_names = [obj.get("table_name") for obj in excel_filed_datas if obj.get("table_name")]

        # 5、数据回填并入库【更新提取到的目标表的schema_text字段，重新生成数据卡片并更新数据库和向量库】

        # (1)数据回填
        fill_rs = fill_field_comments_from_excel(schema_dict, excel_filed_datas)
        # print("字段回填结果:", json.dumps(fill_rs, ensure_ascii=False, indent=4))

        # 收集匹配和未匹配的表信息
        matched_tables = []
        unmatched_tables_detail = []

        # 获取数据库中所有表名（忽略大小写）
        db_table_names_lower = {t.get("table_name", "").strip().lower(): t.get("table_name") for t in (tables + views)
                                if t.get("table_name")}

        for excel_table_name in excel_table_names:
            excel_name_lower = excel_table_name.strip().lower()
            if excel_name_lower in db_table_names_lower:
                matched_tables.append(db_table_names_lower[excel_name_lower])
            else:
                unmatched_tables_detail.append({
                    "table_name": excel_table_name,
                    "reason": "数据库中不存在此表"
                })

        # (2)更新数据库
        rs_table_names = matched_tables  # 只更新匹配到的表
        print(f"从excel中提取到字段数据的表/视图名为:{rs_table_names}")

        ids = []  # 收集目标数据表的id，用以后续查数据卡片库获取w_uuid
        # 根据 rs_table_names 中的表名查询数据库，获取表名对应的id
        # 重要：connect_info 已加密存储，统一用 connect_info_hash 稳定哈希匹配
        _ci_hash = get_connect_info_hash(connect_info) if connect_info else ''
        # 同时准备解密后的明文 hash（兼容 connect_info 是密文的链路）
        try:
            _ci_plain = decrypt_connect_info(connect_info) if is_encrypted(connect_info) else connect_info
        except Exception:
            _ci_plain = connect_info
        _ci_plain_hash = get_connect_info_hash(_ci_plain) if (_ci_plain and _ci_plain != connect_info) else _ci_hash
        for table_name in rs_table_names:
            record = UserDatasourceSchema.query.filter_by(
                user_id=flask_login.current_user.id,
                connect_info_hash=_ci_hash,
                table_name=table_name
            ).first()
            if not record and _ci_plain_hash != _ci_hash:
                record = UserDatasourceSchema.query.filter_by(
                    user_id=flask_login.current_user.id,
                    connect_info_hash=_ci_plain_hash,
                    table_name=table_name
                ).first()
            if not record and _ci_plain:
                # 兜底：明文等值匹配（兼容历史数据）
                record = UserDatasourceSchema.query.filter_by(
                    user_id=flask_login.current_user.id,
                    connect_info=_ci_plain,
                    table_name=table_name
                ).first()
            if record:
                print(f"已找到表名: {table_name} 对应的记录 ID: {record.id}")
                ids.append(str(record.id))

        update_rs = update_schema_text(fill_rs, rs_table_names, flask_login.current_user.id, connect_info,
                                       original_schema_dict)
        print("更新数据库结果:", update_rs)

        # (3)用最新的schema结构数据生成卡片并更新数据库和向量库【删除旧的再新增】
        # 查数据卡片数据库，获取w_uuid，用以删除向量库
        w_uuids = []
        # 根据每个 id 查询 DataCardDataSource 表，并获取 w_uuid 字段
        for record_id in ids:
            record = DataCardDataSource.query.filter_by(doc_id=str(record_id)).first()  # 查询 DataCardDataSource 表
            if record:
                w_uuids.append(record.w_uuid)  # 获取 w_uuid 并加入到 w_uuids 列表
                print(f"记录 ID: {record_id} 的 w_uuid 是: {record.w_uuid}")
            else:
                print(f"未找到 ID: {record_id} 对应的记录")
        # 删除数据卡片库中已生成的卡片和向量库中的数据
        delete_db_rs = delete_records_by_ids(ids)
        print("删除数据卡片库中已生成的卡片结果:", delete_db_rs)
        delete_w_rs = batch_delete_by_uuids(w_uuids, class_name=flask_login.current_user.weaviate_class_name)
        print("删除向量库中的数据结果:", delete_w_rs)

        # 回查 connect_name 和 datasource_id（同一 connect_info 下应一致）
        from models.datasource_infos import DatasourceInfo
        # 重要：DatasourceInfo.connect_info 已加密存储，必须用 connect_info_hash 稳定哈希匹配
        _ds_ci_hash = get_connect_info_hash(connect_info) if connect_info else ''
        datasource = (
            db.session.query(DatasourceInfo)
            .filter_by(user_id=flask_login.current_user.id, connect_info_hash=_ds_ci_hash)
            .first()
        )
        if not datasource and connect_info:
            try:
                _ds_plain = decrypt_connect_info(connect_info) if is_encrypted(connect_info) else connect_info
            except Exception:
                _ds_plain = connect_info
            if _ds_plain and _ds_plain != connect_info:
                datasource = (
                    db.session.query(DatasourceInfo)
                    .filter_by(user_id=flask_login.current_user.id, connect_info_hash=get_connect_info_hash(_ds_plain))
                    .first()
                )
            if not datasource and _ds_plain:
                # 兜底：明文等值匹配（兼容历史数据）
                datasource = (
                    db.session.query(DatasourceInfo)
                    .filter_by(user_id=flask_login.current_user.id, connect_info=_ds_plain)
                    .first()
                )
        connect_name = datasource.connect_name if datasource else None
        datasource_id = str(datasource.id) if datasource else None

        # 只传入需要更新的数据表/视图信息（fill_rs 包含 tables 和 views）
        all_data_cards = generate_datacards_for_schema(
            fill_rs,
            flask_login.current_user.id,
            connect_info,
            connect_name,
            datasource_id=datasource_id,  # 传入 datasource_id
            weaviate_class_name=flask_login.current_user.weaviate_class_name
        )
        if not all_data_cards:
            print("[INFO] 没有生成任何数据名片。")
            return

        datacards_count = len(all_data_cards) if isinstance(all_data_cards, list) else 0
        print(f"-------------------数据卡片生成成功，总计: {datacards_count} 张-------------------")

        # 7、组装详细的返回结果
        table_change_details = update_rs.get("table_change_details", [])

        # 计算汇总统计
        total_fields_updated = 0
        total_fields_from_excel = 0
        total_fields_from_llm = 0

        for table_detail in table_change_details:
            total_fields_updated += table_detail.get("updated_fields", 0)
            total_fields_from_excel += table_detail.get("excel_filled_fields", 0)
            total_fields_from_llm += table_detail.get("llm_filled_fields", 0)

        result = {
            "code": 200,
            "msg": "success",
            "data": {
                "summary": {
                    "total_tables_in_excel": len(excel_table_names),
                    "matched_tables": len(matched_tables),
                    "unmatched_tables": len(unmatched_tables_detail),
                    "total_fields_updated": total_fields_updated,
                    "total_fields_from_excel": total_fields_from_excel,
                    "total_fields_from_llm": total_fields_from_llm,
                    "datacards_deleted": len(w_uuids),
                    "datacards_generated": datacards_count
                },
                "table_details": table_change_details,
                "unmatched_tables_detail": unmatched_tables_detail
            }
        }
        # 让 Flask-RESTful 自己序列化
        return result, 200


api.add_resource(ExtractFieldDataFromExcel, '/extract_field_data_excel')
