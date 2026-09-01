import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional


def ensure_yploads_dir(current_file: str) -> str:
    """
    Resolve and ensure controllers/datasource/yploads directory exists,
    based on the current module file path.
    """
    _main_dir = os.path.dirname(os.path.abspath(current_file))
    _ds_dir = os.path.dirname(_main_dir)
    _yploads_dir = os.path.join(_ds_dir, "yploads")
    os.makedirs(_yploads_dir, exist_ok=True)
    return _yploads_dir


def _atomic_write_json(target_path: str, data: Dict[str, Any]) -> None:
    """
    Write JSON atomically to avoid partial files:
    - write to a temp file in the same directory
    - flush and fsync
    - os.replace to move into place
    """
    dir_name = os.path.dirname(target_path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Use default=str to serialize non-JSON-native types (e.g., UUID, datetime)
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    finally:
        # Best-effort cleanup if anything goes wrong before replace
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


def write_health_report(
    *,
    current_file: str,
    datasource_id: Optional[str],
    user_id: Optional[str],
    connect_info: Optional[str],
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Persist a health report JSON for a datasource atomically.

    Returns:
      The path to the written JSON file, or None if datasource_id is missing.
    """
    if not datasource_id:
        return None

    yploads_dir = ensure_yploads_dir(current_file)
    json_path = os.path.join(yploads_dir, f"{datasource_id}.json")

    # 可选：基于 after.problematic_tables 构建扁平的字段填充明细，便于直接查看
    enriched_after = after or {}
    try:
        problematic_tables = (enriched_after or {}).get("problematic_tables") or []
        if problematic_tables:
            tables_details = []
            for tbl in problematic_tables:
                table_name = (tbl or {}).get("table_name") or ""
                fill_result = (tbl or {}).get("fill_result") or {}

                # 将已填充字段拍平成 {字段名: 填充值} 的映射
                filled_map = {}
                for item in (fill_result.get("filled_fields") or []):
                    name = (item or {}).get("name")
                    comment = (item or {}).get("comment")
                    if name and comment is not None:
                        filled_map[name] = comment

                # 仍缺失字段的名称列表
                still_missing_names = [i.get("name") for i in (fill_result.get("still_missing_fields") or []) if i.get("name")]

                if table_name:
                    tables_details.append({
                        "table_name": table_name,
                        "filled_map": filled_map,                # 例如: {"name": "姓名"}
                        "still_missing_fields": still_missing_names
                    })

            # 放入一个清晰的明细区块
            if tables_details:
                enriched_after["detailed_fill"] = {
                    "tables": tables_details
                }
    except Exception:
        # 不因明细生成失败而影响主流程
        pass

    payload: Dict[str, Any] = {
        "datasource_id": str(datasource_id),
        "user_id": str(user_id) if user_id is not None else None,
        "connect_info": str(connect_info) if connect_info is not None else None,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "before": before or {},
        "after": enriched_after,
    }

    _atomic_write_json(json_path, payload)
    return json_path

