"""Read only the bounded, structured system event store."""
from datetime import datetime, timedelta, timezone
import math

from flask import Blueprint, current_app, request
from flask_login import current_user, login_required
from werkzeug.exceptions import Unauthorized

from core.system_logs import EXTENSION_KEY


log_center_api = Blueprint("log_center_api", __name__)
LOCAL_TIMEZONE = timezone(timedelta(hours=8))


def _response(code, msg, data=None):
    return {"code": code, "msg": msg, "data": data}, code


def _date(value, *, end=False):
    if not value:
        return None
    if len(value) > 40:
        raise ValueError("日期格式无效")
    if len(value) == 10:
        # Date pickers use China calendar days; records remain UTC ISO timestamps.
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE)
        return (parsed + timedelta(days=1) if end else parsed).astimezone(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
    return parsed.astimezone(timezone.utc)


@log_center_api.errorhandler(Unauthorized)
def unauthorized(error):
    return _response(401, "请先登录")


@log_center_api.get("/system")
@login_required
def system_logs():
    if getattr(current_user, "role", None) != "admin":
        return _response(403, "仅管理员可查看系统日志")
    try:
        allowed = {"page", "page_size", "level", "keyword", "start_date", "end_date", "_token"}
        if any(key not in allowed for key in request.args):
            raise ValueError("不支持的查询参数")
        if any(len(request.args.getlist(key)) > 1 for key in request.args):
            raise ValueError("查询参数不能重复")
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
        if not 1 <= page <= 100000 or not 1 <= page_size <= 100:
            raise ValueError("page 必须为正整数，page_size 必须在 1 到 100 之间")
        level = request.args.get("level", "all")
        if level not in {"all", "INFO", "WARNING", "ERROR"}:
            raise ValueError("level 无效")
        keyword = request.args.get("keyword", "").strip()
        if len(keyword) > 200:
            raise ValueError("keyword 不能超过 200 个字符")
        start = _date(request.args.get("start_date", ""))
        end = _date(request.args.get("end_date", ""), end=True)
        if start is not None and end is not None and start >= end:
            raise ValueError("开始时间不能晚于结束时间")
    except (ValueError, OverflowError):
        return _response(400, "查询参数无效，请检查分页、级别、关键词和日期范围")
    store = current_app.extensions.get(EXTENSION_KEY)
    if store is None:
        return _response(503, "系统日志暂不可用")
    try:
        records, truncated = store.read()
        items = []
        for record in records:
            if level != "all" and record.get("level") != level:
                continue
            try:
                timestamp = _date(record.get("created_at", ""))
            except (ValueError, TypeError, OverflowError):
                continue
            if timestamp is None or (start is not None and timestamp < start) or (end is not None and timestamp >= end):
                continue
            haystack = " ".join(str(record.get(field) or "") for field in (
                "message", "event", "request_id", "method", "path", "status_code")).casefold()
            if keyword and keyword.casefold() not in haystack:
                continue
            items.append(record)
        total = len(items)
        offset = (page - 1) * page_size
        return _response(200, "success", {"items": items[offset:offset + page_size],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": math.ceil(total / page_size), "truncated": truncated})
    except Exception:
        return _response(503, "系统日志暂不可用，请稍后重试")
