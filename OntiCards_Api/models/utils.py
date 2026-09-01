"""
@File: utils.py
@Description: 模型通用工具函数
@Author: 韩小豪 849631113@qq.com
@Create: 2026-07-31
"""


def format_datetime(value):
    """
    安全格式化时间字段，支持 datetime 对象或字符串

    @param value: datetime 对象、字符串或 None
    @return: ISO 格式字符串或 None
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)
