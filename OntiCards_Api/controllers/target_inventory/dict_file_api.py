"""
 @File: dict_file_api.py
 @Description: 字典文件上传和解析
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 16:30
"""

from __future__ import annotations
import os
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Blueprint, request
from flask_restful import Resource, Api
from flask_login import login_required
from werkzeug.utils import secure_filename

# 字典文件上传目录（放在 target_inventory 目录下）
DICT_UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "dict_uploads"
)
os.makedirs(DICT_UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

dict_file_bp = Blueprint("dict_file_bp", __name__)
api = Api(dict_file_bp)


# ================== 统一响应格式 ==================
def _json_safe(obj):
    """JSON序列化安全处理"""
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    return obj


def _deep_json_safe(data):
    """深度JSON安全转换"""
    return json.loads(json.dumps(data, default=_json_safe, ensure_ascii=False))


def format_response(data=None, code: int = 200, message: str = "操作成功"):
    """
    统一返回格式

    Args:
        data: 返回数据
        code: HTTP状态码
        message: 提示信息

    Returns:
        (响应体, HTTP状态码)
    """
    return {"code": code, "message": message, "data": _deep_json_safe(data)}, code


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def too_large(stream) -> bool:
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size > MAX_FILE_SIZE


class DictFileUploadAPI(Resource):
    @login_required
    def post(self):
        """
        上传字典文件（Excel/CSV）

        请求：
        - file: Excel/CSV 文件
        - dict_name: 字典名称（可选）

        返回：
        {
            "code": 200,
            "message": "上传成功",
            "data": {
                "dict_file_id": "dict_file.xlsx",
                "entry_count": 156,
                "preview": [...],
                "save_path": "/path/to/file"
            }
        }
        """
        # 校验：是否包含文件
        if "file" not in request.files:
            return format_response(None, 400, "缺少文件")

        file = request.files["file"]
        if not file or file.filename == "":
            return format_response(None, 400, "文件为空")

        # 校验文件类型
        if not allowed_file(file.filename):
            return format_response(
                None,
                400,
                f"不支持的文件类型，仅允许: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # 校验文件大小
        if too_large(file.stream):
            return format_response(
                None,
                400,
                f"文件过大，最大支持 {MAX_FILE_SIZE // (1024 * 1024)}MB"
            )

        # 保存文件
        # 先获取原始文件扩展名（避免中文文件名被 secure_filename 移除）
        original_ext = os.path.splitext(file.filename)[1].lower()
        # 使用固定文件名，新文件会覆盖旧文件
        dict_file_id = f"dict_file{original_ext}"
        save_path = os.path.join(DICT_UPLOAD_FOLDER, dict_file_id)

        # 删除其他扩展名的旧字典文件（确保始终只保留一个最新文件）
        try:
            for old_file in os.listdir(DICT_UPLOAD_FOLDER):
                if old_file.startswith("dict_file") and old_file != dict_file_id:
                    old_path = os.path.join(DICT_UPLOAD_FOLDER, old_file)
                    os.remove(old_path)
                    print(f"[字典文件上传] 删除旧文件: {old_file}")
        except Exception as e:
            print(f"[字典文件上传] 清理旧文件失败: {e}")

        # 保存上传的文件
        try:
            file.save(save_path)
            file.close()
        except Exception as e:
            return format_response(None, 500, f"文件保存失败：{str(e)}")

        # 解析字典文件
        try:
            entries = parse_dict_file(save_path)
            data = {
                "dict_file_id": dict_file_id,
                "entry_count": len(entries),
                "preview": entries[:10],
                "save_path": save_path
            }
            return format_response(data, 200, "上传成功")
        except Exception as e:
            # 解析失败，删除文件
            try:
                os.remove(save_path)
            except Exception:
                pass
            return format_response(None, 400, f"解析失败：{str(e)}")


def parse_dict_file(file_path: str) -> list:
    """
    解析字典文件，提取字段注释

    期望格式：
    | 字段名 | 字段注释 | 字段类型（可选） |
    |--------|----------|------------------|
    | deleted | 删除标志 | int |
    | ...    | ...      | ... |

    返回：
    [
        {"column_name": "deleted", "column_comment": "删除标志", "column_type": "int"},
        ...
    ]
    """
    # 读取文件
    ext = Path(file_path).suffix.lower()
    if ext == ".xls":
        df = pd.read_excel(file_path, engine="xlrd")
    elif ext == ".xlsx":
        df = pd.read_excel(file_path, engine="openpyxl")
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式：{ext}")

    # 自动识别列名（支持中英文）
    col_map = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ["字段名", "column_name", "field_name", "column", "field"]:
            col_map["name"] = col
        elif col_lower in ["字段注释", "注释", "comment", "description", "desc"]:
            col_map["comment"] = col
        elif col_lower in ["字段类型", "类型", "type", "data_type"]:
            col_map["type"] = col

    if "name" not in col_map or "comment" not in col_map:
        raise ValueError("字典文件必须包含'字段名'和'字段注释'列")

    # 提取条目
    entries = []
    for _, row in df.iterrows():
        name = str(row[col_map["name"]]).strip()
        comment = str(row[col_map["comment"]]).strip()

        # 跳过空行
        if not name or not comment or name == "nan" or comment == "nan":
            continue

        entry = {
            "column_name": name,
            "column_comment": comment
        }

        # 可选：字段类型
        if "type" in col_map:
            col_type = str(row[col_map["type"]]).strip()
            if col_type and col_type != "nan":
                entry["column_type"] = col_type

        entries.append(entry)

    if not entries:
        raise ValueError("字典文件中没有有效的字段条目")

    return entries


api.add_resource(DictFileUploadAPI, "/dict/upload")
