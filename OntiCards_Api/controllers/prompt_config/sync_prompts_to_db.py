"""
 @File: sync_prompts_to_db.py
 @Description: 同步提示词文件到数据库工具
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-06

 使用方法:
 1. 在 Flask 应用上下文中运行:
    from app import app
    from scripts.sync_prompts_to_db import sync_all_prompts
    with app.app_context():
        result = sync_all_prompts()
        print(result)

 2. 或者作为独立脚本运行:
    python scripts/sync_prompts_to_db.py
"""

from __future__ import annotations

import sys
import os

# 确保可以导入项目模块
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def sync_all_prompts(project_root: str = None) -> dict:
    """
    同步所有提示词文件到数据库

    Args:
        project_root: 项目根目录路径（默认为脚本所在目录的父目录）

    Returns:
        同步结果统计 {"success": [...], "failed": [...], "total": int}
    """
    from pathlib import Path

    from extensions.ext_database import db
    from models.prompt_config import PromptConfig

    if project_root is None:
        # 脚本在 scripts/ 目录下，所以 parent 是项目根目录
        project_root = Path(script_dir).parent

    # 查找 libs 目录
    # 优先查找项目根目录下 (项目/libs/)
    # 如果不存在，尝试项目父目录下 (../libs/)
    libs_candidates = [
        Path(project_root) / "libs",           # 项目根目录下的 libs
        Path(project_root).parent / "libs",     # 项目父目录下的 libs
    ]

    libs_dir = None
    for candidate in libs_candidates:
        if candidate.exists() and candidate.is_dir():
            libs_dir = candidate
            break

    if libs_dir is None:
        print(f"[SYNC] 错误: 未找到 libs 目录")
        print(f"  尝试过的位置:")
        for candidate in libs_candidates:
            print(f"    - {candidate}")
        return {"success": [], "failed": ["libs 目录未找到"], "total": 0}

    results = {"success": [], "failed": [], "total": 0}

    # 定义需要同步的文件映射 (数据库名: 相对于 libs 目录的路径)
    files_to_sync = {
        # DDL SQL 文件
        "data_audit_postgre.txt": "data_audit_ddl_sql/data_audit_postgre.txt",
        "data_audit_mysql.txt": "data_audit_ddl_sql/data_audit_mysql.txt",
        "data_audit_mssql.txt": "data_audit_ddl_sql/data_audit_mssql.txt",
        "data_audit_oracle.txt": "data_audit_ddl_sql/data_audit_oracle.txt",
        "data_audit_sqlite.txt": "data_audit_ddl_sql/data_audit_sqlite.txt",
        "data_audit_trino.txt": "data_audit_ddl_sql/data_audit_trino.txt",
        # 人大金仓（KingBase）- 使用独立的 DDL SQL 文件
        "data_audit_kingbase.txt": "data_audit_ddl_sql/data_audit_kingbase.txt",
        # OceanBase MySQL 模式租户：使用独立的 DDL SQL
        "data_audit_oceanbase.txt": "data_audit_ddl_sql/data_audit_oceanbase.txt",
        # 达梦 DM：使用独立的 DDL SQL（基于 Oracle 语法）
        "data_audit_dm.txt": "data_audit_ddl_sql/data_audit_dm.txt",
        # Query 提示词
        "postgresql_multi_table.txt": "prompt/query_agg_prompt/postgresql_multi_table.txt",
        "oracle_multi_table.txt": "prompt/query_agg_prompt/oracle_multi_table.txt",
        "mssql_multi_table.txt": "prompt/query_agg_prompt/mssql_multi_table.txt",
        "mysql_multi_table.txt": "prompt/query_agg_prompt/mysql_multi_table.txt",
        "sqlite_multi_table.txt": "prompt/query_agg_prompt/sqlite_multi_table.txt",
        "trino_multi_table.txt": "prompt/query_agg_prompt/trino_multi_table.txt",
        # 人大金仓（KingBase）- 使用独立的提示词文件
        "kingbase_multi_table.txt": "prompt/query_agg_prompt/kingbase_multi_table.txt",
        # OceanBase MySQL 模式租户：使用独立的提示词文件
        "oceanbase_multi_table.txt": "prompt/query_agg_prompt/oceanbase_multi_table.txt",
        # 达梦 DM：使用独立的提示词文件（基于 Oracle 模板）
        "dm_multi_table.txt": "prompt/query_agg_prompt/dm_multi_table.txt",
        "strategy_detect.txt": "prompt/query_agg_prompt/strategy_detect.txt",
        "sql_with_relationship.txt": "prompt/query_agg_prompt/sql_with_relationship.txt",
        "result_fusion.txt": "prompt/query_agg_prompt/result_fusion.txt",
        "retry_whitelist_error.txt": "prompt/query_agg_prompt/retry_whitelist_error.txt",
        "retry_execution_error.txt": "prompt/query_agg_prompt/retry_execution_error.txt",
        # Global Inventory 提示词
        "table_relationship_analysis_prompt.txt": "prompt/global_inventory/table_relationship_analysis_prompt.txt",
        "table_relationship_analysis_enhanced_prompt.txt": "prompt/global_inventory/table_relationship_analysis_enhanced_prompt.txt",
        # Fill Field 提示词
        "fill_field_by_llm.txt": "prompt/fill_field_by_llm.txt",
        # Governance 提示词（reports_generate 目录下的新版提示词）
        "report_summary_prompt.txt": "prompt/governance/reports_generate/report_summary_prompt.txt",
        "dialect_adaptation_prompt.txt": "prompt/governance/dialect_adaptation_prompt.txt",
        "report_dynamic_prompt.txt": "prompt/governance/reports_generate/report_dynamic_prompt.txt",
        "rule_parsing_prompt.txt": "prompt/governance/rule_parsing_prompt.txt",
        # Governance 报告分块提示词
        "report_basic_audit_chunk.txt": "prompt/governance/reports_generate/report_basic_audit_chunk.txt",
        "report_relation_chunk.txt": "prompt/governance/reports_generate/report_relation_chunk.txt",
        "report_quality_chunk.txt": "prompt/governance/reports_generate/report_quality_chunk.txt",
        "report_overall_summary_chunk.txt": "prompt/governance/reports_generate/report_overall_summary_chunk.txt",
        "report_chunk_prompt.txt": "prompt/governance/reports_generate/report_chunk_prompt.txt",
        # DataCard 数据卡片生成提示词
        "datacard_generate_prompt.txt": "prompt/datacard_generate/datacard_generate_prompt.txt",
        "datacard_sample_prompt.txt": "prompt/datacard_generate/datacard_sample_prompt.txt",
    }

    # 描述信息映射
    descriptions = {
        "data_audit_postgre.txt": "PostgreSQL 数据盘查 DDL SQL",
        "data_audit_mysql.txt": "MySQL 数据盘查 DDL SQL",
        "data_audit_mssql.txt": "SQL Server 数据盘查 DDL SQL",
        "data_audit_oracle.txt": "Oracle 数据盘查 DDL SQL",
        "data_audit_sqlite.txt": "SQLite 数据盘查模板 SQL",
        "data_audit_trino.txt": "Trino 数据盘查模板 SQL",
        # 人大金仓（KingBase）- 使用独立的 DDL SQL 文件
        "data_audit_kingbase.txt": "人大金仓 KingBase 数据盘查 DDL SQL",
        # OceanBase MySQL 模式租户：使用独立的 DDL SQL
        "data_audit_oceanbase.txt": "OceanBase MySQL 模式 数据盘查 DDL SQL",
        # 达梦 DM：使用独立的 DDL SQL
        "data_audit_dm.txt": "达梦 DM 数据盘查 DDL SQL",
        "postgresql_multi_table.txt": "PostgreSQL 多表查询SQL生成 提示词",
        "oracle_multi_table.txt": "Oracle 多表查询SQL生成 提示词",
        "mssql_multi_table.txt": "SQL Server 多表查询SQL生成 提示词",
        "mysql_multi_table.txt": "MySQL 多表查询SQL生成 提示词",
        "sqlite_multi_table.txt": "SQLite 多表查询SQL生成 提示词",
        "trino_multi_table.txt": "Trino 多表查询SQL生成 提示词",
        # 人大金仓（KingBase）- 使用独立的提示词文件
        "kingbase_multi_table.txt": "人大金仓 KingBase 多表查询SQL生成 提示词",
        # OceanBase MySQL 模式租户：使用独立的提示词文件
        "oceanbase_multi_table.txt": "OceanBase MySQL 模式 多表查询SQL生成 提示词",
        # 达梦 DM：使用独立的提示词文件
        "dm_multi_table.txt": "达梦 DM 多表查询SQL生成 提示词",
        "strategy_detect.txt": "查询策略检测提示词",
        "sql_with_relationship.txt": "关联查询 SQL生成 提示词",
        "result_fusion.txt": "结果融合提示词",
        "retry_whitelist_error.txt": "SQL白名单错误重试提示词",
        "retry_execution_error.txt": "SQL执行错误重试提示词",
        "table_relationship_analysis_prompt.txt": "表关系分析提示词（基础版）",
        "table_relationship_analysis_enhanced_prompt.txt": "表关系分析提示词（增强版）",
        "fill_field_by_llm.txt": "LLM 字段描述填充提示词",
        "report_summary_prompt.txt": "报告摘要生成提示词（reports_generate版）",
        "dialect_adaptation_prompt.txt": "SQL 方言适配提示词",
        "report_dynamic_prompt.txt": "报告动态生成提示词（reports_generate版）",
        "rule_parsing_prompt.txt": "自然语言规则解析提示词",
        # Governance 报告分块提示词
        "report_basic_audit_chunk.txt": "报告基础空值检测板块生成提示词",
        "report_relation_chunk.txt": "报告表关系发现板块生成提示词",
        "report_quality_chunk.txt": "报告规则库质检板块生成提示词",
        "report_overall_summary_chunk.txt": "报告综合总结章节生成提示词",
        "report_chunk_prompt.txt": "报告分块生成通用提示词模板",
        # DataCard 数据卡片生成提示词
        "datacard_generate_prompt.txt": "数据卡片生成提示词",
        "datacard_sample_prompt.txt": "数据采样脱敏分析提示词",
    }

    for db_name, relative_path in files_to_sync.items():
        file_path = libs_dir / relative_path
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 写入数据库
                config = PromptConfig.query.filter_by(file_name=db_name).first()
                if config:
                    config.prompt = content
                    config.description = descriptions.get(db_name, "")
                else:
                    config = PromptConfig(
                        prompt=content,
                        file_name=db_name,
                        description=descriptions.get(db_name, "")
                    )
                    db.session.add(config)

                db.session.commit()
                results["success"].append(db_name)
                print(f"[SYNC] OK: {db_name}")

            except Exception as e:
                db.session.rollback()
                results["failed"].append(f"{db_name} ({str(e)})")
                print(f"[SYNC] ERROR: {db_name} - {e}")
        else:
            results["failed"].append(f"{db_name} (文件不存在: {file_path})")
            print(f"[SYNC] SKIP: {db_name} (文件不存在)")

    results["total"] = len(files_to_sync)
    return results


def list_db_prompts() -> list:
    """列出数据库中所有提示词"""
    from models.prompt_config import PromptConfig

    configs = PromptConfig.query.all()
    return [c.to_dict() for c in configs]


def clear_all_prompts() -> int:
    """清空所有提示词配置（谨慎使用）"""
    from extensions.ext_database import db
    from models.prompt_config import PromptConfig

    count = PromptConfig.query.delete()
    db.session.commit()
    return count


def export_to_file(db_name: str, file_path: str) -> bool:
    """导出数据库中的提示词到文件"""
    from models.prompt_config import PromptConfig

    config = PromptConfig.query.filter_by(file_name=db_name).first()
    if not config:
        print(f"[EXPORT] 未找到提示词: {db_name}")
        return False

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(config.prompt)
        print(f"[EXPORT] OK: {db_name} -> {file_path}")
        return True
    except Exception as e:
        print(f"[EXPORT] ERROR: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("提示词同步工具")
    print("=" * 60)

    # 尝试加载 Flask 应用上下文
    try:
        from app import app
        from extensions import ext_database

        with app.app_context():
            # 确保数据库连接正常
            from sqlalchemy import text
            ext_database.db.session.execute(text("SELECT 1"))

            print("\n[1] 同步所有提示词到数据库")
            print("[2] 列出数据库中的提示词")
            print("[3] 清空所有提示词（谨慎）")
            print("[4] 退出")
            print("-" * 60)

            choice = input("请选择操作 [1]: ").strip() or "1"

            if choice == "1":
                print("\n开始同步...")
                result = sync_all_prompts()
                print("\n" + "=" * 60)
                print(f"同步完成！成功: {len(result['success'])}, 失败: {len(result['failed'])}, 总计: {result['total']}")
                if result['failed']:
                    print("\n失败列表:")
                    for f in result['failed']:
                        print(f"  - {f}")
            elif choice == "2":
                print("\n数据库中的提示词:")
                prompts = list_db_prompts()
                for p in prompts:
                    print(f"  - {p['file_name']}: {len(p.get('prompt', ''))} 字符")
            elif choice == "3":
                confirm = input("确定要清空所有提示词吗？此操作不可恢复 [y/N]: ").strip().lower()
                if confirm == "y":
                    count = clear_all_prompts()
                    print(f"已清空 {count} 条提示词")
                else:
                    print("已取消")
            else:
                print("退出")

    except ImportError as e:
        print(f"无法导入 Flask 应用: {e}")
        print("请在 Flask 应用上下文中运行 sync_all_prompts() 函数")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
