"""
 @File: sql_prompt_loader.py
 @Description: 提示词读取/插值工具
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-27 14:56
 @Update: 2026-05-06 - 改为优先从数据库读取，fallback到文件
"""

# -*- coding: utf-8 -*-
from pathlib import Path

# 以该文件为基准定位项目根目录（controllers/query -> controllers -> 项目根）
_ROOT_DIR = Path(__file__).resolve().parents[2]
PROMPTS_DIR = _ROOT_DIR / "libs" / "prompt" / "query_agg_prompt"

# 导入提示词配置管理器
from models.prompt_config import prompt_manager


def load_prompt(filename: str) -> str:
    """
    加载提示词文件

    优先级：数据库 > 缓存 > 文件

    Args:
        filename: 提示词文件名（如 'mysql_multi_table.txt'）

    Returns:
        提示词内容字符串

    Raises:
        FileNotFoundError: 当提示词不存在时抛出
    """
    # 1. 优先从数据库/缓存读取
    content = prompt_manager.get_prompt(filename)
    if content:
        return content

    # 2. Fallback 到文件读取（并自动同步到数据库）
    path = PROMPTS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 同步到数据库
        prompt_manager.set_prompt(filename, content)
        return content

    raise FileNotFoundError(f"未找到提示词文件: {filename}")


def render_prompt(tpl: str, **kwargs) -> str:
    """渲染提示词模板，替换占位符 {{key}}"""
    out = tpl
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out

