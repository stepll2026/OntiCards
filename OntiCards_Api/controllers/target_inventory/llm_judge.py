"""
 @File: llm_judge.py
 @Description: LLM 裁决：从 TopK 候选中生成推荐注释
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 16:00
"""

from __future__ import annotations
import json
import re
from controllers.agents.qwen.llm_utils import llm_call


def llm_judge_candidates(
    target_field: dict,      # {table, column, type}
    profile: dict,           # 画像信息
    topk_candidates: list,   # TopK 候选列表
    temperature: float = 0.3 # LLM 温度参数（低温度更确定性）
) -> dict:
    """
    LLM 裁决：从 TopK 候选中生成 1~3 条推荐注释

    参数：
        target_field: 目标字段信息 {table, column, type}
        profile: 画像信息 {type_hint, format_hint, null_rate_est, distinct_est, top_values, sample_values}
        topk_candidates: TopK 候选列表 [{table_name, column_name, column_comment, score, ...}]
        temperature: LLM 温度参数

    返回格式：
    {
        "candidates": [
            {
                "comment": "删除标志（0未删除/1已删除）",
                "confidence": 0.93,
                "source": "t_order.is_deleted",
                "reasoning": "字段名高度相似，取值画像完全匹配（0/1布尔值）"
            },
            ...
        ],
        "need_human_confirm": true,
        "llm_raw_response": "..."
    }
    """
    # 如果没有候选，直接返回
    if not topk_candidates:
        return {
            "candidates": [],
            "need_human_confirm": True,
            "llm_raw_response": "无候选注释"
        }

    # 构造 Prompt
    prompt = build_llm_prompt(target_field, profile, topk_candidates)

    # 调用 LLM
    try:
        llm_response = llm_call(prompt, temperature=temperature, timeout=120, retries=2)
    except Exception as e:
        print(f"[LLM 裁决] LLM 调用失败: {e}")
        # Fallback: 返回 top1
        return _fallback_to_top1(topk_candidates, llm_raw_response=f"LLM 调用失败: {e}")

    # 解析 LLM 返回的 JSON
    try:
        result = parse_llm_response(llm_response)
        result["llm_raw_response"] = llm_response
        return result
    except Exception as e:
        print(f"[LLM 裁决] 解析 LLM 响应失败: {e}")
        # Fallback: 返回 top1
        return _fallback_to_top1(topk_candidates, llm_raw_response=llm_response)


def build_llm_prompt(target_field: dict, profile: dict, topk_candidates: list) -> str:
    """
    构造结构化 Prompt
    """
    table_name = target_field.get("table", "")
    column_name = target_field.get("column", "")
    column_type = target_field.get("type", "")

    # 画像信息
    type_hint = profile.get("type_hint", "unknown")
    format_hint = profile.get("format_hint", "")
    null_rate = profile.get("null_rate_est", 0)
    distinct_count = profile.get("distinct_est", 0)
    top_values = profile.get("top_values", [])
    sample_values = profile.get("sample_values", [])

    # 格式化 top_values
    top_str = ", ".join([f"{v.get('v')}({v.get('cnt')}次)" for v in top_values[:5]])

    # 格式化样例值
    sample_str = ", ".join([str(v) for v in sample_values[:5]])

    # 格式化候选列表
    candidates_list = []
    for i, cand in enumerate(topk_candidates[:10], 1):  # 最多取前 10 个候选
        source_table = cand.get("table_name", "")
        source_column = cand.get("column_name", "")
        source_type = cand.get("source_type", "table_ref")
        comment = cand.get("column_comment", "")
        score = cand.get("score", 0.0)

        if source_type == "dict":
            source = f"dict:{source_column}"
        else:
            source = f"{source_table}.{source_column}"

        candidates_list.append(
            f"{i}. 来源：{source}\n"
            f"   注释：{comment}\n"
            f"   相似度：{score:.3f}"
        )

    candidates_text = "\n\n".join(candidates_list)

    # 构造 Prompt
    prompt = f"""你是一个数据库字段注释专家。请根据以下信息，为目标字段推荐最合适的注释。

## 目标字段信息
- 表名：{table_name}
- 字段名：{column_name}
- 字段类型：{column_type}

## 取值画像（客观证据）
- 类型提示：{type_hint}
- 格式提示：{format_hint if format_hint else "无"}
- 空值率：{null_rate:.2f}%
- 唯一值数：{distinct_count}
- Top 值分布：{top_str if top_str else "无"}
- 样例值：{sample_str if sample_str else "无"}（已脱敏）

## 候选注释（来自参考表和字典）
{candidates_text}

## 任务要求
1. 综合分析字段名、类型、取值画像和候选注释
2. 推荐 1~3 条最合适的注释（按置信度降序）
3. 每条注释必须包含：
   - comment：推荐的注释文本（简洁明了，16字以内）
   - confidence：置信度（0~1 的小数）
   - source：来源（表名.字段名 或 dict:xxx）
   - reasoning：推荐理由（简短说明，30字以内）

## 置信度判断标准
- >= 0.85：字段名高度相似 + 画像完全匹配
- 0.70~0.85：字段名相似 + 画像部分匹配
- 0.60~0.70：语义相近但存在歧义
- < 0.60：不确定，必须人工确认

## 输出格式（严格 JSON）
请严格按照以下 JSON 格式输出，不要添加任何其他文字：

{{
    "candidates": [
        {{
            "comment": "删除标志（0未删除/1已删除）",
            "confidence": 0.93,
            "source": "t_order.is_deleted",
            "reasoning": "字段名高度相似，取值画像完全匹配"
        }}
    ],
    "need_human_confirm": true
}}

请输出 JSON：
"""
    return prompt


def parse_llm_response(llm_response: str) -> dict:
    """
    解析 LLM 返回的 JSON（带容错处理）
    """
    # 清洗 LLM 返回的 Markdown 代码块
    cleaned = clean_llm_json_response(llm_response)

    # 解析 JSON
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")

    # 校验必需字段
    if "candidates" not in result:
        raise ValueError("缺少 candidates 字段")

    if not isinstance(result["candidates"], list):
        raise ValueError("candidates 必须是列表")

    # 校验每个候选
    for cand in result["candidates"]:
        if not isinstance(cand, dict):
            raise ValueError("候选必须是字典")

        required_fields = ["comment", "confidence", "source", "reasoning"]
        for field in required_fields:
            if field not in cand:
                raise ValueError(f"候选缺少 {field} 字段")

        # 置信度范围校验
        confidence = cand["confidence"]
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            raise ValueError(f"置信度必须在 0~1 之间: {confidence}")

    # 设置默认值
    if "need_human_confirm" not in result:
        # 如果最高置信度 < 0.85，强制人工确认
        max_confidence = max([c["confidence"] for c in result["candidates"]], default=0)
        result["need_human_confirm"] = max_confidence < 0.85

    return result


def clean_llm_json_response(response_str: str) -> str:
    """
    清洗 LLM 返回的 Markdown 代码块
    """
    # 去除首尾空白
    response_str = response_str.strip()

    # 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_str, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试提取纯 JSON（以 { 开头，} 结尾）
    match = re.search(r'(\{.*\})', response_str, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果都没有，直接返回原字符串
    return response_str


def _fallback_to_top1(topk_candidates: list, llm_raw_response: str = "") -> dict:
    """
    Fallback 策略：返回 top1 候选
    """
    if not topk_candidates:
        return {
            "candidates": [],
            "need_human_confirm": True,
            "llm_raw_response": llm_raw_response
        }

    top1 = topk_candidates[0]
    source_table = top1.get("table_name", "")
    source_column = top1.get("column_name", "")
    source_type = top1.get("source_type", "table_ref")

    if source_type == "dict":
        source = f"dict:{source_column}"
    else:
        source = f"{source_table}.{source_column}"

    # 基于 score 计算置信度（简单映射）
    score = float(top1.get("score", 0.0))
    confidence = min(0.9, score + 0.1)  # 最高 0.9

    return {
        "candidates": [
            {
                "comment": top1.get("column_comment", ""),
                "confidence": confidence,
                "source": source,
                "reasoning": "LLM 裁决失败，回退到 top1 候选"
            }
        ],
        "need_human_confirm": True,
        "llm_raw_response": llm_raw_response
    }
