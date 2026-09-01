"""
 @File: prompt_config.py
 @Description: 提示词配置模型 - 对应 prompt_config 表
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-06
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column, String, Text, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from extensions.ext_database import db
from models.utils import format_datetime


class PromptConfig(db.Model):
    """提示词配置表 - 存储系统中的提示词模板内容"""
    __tablename__ = "prompt_config"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )

    prompt = Column(
        Text,
        nullable=False,
        comment="提示词实际内容"
    )

    file_name = Column(
        String(255),
        nullable=False,
        comment="映射项目目录中的实际文件名"
    )

    description = Column(
        Text,
        nullable=True,
        comment="提示词作用描述"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        comment="创建时间"
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )

    def __repr__(self):
        return f"<PromptConfig file_name={self.file_name}>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "prompt": self.prompt,
            "file_name": self.file_name,
            "description": self.description,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


class PromptConfigManager:
    """
    提示词配置管理器

    提供统一的接口来管理提示词配置，支持：
    1. 从数据库读取（优先）
    2. 从文件读取（fallback）
    3. 同步文件内容到数据库
    4. 热更新（无需重启服务）
    """

    _instance = None
    _cache = {}  # 内存缓存 {file_name: prompt_content}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_prompt(self, file_name: str, use_cache: bool = True) -> Optional[str]:
        """
        获取提示词内容

        优先级：缓存 > 数据库 > 文件

        Args:
            file_name: 文件名（如 'data_audit_mysql.txt'）
            use_cache: 是否使用内存缓存（默认True，热更新时设为False）

        Returns:
            提示词内容，如果不存在返回 None
        """
        # 1. 检查缓存
        if use_cache and file_name in self._cache:
            return self._cache[file_name]

        # 2. 从数据库读取
        prompt_config = PromptConfig.query.filter_by(file_name=file_name).first()
        if prompt_config:
            self._cache[file_name] = prompt_config.prompt
            return prompt_config.prompt

        # 3. 从文件读取（回退）
        content = self._read_from_file(file_name)
        if content:
            # 自动同步到数据库
            self._sync_to_db(file_name, content)
            self._cache[file_name] = content
            return content

        return None

    def set_prompt(self, file_name: str, content: str, description: str = None) -> bool:
        """
        设置/更新提示词内容（写入数据库）

        Args:
            file_name: 文件名
            content: 提示词内容
            description: 描述（可选）

        Returns:
            True 成功，False 失败
        """
        try:
            from datetime import datetime
            prompt_config = PromptConfig.query.filter_by(file_name=file_name).first()

            if prompt_config:
                prompt_config.prompt = content
                prompt_config.updated_at = datetime.utcnow()
                if description:
                    prompt_config.description = description
            else:
                prompt_config = PromptConfig(
                    prompt=content,
                    file_name=file_name,
                    description=description
                )
                db.session.add(prompt_config)

            db.session.commit()

            # 更新缓存
            self._cache[file_name] = content
            return True

        except Exception as e:
            db.session.rollback()
            print(f"[PromptConfigManager] 更新失败: {e}")
            return False

    def delete_prompt(self, file_name: str) -> bool:
        """
        删除提示词配置

        Args:
            file_name: 文件名

        Returns:
            True 成功，False 失败
        """
        try:
            prompt_config = PromptConfig.query.filter_by(file_name=file_name).first()
            if prompt_config:
                db.session.delete(prompt_config)
                db.session.commit()

                # 清除缓存
                if file_name in self._cache:
                    del self._cache[file_name]

                return True
            return False

        except Exception as e:
            db.session.rollback()
            print(f"[PromptConfigManager] 删除失败: {e}")
            return False

    def list_prompts(self) -> List[dict]:
        """
        列出所有提示词配置

        Returns:
            提示词配置列表
        """
        configs = PromptConfig.query.all()
        return [c.to_dict() for c in configs]

    def sync_from_file(self, file_name: str, file_path: str = None, description: str = None) -> bool:
        """
        从文件同步内容到数据库

        Args:
            file_name: 数据库中的记录名
            file_path: 文件实际路径（如果为 None，则使用默认路径）
            description: 描述信息

        Returns:
            True 成功，False 失败
        """
        content = self._read_from_file(file_name, file_path)
        if content is None:
            return False

        return self.set_prompt(file_name, content, description)

    def sync_all_from_files(self, project_root: str = None) -> dict:
        """
        同步所有已知文件到数据库

        Args:
            project_root: 项目根目录路径（默认为 models/ 的父目录，即项目根目录）

        Returns:
            同步结果统计 {"success": [...], "failed": [...]}
        """
        from pathlib import Path

        if project_root is None:
            # 模型文件在 OntiCards_Api/models/ 下，所以 parent 是项目根目录
            project_root = Path(__file__).resolve().parent.parent

        # 查找 libs 目录
        # 优先查找项目根目录下 (项目/libs/)
        # 如果不存在，尝试项目父目录下 (../libs/)
        libs_candidates = [
            Path(project_root) / "libs",
            Path(project_root).parent / "libs",
        ]

        libs_dir = None
        for candidate in libs_candidates:
            if candidate.exists() and candidate.is_dir():
                libs_dir = candidate
                break

        if libs_dir is None:
            print(f"[PromptConfigManager] 错误: 未找到 libs 目录")
            print(f"  尝试过的位置:")
            for candidate in libs_candidates:
                print(f"    - {candidate}")
            return {"success": [], "failed": ["libs 目录未找到"]}

        results = {"success": [], "failed": []}

        # 定义需要同步的文件映射 (数据库名: 相对于 libs 目录的路径)
        files_to_sync = {
            # DDL SQL 文件
            "data_audit_postgre.txt": "data_audit_ddl_sql/data_audit_postgre.txt",
            "data_audit_mysql.txt": "data_audit_ddl_sql/data_audit_mysql.txt",
            "data_audit_mssql.txt": "data_audit_ddl_sql/data_audit_mssql.txt",
            "data_audit_oracle.txt": "data_audit_ddl_sql/data_audit_oracle.txt",
            "data_audit_sqlite.txt": "data_audit_ddl_sql/data_audit_sqlite.txt",
            "data_audit_trino.txt": "data_audit_ddl_sql/data_audit_trino.txt",
            # 人大金仓（KingBase）- 使用独立的 DDL SQL 文件（基于 PostgreSQL）
            "data_audit_kingbase.txt": "data_audit_ddl_sql/data_audit_kingbase.txt",
            # OceanBase MySQL 模式租户：使用独立的 DDL SQL（去掉了 DROP PROCEDURE）
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
            # OceanBase MySQL 模式租户：使用独立的提示词文件（当前内容基于 MySQL 模板）
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
            "report_basic_audit_chunk.txt": "质检报告-基础空值检测板块生成提示词",
            "report_relation_chunk.txt": "质检报告-表关系发现板块生成提示词",
            "report_quality_chunk.txt": "质检报告-规则库质检板块生成提示词",
            "report_overall_summary_chunk.txt": "质检报告-综合总结章节生成提示词",
            "report_chunk_prompt.txt": "质检报告-分块生成通用提示词模板",
            # DataCard 数据卡片生成提示词
            "datacard_generate_prompt.txt": "数据卡片生成提示词",
        }

        for db_name, relative_path in files_to_sync.items():
            file_path = libs_dir / relative_path
            if file_path.exists():
                if self.sync_from_file(db_name, str(file_path), descriptions.get(db_name, "")):
                    results["success"].append(db_name)
                else:
                    results["failed"].append(db_name)
            else:
                results["failed"].append(f"{db_name} (文件不存在: {file_path})")

        return results

    def clear_cache(self):
        """清除内存缓存"""
        self._cache.clear()

    def invalidate_cache(self, file_name: str = None):
        """
        使缓存失效

        Args:
            file_name: 如果指定，只清除该文件的缓存；否则清除全部
        """
        if file_name:
            if file_name in self._cache:
                del self._cache[file_name]
        else:
            self._cache.clear()

    def _read_from_file(self, file_name: str, file_path: str = None) -> Optional[str]:
        """
        从文件读取内容

        Args:
            file_name: 文件名
            file_path: 完整文件路径（可选）

        Returns:
            文件内容，读取失败返回 None
        """
        try:
            if file_path:
                path = Path(file_path)
            else:
                # 根据 file_name 推断默认路径
                path = self._get_default_path(file_name)

            if path and path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[PromptConfigManager] 读取文件失败 {file_name}: {e}")

        return None

    def _get_default_path(self, file_name: str) -> Path:
        """根据文件名推断默认路径"""
        root_dir = Path(__file__).resolve().parents[2]

        # 路径映射
        path_mappings = {
            # DDL SQL
            "data_audit_postgre.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_postgre.txt",
            "data_audit_mysql.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_mysql.txt",
            "data_audit_mssql.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_mssql.txt",
            "data_audit_oracle.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_oracle.txt",
            "data_audit_sqlite.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_sqlite.txt",
            "data_audit_trino.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_trino.txt",
            # 人大金仓（KingBase）- 使用独立的 DDL SQL 文件
            "data_audit_kingbase.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_kingbase.txt",
            # OceanBase MySQL 模式租户：使用独立的 DDL SQL
            "data_audit_oceanbase.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_oceanbase.txt",
            # 达梦 DM：使用独立的 DDL SQL
            "data_audit_dm.txt": root_dir / "libs" / "data_audit_ddl_sql" / "data_audit_dm.txt",
            # Query 提示词
            "postgresql_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "postgresql_multi_table.txt",
            "oracle_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "oracle_multi_table.txt",
            "mssql_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "mssql_multi_table.txt",
            "mysql_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "mysql_multi_table.txt",
            "sqlite_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "sqlite_multi_table.txt",
            "trino_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "trino_multi_table.txt",
            # 人大金仓（KingBase）- 使用独立的提示词文件
            "kingbase_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "kingbase_multi_table.txt",
            # OceanBase MySQL 模式租户：使用独立的提示词文件
            "oceanbase_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "oceanbase_multi_table.txt",
            # 达梦 DM：使用独立的提示词文件
            "dm_multi_table.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "dm_multi_table.txt",
            "strategy_detect.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "strategy_detect.txt",
            "sql_with_relationship.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "sql_with_relationship.txt",
            "result_fusion.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "result_fusion.txt",
            "retry_whitelist_error.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "retry_whitelist_error.txt",
            "retry_execution_error.txt": root_dir / "libs" / "prompt" / "query_agg_prompt" / "retry_execution_error.txt",
            # Global Inventory
            "table_relationship_analysis_prompt.txt": root_dir / "libs" / "prompt" / "global_inventory" / "table_relationship_analysis_prompt.txt",
            "table_relationship_analysis_enhanced_prompt.txt": root_dir / "libs" / "prompt" / "global_inventory" / "table_relationship_analysis_enhanced_prompt.txt",
            # Fill Field
            "fill_field_by_llm.txt": root_dir / "libs" / "prompt" / "fill_field_by_llm.txt",
            # Governance 提示词（reports_generate 目录下的新版提示词）
            "report_summary_prompt.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_summary_prompt.txt",
            "dialect_adaptation_prompt.txt": root_dir / "libs" / "prompt" / "governance" / "dialect_adaptation_prompt.txt",
            "report_dynamic_prompt.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_dynamic_prompt.txt",
            "rule_parsing_prompt.txt": root_dir / "libs" / "prompt" / "governance" / "rule_parsing_prompt.txt",
            # Governance 报告分块提示词
            "report_basic_audit_chunk.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_basic_audit_chunk.txt",
            "report_relation_chunk.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_relation_chunk.txt",
            "report_quality_chunk.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_quality_chunk.txt",
            "report_overall_summary_chunk.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_overall_summary_chunk.txt",
            "report_chunk_prompt.txt": root_dir / "libs" / "prompt" / "governance" / "reports_generate" / "report_chunk_prompt.txt",
            # DataCard 数据卡片生成提示词
            "datacard_generate_prompt.txt": root_dir / "libs" / "prompt" / "datacard_generate" / "datacard_generate_prompt.txt",
        }

        return path_mappings.get(file_name)

    def _sync_to_db(self, file_name: str, content: str):
        """同步内容到数据库"""
        self.set_prompt(file_name, content)


# 全局单例
prompt_manager = PromptConfigManager()
