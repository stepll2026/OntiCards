"""
 @File: term_recognizer.py
 @Description: 术语识别与展开模块 - 用于NL2SQL查询链路中的业务术语识别
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14
 @Update: 2026-05-14 重构：支持按术语库查询，移除 datasource_id 关联
 @Update: 2026-05-14 新增：支持根据 datasource_id 获取已启用的术语库

 功能：
 1. 术语识别：在用户问题中识别业务术语
 2. 术语展开：将识别到的术语替换为详细定义
 3. 数据源关联：根据 datasource_id 获取已添加并启用的术语库
"""

import json
from typing import List, Dict, Optional
from models.business_terms import BusinessTerm
from models.business_term_libraries import BusinessTermLibrary
from models.datasource_term_library import DatasourceTermLibrary


def get_enabled_library_ids_by_datasource(datasource_id: str) -> List[str]:
    """
    根据数据源ID获取已添加并启用的术语库ID列表

    Args:
        datasource_id: 数据源ID

    Returns:
        已启用术语库的ID列表
    """
    if not datasource_id:
        return []

    enabled_links = DatasourceTermLibrary.query.join(
        BusinessTermLibrary,
        DatasourceTermLibrary.library_id == BusinessTermLibrary.id
    ).filter(
        DatasourceTermLibrary.datasource_id == datasource_id,
        DatasourceTermLibrary.is_enabled == True,
        BusinessTermLibrary.status == "active"
    ).all()

    return [str(link.library_id) for link in enabled_links]


def recognize_terms_by_library_ids(question: str, library_ids: List[str]) -> List[Dict]:
    """
    术语识别（按库ID列表）

    Args:
        question: 用户原始问题
        library_ids: 术语库ID列表（可指定多个库）

    Returns:
        匹配到的术语列表
    """
    if not library_ids:
        return []

    terms = BusinessTerm.query.filter(
        BusinessTerm.library_id.in_(library_ids),
        BusinessTerm.status == "active",
        BusinessTermLibrary.status == "active"
    ).join(
        BusinessTermLibrary,
        BusinessTerm.library_id == BusinessTermLibrary.id
    ).all()

    matched_terms = []
    for term in terms:
        names_to_match = [term.term_name] + term.get_term_alias_list()
        for name in names_to_match:
            if name in question or name.lower() in question.lower():
                matched_terms.append({
                    "term_name": term.term_name,
                    "term_definition": term.term_definition,
                    "related_fields": term.get_related_fields_list(),
                    "related_datacards": term.get_related_datacards_list(),
                    "matched_name": name,
                    "term_id": str(term.id),
                    "library_id": str(term.library_id),
                    "library_name": term.library.name if term.library else None
                })
                break

    return matched_terms


def recognize_all_active_terms(question: str) -> List[Dict]:
    """
    术语识别（查询所有启用的术语）

    Args:
        question: 用户原始问题

    Returns:
        匹配到的术语列表
    """
    terms = BusinessTerm.query.filter(
        BusinessTerm.status == "active",
        BusinessTermLibrary.status == "active"
    ).join(
        BusinessTermLibrary,
        BusinessTerm.library_id == BusinessTermLibrary.id
    ).all()

    matched_terms = []
    for term in terms:
        names_to_match = [term.term_name] + term.get_term_alias_list()
        for name in names_to_match:
            if name in question or name.lower() in question.lower():
                matched_terms.append({
                    "term_name": term.term_name,
                    "term_definition": term.term_definition,
                    "related_fields": term.get_related_fields_list(),
                    "related_datacards": term.get_related_datacards_list(),
                    "matched_name": name,
                    "term_id": str(term.id),
                    "library_id": str(term.library_id),
                    "library_name": term.library.name if term.library else None
                })
                break

    return matched_terms


def rewrite_question(question: str, matched_terms: List[Dict]) -> str:
    """
    问题转写：将术语替换为展开后的详细描述

    Args:
        question: 原始问题
        matched_terms: 识别到的术语列表

    Returns:
        转写后的新问题
    """
    rewritten = question
    for term in matched_terms:
        definition = term["term_definition"]
        matched_name = term["matched_name"]
        related_fields = term.get("related_fields", [])
        related_datacards = term.get("related_datacards", [])

        # 构建增强的定义信息
        enhanced_definition = f"（{definition}）"

        # 如果有关联字段，添加字段提示
        if related_fields:
            fields_hint = ", ".join([
                f"{f.get('table', '')}.{f.get('field', '')}"
                for f in related_fields
                if f.get('table') and f.get('field')
            ])
            if fields_hint:
                enhanced_definition = f"（{definition}，关联字段：{fields_hint}）"

        # 如果有关联数据卡片，添加数据卡片提示
        if related_datacards:
            cards_hint = ", ".join([
                f"数据表：{c.get('name', '')}"
                for c in related_datacards
                if c.get('name')
            ])
            if cards_hint:
                enhanced_definition = enhanced_definition.rstrip("）") + f"，关联表：{cards_hint}）"

        rewritten = rewritten.replace(matched_name, enhanced_definition)

    return rewritten


def process_question_by_libraries(question: str, library_ids: List[str]) -> tuple:
    """
    处理用户问题：按指定库识别术语并转写

    Args:
        question: 用户原始问题
        library_ids: 术语库ID列表

    Returns:
        (转写后的问题, 识别到的术语列表, 是否进行了转写)
    """
    matched_terms = recognize_terms_by_library_ids(question, library_ids)

    if not matched_terms:
        return question, [], False

    rewritten = rewrite_question(question, matched_terms)
    return rewritten, matched_terms, True


def process_question(question: str) -> tuple:
    """
    处理用户问题：识别所有启用术语并转写

    Args:
        question: 用户原始问题

    Returns:
        (转写后的问题, 识别到的术语列表, 是否进行了转写)
    """
    matched_terms = recognize_all_active_terms(question)

    if not matched_terms:
        return question, [], False

    rewritten = rewrite_question(question, matched_terms)
    return rewritten, matched_terms, True
