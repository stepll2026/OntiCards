"""
@File: audit_executor.py
@Description: 规则执行引擎 - 执行治理规则并生成结果
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
@Update: 2026-06-02 - 集成方言适配层，支持多数据库类型

核心能力：
1. 基于方言适配器生成跨数据库兼容的 SQL
2. 支持自然语言规则解析（LLM）
3. 多表批量执行模式
4. 规则执行结果聚合
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text
from sqlalchemy.engine import Engine

from extensions.ext_database import db
from models.governance_rule import GovernanceRule
from models.governance_report import GovernanceReport
from models.rule_execution_result import RuleExecutionResult
from controllers.governance.dialect_adapter import DialectAdapter


# ========== JSON 序列化辅助 ==========

def _sanitize_for_json(obj: Any) -> Any:
    """递归地将对象转换为可 JSON 序列化的纯 Python 类型

    用于 SQLAlchemy JSONB 字段写入前的安全转换，处理以下不可序列化类型：
    - datetime / date → ISO 格式字符串
    - UUID → 字符串
    - Decimal → float（保留精度）
    - bytes → UTF-8 解码字符串（失败时回退 base64）
    - set / tuple → list
    - 自定义对象 → 仅保留 __dict__ 中可序列化字段，否则转为 str

    Args:
        obj: 任意 Python 对象

    Returns:
        可 JSON 序列化的对象
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        # datetime/date → ISO 格式字符串
        return obj.isoformat()

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, Decimal):
        # Decimal 转为 float，特殊值（NaN/Inf）转为字符串避免 JSON 报错
        try:
            f = float(obj)
            if f != f or f in (float('inf'), float('-inf')):
                return str(obj)
            return f
        except Exception:
            return str(obj)

    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except Exception:
            import base64
            return base64.b64encode(obj).decode('ascii')

    if isinstance(obj, dict):
        return {str(_sanitize_for_json(k)): _sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_sanitize_for_json(item) for item in obj]

    # 其他自定义对象：尝试转字符串
    try:
        return str(obj)
    except Exception:
        return None


# ========== SQL 执行异常友好提示 ==========

def _get_friendly_sql_error_message(e: Exception, rule: GovernanceRule = None) -> str:
    """将 SQL 执行异常转换为面向用户的友好中文提示

    Args:
        e: 捕获的原始异常
        rule: 当前执行的规则（可选，用于补充上下文）

    Returns:
        友好的中文提示字符串
    """
    err_msg = str(e)
    err_lower = err_msg.lower()

    # ---- 1. 表 / 视图 / 关系不存在 ----
    if 'does not exist' in err_lower:
        m = re.search(r'relation "?([^"]+?)"? does not exist', err_lower)
        if not m:
            m = re.search(r"table '?([^']+?)'? doesn't exist", err_lower)
        if not m:
            m = re.search(r"table '?([^']+?)'? does not exist", err_lower)
        table_name = m.group(1) if m else None
        hint = f"执行失败，目标表 '{table_name}' 不存在。" if table_name else "执行失败，目标表不存在。"
        hint += " 请检查表名和 schema 是否正确，或确认该表是否已导入。"
        return hint

    # ---- 2. 列不存在 ----
    if 'column' in err_lower and ('does not exist' in err_lower or 'was not found' in err_lower):
        m = re.search(r'column "?([^"]+?)"? (?:does not exist|was not found)', err_lower)
        if not m:
            m = re.search(r"column '?([^']+?)'? (?:does not exist|was not found)", err_lower)
        col_name = m.group(1) if m else None
        hint = f"执行失败，列 '{col_name}' 不存在。" if col_name else "执行失败，目标列不存在。"
        hint += " 请检查列名是否正确，或确认该字段是否存在于目标表中。"
        return hint

    # ---- 3. 除零错误 ----
    if 'division by zero' in err_lower or 'divide by zero' in err_lower:
        return ("执行失败，检测 SQL 存在除零运算。"
                " 可能是分母为零（如某列全部为 0 导致除零），请检查阈值规则配置或目标列数据。")

    # ---- 4. SQL 语法错误 ----
    if 'syntax error' in err_lower or 'you have an error in your sql syntax' in err_lower:
        return ("执行失败，检测 SQL 存在语法错误。"
                " 请检查规则条件表达式配置是否正确。")

    # ---- 5. 类型转换错误 ----
    if ('invalid input syntax' in err_lower or 'cannot cast' in err_lower
            or 'incorrect integer' in err_lower or 'incorrect decimal' in err_lower):
        return ("执行失败，数据类型转换失败。"
                " 请检查规则条件中字段的值类型是否与目标列类型匹配。")

    # ---- 6. 执行超时 ----
    if 'canceling statement due to statement timeout' in err_lower:
        return ("执行失败，SQL 执行超时。"
                " 目标表数据量较大，建议优化规则条件或减少扫描范围。")

    # ---- 7. 权限不足 ----
    if 'permission denied for' in err_lower or 'row-level security policy' in err_lower:
        return ("执行失败，数据库权限不足，无法访问目标表或视图。"
                " 请联系数据库管理员授予相应权限。")

    # ---- 8. 数值溢出 ----
    if 'overflow' in err_lower or 'numeric value out of range' in err_lower:
        return ("执行失败，数值计算结果超出数据库允许范围。"
                " 请检查规则配置中的阈值或条件表达式是否合理。")

    # ---- 9. 违反约束（如外键、唯一约束检查时目标表无权限）----
    if 'violation' in err_lower or 'constraint' in err_lower:
        return ("执行失败，违反数据库约束。"
                " 请检查规则条件表达式配置是否合理。")

    # ---- 兜底 ----
    if len(err_msg) > 60:
        return "执行失败，发生未知错误，请检查规则配置或联系管理员。"
    return f"执行失败：{err_msg}"


class RuleExecutor:
    """规则执行引擎"""

    def __init__(self, engine: Engine, db_type: str, db_name: str, schema_name: str = None):
        """初始化执行引擎

        Args:
            engine: SQLAlchemy Engine 对象
            db_type: 数据库类型 (postgresql/mysql/mssql/oracle/sqlite/trino)
            db_name: 数据库名
            schema_name: 模式名
        """
        self.engine = engine
        self.db_type = db_type.lower()
        self.db_name = db_name
        self.schema_name = schema_name or self._get_default_schema()
        # 初始化方言适配器
        self.dialect_adapter = DialectAdapter(self.db_type)

    def _get_default_schema(self) -> str:
        """获取默认 schema"""
        defaults = {
            'postgresql': 'public',
            'mssql': 'dbo',
            'oracle': None,
            'mysql': None,
            'sqlite': None,
            'trino': None,
            'oceanbase': None,  # OceanBase MySQL 模式无 schema 分离
            # 达梦 DM：与 Oracle 行为一致，无默认 schema（默认使用用户名大写作为 owner）
            # 这里返回 None，让调用方从 username 派生（避免误传 'public' 等非达梦默认值）
            'dm': None,
            # 人大金仓 KingBase：基于 PostgreSQL 协议，默认 schema 为 public
            'kingbase': 'public',
        }
        return defaults.get(self.db_type)

    def _quote_identifier(self, name: str) -> str:
        """根据数据库类型添加标识符引号"""
        return self.dialect_adapter.quote_identifier(name)

    def _build_table_name(self, table_name: str) -> str:
        """构建完整的表名"""
        if self.schema_name:
            return f"{self._quote_identifier(self.schema_name)}.{self._quote_identifier(table_name)}"
        return self._quote_identifier(table_name)

    def _get_table_columns(self, table_name: str) -> List[str]:
        """获取表的所有列名（不带引号）

        使用 information_schema.columns 适配多种数据库方言。
        当查询失败时回退到返回空列表（调用方将仅返回查询字段）。
        """
        try:
            # 人大金仓（KingBase）基于 PostgreSQL，复用 PostgreSQL 的查询
            if self.db_type in ('postgresql', 'kingbase'):
                cols_sql = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                      AND table_schema = :schema
                    ORDER BY ordinal_position
                """) if self.schema_name else text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_catalog = :db_name AND table_name = :table_name
                    ORDER BY ordinal_position
                """)
            elif self.db_type == 'mysql' or self.db_type == 'oceanbase':
                # OceanBase MySQL 模式与 MySQL 行为一致，复用同一查询方式
                cols_sql = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :db_name AND table_name = :table_name
                    ORDER BY ordinal_position
                """)
            elif self.db_type == 'mssql':
                cols_sql = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_catalog = :db_name
                      AND (table_schema = :schema OR (:schema IS NULL))
                      AND table_name = :table_name
                    ORDER BY ordinal_position
                """)
            elif self.db_type == 'sqlite':
                cols_sql = text("""
                    SELECT p.name as column_name
                    FROM pragma_table_info(:table_name) p
                """)
            elif self.db_type == 'dm':
                # 达梦 DM：使用 ALL_TAB_COLUMNS（与 Oracle 一致）
                # ALL_TAB_COLUMNS 通过 owner + table_name 唯一定位
                cols_sql = text("""
                    SELECT column_name
                    FROM all_tab_columns
                    WHERE owner = :schema AND table_name = :table_name
                    ORDER BY column_id
                """)
                # 达梦场景下：db_name 实际是 owner（用户名大写），从 schema_name 兜底
                # 调用者传入的 self.schema_name 已经是 owner 大写形式
            else:
                cols_sql = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_catalog = :db_name AND table_name = :table_name
                    ORDER BY ordinal_position
                """)

            params = {'table_name': table_name, 'db_name': self.db_name}
            if self.schema_name:
                params['schema'] = self.schema_name

            with self.engine.begin() as conn:
                rows = conn.execute(cols_sql, params).fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            print(f"[WARN] 获取表 {table_name} 的列信息失败: {e}")
            return []

    def _generate_sql(self, rule: GovernanceRule) -> tuple:
        """根据规则生成检测 SQL。

        优先策略：
        1. 有 sql_text → 直接使用用户已确认的最终 SQL
        2. 无 sql_text → 兜底动态生成（兼容旧数据）

        Returns:
            (sql: str, params: dict)
        """
        # 策略1：直接使用用户确认的 sql_text
        if rule.sql_text and rule.sql_text.strip():
            # sql_text 是用户已确认的最终 SQL，直接使用，不做任何修改
            return rule.sql_text.strip(), {}

        # 策略2：无 sql_text，兜底动态生成（仅兼容历史数据）
        table = rule.target_table
        column = rule.target_column or ''
        condition = rule.condition_expr or ''
        conditions_config = rule.conditions_config

        # 有作用域的规则必须指定目标表
        if not table:
            raise ValueError(
                f"规则「{rule.rule_name}」(id={rule.id})缺少 target_table，无法生成检测 SQL。"
                f"请使用 execute_multi_table() 对无作用域规则进行批量多表执行。"
            )

        full_table = self._build_table_name(table)
        quoted_column = self._quote_identifier(column)
        rule_type = rule.rule_type

        # 优先处理多条件模式
        if conditions_config:
            try:
                import json
                if isinstance(conditions_config, str):
                    config = json.loads(conditions_config)
                else:
                    config = conditions_config

                conditions = config.get('conditions', [])
                condition_mode = config.get('condition_mode', 'AND')

                if conditions and len(conditions) > 0:
                    # 多条件模式
                    # 语义说明：
                    #   conditions_config 中存储的是【业务条件】（business conditions），
                    #   即用户描述中的"必须满足的条件"。
                    #   例如：规则"订购数量>0 且 日期≥2025-09"
                    #         条件1: qty > 0（订购数量必须满足）
                    #         条件2: order_date >= '2025-09-01'（日期必须满足）
                    #         condition_mode: AND
                    #
                    #   执行逻辑（De Morgan 取反）：
                    #     NOT (qty > 0) OR NOT (order_date >= '2025-09-01')
                    #   等价于：违反任意一个条件即为违规行
                    where_clauses = []
                    for cond in conditions:
                        cond_column = cond.get('column', '')
                        cond_expr = cond.get('condition', '')

                        if not cond_column or not cond_expr:
                            continue

                        quoted_cond_column = self._quote_identifier(cond_column)
                        # 替换 column 占位符
                        adapted_cond = re.sub(
                            r'\bcolumn\b',
                            quoted_cond_column,
                            cond_expr.strip(),
                            flags=re.IGNORECASE
                        )
                        # 业务条件取反，得到违规条件
                        negated = f"NOT ({adapted_cond})"
                        where_clauses.append(f"({negated})")

                    if where_clauses:
                        # De Morgan 取反：业务 AND → 违规 OR，业务 OR → 违规 AND
                        sql_mode = 'OR' if condition_mode == 'AND' else 'AND'
                        where_clause = f"\n    {sql_mode} ".join(where_clauses)
                        sql = f"""
                            SELECT
                                COUNT(*) as total_count,
                                SUM(CASE WHEN {where_clause} THEN 1 ELSE 0 END) as failed_count
                            FROM {full_table}
                        """
                        return sql.strip(), {}

            except Exception as e:
                print(f"[WARN] 解析 conditions_config 失败: {str(e)}")

        # 专家模式：有 condition_expr 时，直接使用条件表达式
        if condition and condition.strip():
            adapted_condition = re.sub(
                r'\bcolumn\b',
                quoted_column,
                condition.strip(),
                flags=re.IGNORECASE
            )

            # 一致性校验的特殊处理：只有"双方都为 NULL"才豁免
            # 违规条件：(col1 <> col2) OR (col1 IS NULL) <> (col2 IS NULL)
            if rule_type == 'consistency_check':
                match = re.search(r'(\w+)\s*=\s*(\w+)', condition.strip())
                if match:
                    col1, col2 = match.group(1), match.group(2)
                    adapted_condition = f"({col1} <> {col2}) OR ({col1} IS NULL) <> ({col2} IS NULL)"
                    sql = f"""
                        SELECT
                            COUNT(*) as total_count,
                            SUM(CASE WHEN {adapted_condition} THEN 1 ELSE 0 END) as failed_count
                        FROM {full_table}
                    """
                    return sql.strip(), {}

            # 其他规则类型：NOT(业务条件) = 违规条件
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN NOT ({adapted_condition}) THEN 1 ELSE 0 END) as failed_count
                FROM {full_table}
            """
            return sql.strip(), {}

        # 自动模式：无 condition_expr 时，根据 rule_type 生成默认的【业务条件】，
        # SQL 使用 NOT(业务条件) 包装使其成为违规条件（与专家模式语义一致）

        if rule_type == 'null_check':
            # 业务条件：字段必须有值；违反条件：NOT(IS NOT NULL AND != '')
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN NOT ({quoted_column} IS NOT NULL AND {quoted_column} != '') THEN 1 ELSE 0 END) as failed_count
                FROM {full_table}
            """
            return sql.strip(), {}

        elif rule_type == 'unique':
            # 业务条件：字段值必须唯一；违反条件：出现重复
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({quoted_column}) as non_null_count,
                    COUNT(DISTINCT {quoted_column}) as unique_count,
                    COUNT(*) - COUNT(DISTINCT {quoted_column}) as duplicate_count
                FROM {full_table}
                WHERE {quoted_column} IS NOT NULL AND {quoted_column} != ''
            """
            return sql.strip(), {}

        elif rule_type == 'format':
            # 业务条件：adapted_regex 匹配；违反条件：NOT(matches)
            adapted_regex = self._adapt_regex_condition(condition, quoted_column)
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN {quoted_column} IS NOT NULL AND {quoted_column} != '' AND NOT ({adapted_regex}) THEN 1 ELSE 0 END) as failed_count
                FROM {full_table}
            """
            return sql.strip(), {}

        elif rule_type == 'consistency_check':
            # 一致性校验：只有"双方都为 NULL"才豁免
            # 违规条件：(col1 <> col2) OR (col1 IS NULL) <> (col2 IS NULL)
            # 注意：不能用 NOT() 取反，因为 NULL 值会导致 NOT(NULL)=NULL，CASE 落入 ELSE
            match = re.search(r'(\w+)\s*=\s*(\w+)', condition.strip())
            if match:
                col1, col2 = match.group(1), match.group(2)
                # 违规条件：不相等 或 NULL状态不同
                violation_condition = f"({col1} <> {col2}) OR ({col1} IS NULL) <> ({col2} IS NULL)"
                sql = f"""
                    SELECT
                        COUNT(*) as total_count,
                        SUM(CASE WHEN {violation_condition} THEN 1 ELSE 0 END) as failed_count
                    FROM {full_table}
                """
                return sql.strip(), {}

            # 解析失败，回退到普通逻辑
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN {quoted_column} IS NOT NULL AND NOT ({adapted_condition}) THEN 1 ELSE 0 END) as failed_count
                FROM {full_table}
            """
            return sql.strip(), {}

        elif rule_type in ('threshold', 'enum', 'custom_sql', 'length_check', 'range_check', 'date_check', 'freshness_check', 'value_distribution'):
            # 业务条件：adapted_condition；违反条件：NOT(adapted_condition)
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN {quoted_column} IS NOT NULL AND NOT ({adapted_condition}) THEN 1 ELSE 0 END) as failed_count
                FROM {full_table}
            """
            return sql.strip(), {}

        else:
            raise ValueError(f"不支持的规则类型: {rule_type}")

    def _adapt_regex_condition(self, condition: str, quoted_column: str) -> str:
        """
        适配正则表达式条件

        Args:
            condition: 原始条件表达式
            quoted_column: 引号后的列名

        Returns:
            适配后的正则表达式条件
        """
        if not condition:
            return quoted_column

        # 如果条件中包含正则匹配符号，适配语法
        if '~*' in condition or 'REGEXP' in condition.upper():
            # 替换列名
            result = re.sub(r'\bcolumn\b', quoted_column, condition, flags=re.IGNORECASE)

            # 适配正则语法
            # 人大金仓（KingBase）基于 PostgreSQL，复用 PostgreSQL 的正则语法
            if self.db_type in ('postgresql', 'kingbase'):
                # PostgreSQL 使用 ~* (不区分大小写)
                pass
            elif self.db_type == 'mysql' or self.db_type == 'oceanbase':
                # MySQL/OceanBase 使用 REGEXP
                result = result.replace('~*', 'REGEXP')
            elif self.db_type in ('oracle', 'dm'):
                # Oracle / 达梦 DM 使用 REGEXP_LIKE 函数（达梦与 Oracle 兼容）
                # 处理逻辑：把 "~*" 转换为 REGEXP_LIKE(col, 'pattern') 函数调用
                # 注意：这里保持简化版，达梦的实际正则表达式处理已由 DialectAdapter 处理
                # 此分支主要用于清理 PG 风格的 ~* 表达式
                result = result.replace('~*', 'REGEXP_LIKE_PLACEHOLDER')  # 占位符，由调用方进一步处理
            elif self.db_type in ('mssql', 'sqlite'):
                # 不支持正则，降级为 LIKE
                # 简单转换：移除正则符号，使用简单匹配
                result = quoted_column

            return result
        else:
            # 非正则条件，直接替换列名
            return re.sub(r'\bcolumn\b', quoted_column, condition, flags=re.IGNORECASE)

    def _process_result(self, rule: GovernanceRule, rows: List[dict]) -> Dict[str, Any]:
        """处理执行结果

        Args:
            rule: 规则对象
            rows: 查询结果

        Returns:
            处理后的结果字典（包含 processed_stats 和 raw_row）
        """
        if not rows:
            return {
                'total_count': 0,
                'passed_count': 0,
                'failed_count': 0,
                'failed_rate': 0.0,
                'status': 'error',
                'raw_row': None
            }

        raw_row = dict(rows[0])  # 保留原始行数据
        total = int(raw_row.get('total_count', 0) or 0)

        if rule.rule_type == 'unique':
            # 唯一性检测特殊处理
            non_null = int(raw_row.get('non_null_count', 0) or 0)
            unique = int(raw_row.get('unique_count', 0) or 0)
            duplicate = int(raw_row.get('duplicate_count', 0) or 0)
            failed = duplicate
            passed = total - failed if total > 0 else 0
        else:
            failed = int(raw_row.get('failed_count', 0) or 0)
            passed = total - failed if total > 0 else 0

        failed_rate = (failed / total * 100) if total > 0 else 0.0

        # 判断状态：通过率 >= 95% 为通过
        pass_rate = 100 - failed_rate
        if pass_rate >= 95:
            status = 'passed'
        elif total == 0:
            status = 'passed'  # 空表视为通过
        else:
            status = 'failed'

        return {
            'total_count': total,
            'passed_count': passed,
            'failed_count': failed,
            'failed_rate': round(failed_rate, 2),
            'status': status,
            'raw_row': raw_row
        }

    def _resolve_column_name(self, rule: GovernanceRule) -> Optional[str]:
        """
        解析规则的目标列名。

        - 单列规则：直接返回 rule.target_column
        - 多条件规则（composite）：从 conditions_config 中提取所有列名，逗号拼接

        Returns:
            列名字符串，如 "warehouse" 或 "warehouse,quantity"，无列信息时返回 None
        """
        # 单列/单条件规则
        if rule.target_column:
            return rule.target_column

        # 多条件规则：从 conditions_config 中提取所有列名
        if rule.conditions_config:
            try:
                import json
                config = rule.conditions_config
                if isinstance(config, str):
                    config = json.loads(config)

                columns = [c.get('column', '') for c in config.get('conditions', []) if c.get('column')]
                # 去重保持顺序
                seen = set()
                unique_cols = []
                for col in columns:
                    if col and col not in seen:
                        seen.add(col)
                        unique_cols.append(col)

                if unique_cols:
                    return ','.join(unique_cols)
            except Exception:
                pass

        return None

    def _extract_where_from_sql_text(self, sql_text: str) -> str:
        """
        从 sql_text 中提取 WHERE 条件。

        sql_text 格式：
            SELECT COUNT(*) as total_count,
                   SUM(CASE WHEN <where_condition> THEN 1 ELSE 0 END) as failed_count
            FROM ...

        提取 <where_condition> 部分用于样本查询。
        """
        # 匹配 CASE WHEN ... THEN 1 ELSE 0 END
        match = re.search(
            r'CASE\s+WHEN\s+(.+?)\s+THEN\s+1\s+ELSE\s+0\s+END',
            sql_text,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return ''

    def _get_sample_data(self, rule: GovernanceRule, limit: int = 20) -> List[dict]:
        """获取失败样本数据（带条件上下文）

        优先使用 sql_text 中的 WHERE 条件；
        无 sql_text 时兜底动态生成（兼容旧数据）。

        Args:
            rule: 规则对象
            limit: 样本数量限制（默认 20 条）

        Returns:
            失败样本列表（带条件上下文）

        失败样本每个元素的字段：
            - sample_value: 数组形式，包含所有违规记录。每条记录为完整数据库记录（全字段），便于用户追溯
            - violated_conditions: 数组形式，列出所有违反的条件
                - 每个元素: {column: 列名, condition: 原始条件, negated_condition: 取反后的条件}
            - condition_mode: 多条件模式（AND / OR），仅多条件规则时存在
            - rule_type: 规则类型
            - condition_expr: 条件表达式（仅专家模式时存在）
        """
        table = rule.target_table or ''
        column = rule.target_column or ''

        if not table:
            return []

        full_table = self._build_table_name(table)

        try:
            # 策略1：有 sql_text，直接提取 WHERE 条件
            if rule.sql_text and rule.sql_text.strip():
                sql_text = rule.sql_text.strip()

                where_clause = self._extract_where_from_sql_text(sql_text)
                if not where_clause:
                    return []

                # 解析目标列：单列规则直接用 target_column；
                # 多条件规则（composite）从 conditions_config 中提取所有列，逗号拼接；
                # 兜底：从 WHERE 条件中正则匹配第一个列名
                sample_col = self._resolve_column_name(rule)

                # 多列（composite）规则：select 所有相关列，让样本带有完整上下文
                sample_cols = []
                if rule.conditions_config:
                    try:
                        import json as _json
                        cfg = rule.conditions_config
                        if isinstance(cfg, str):
                            cfg = _json.loads(cfg)
                        for c in cfg.get('conditions', []):
                            col = c.get('column', '')
                            if col and col not in sample_cols:
                                sample_cols.append(col)
                    except Exception:
                        sample_cols = []
                if not sample_cols and sample_col:
                    sample_cols = [c.strip() for c in sample_col.split(',') if c.strip()]

                if not sample_cols:
                    return []

                # 构建 SELECT 子句：优先查询全字段（便于用户数据库中追溯）
                # 自动使用全字段：用户希望看到违规行的完整记录
                all_columns = self._get_table_columns(table)
                if all_columns:
                    select_parts = [self._quote_identifier(c) for c in all_columns]
                else:
                    # 回退到目标字段
                    select_parts = []
                    for c in sample_cols:
                        select_parts.append(f"{self._quote_identifier(c)} as {self._quote_identifier(c)}")
                select_clause = ", ".join(select_parts)

                # 先获取违规记录
                sample_sql = f"""
                    SELECT {select_clause}
                    FROM {full_table}
                    WHERE {where_clause}
                    LIMIT :limit
                """

                # 将所有数据库操作放在一个 with 块内
                with self.engine.begin() as conn:
                    result = conn.execute(text(sample_sql), {'limit': limit})
                    raw_samples = [dict(row) for row in result.mappings().all()]  # 全字段原始记录

                    # 如果有多条件配置，需要精确检测每条记录违反了哪个条件
                    # 但样本查询已获得全部字段，sample_value 直接使用 raw_samples
                    if rule.conditions_config and len(sample_cols) > 1:
                        try:
                            import json as _json
                            cfg = rule.conditions_config
                            if isinstance(cfg, str):
                                cfg = _json.loads(cfg)
                            conditions = cfg.get('conditions', [])
                            condition_mode = cfg.get('condition_mode', 'AND')

                            print(f"[DEBUG] 检测多条件违规: conditions_count={len(conditions)}, condition_mode={condition_mode}")

                            if not conditions:
                                print("[DEBUG] conditions为空，跳过精确检测")
                                raise Exception("conditions为空")

                            samples = []
                            # 收集所有违规记录（全字段直接来自数据库查询）
                            all_records = []
                            all_violated_conditions = []

                            for row in raw_samples:
                                # row 已经是完整记录（全字段），用于后续追溯
                                # 提取目标字段值用于违规检测
                                row_values = {}
                                for c in sample_cols:
                                    raw_key = c
                                    qc = self._quote_identifier(c)
                                    if raw_key in row:
                                        row_values[c] = row[raw_key]
                                    elif qc in row:
                                        row_values[c] = row[qc]
                                    else:
                                        # 不区分大小写尝试
                                        for k in row.keys():
                                            if str(k).lower() == str(c).lower():
                                                row_values[c] = row[k]
                                                break

                                # 检测该记录违反了哪些条件
                                violated_list = []
                                for cond in conditions:
                                    cond_col = cond.get('column', '')
                                    cond_expr = cond.get('condition', '')
                                    if not cond_col or not cond_expr:
                                        continue

                                    quoted_col = self._quote_identifier(cond_col)
                                    adapted_cond = re.sub(
                                        r'\bcolumn\b',
                                        quoted_col,
                                        cond_expr.strip(),
                                        flags=re.IGNORECASE
                                    )

                                    # 构建该记录的判断条件
                                    row_identifiers = []
                                    for c in sample_cols:
                                        val = row_values.get(c)
                                        qc = self._quote_identifier(c)
                                        if val is None:
                                            row_identifiers.append(f"{qc} IS NULL")
                                        elif isinstance(val, (int, float)):
                                            row_identifiers.append(f"{qc} = {val}")
                                        else:
                                            safe_val = str(val).replace("'", "''")
                                            row_identifiers.append(f"{qc} = '{safe_val}'")

                                    row_where = " AND ".join(row_identifiers)

                                    # 检查该行是否违反此条件（NOT原始条件 = TRUE）
                                    check_sql = f"""
                                        SELECT CASE WHEN NOT ({adapted_cond}) THEN 1 ELSE 0 END as violated
                                        FROM {full_table}
                                        WHERE {row_where}
                                    """

                                    try:
                                        check_result = conn.execute(text(check_sql), {})
                                        check_row = check_result.fetchone()
                                        is_violated = check_row and check_row[0] == 1
                                        print(f"[DEBUG] 检测 cond_col={cond_col}, cond_expr={cond_expr[:50]}, is_violated={is_violated}")
                                        if is_violated:
                                            violated_list.append({
                                                'column': cond_col,
                                                'condition': cond_expr,
                                                'negated_condition': f"NOT ({adapted_cond})"
                                            })
                                    except Exception as check_err:
                                        print(f"[WARN] 检测条件违反情况失败: {check_err}, sql={check_sql}")

                                # 如果没有检测到违反条件，但该记录在违规结果中
                                if not violated_list:
                                    violated_list.append({
                                        'column': ','.join(sample_cols),
                                        'condition': where_clause,
                                        'negated_condition': where_clause
                                    })

                                # 收集【全字段】记录和违反的条件
                                all_records.append(row)
                                for vc in violated_list:
                                    if vc not in all_violated_conditions:
                                        all_violated_conditions.append(vc)

                            # 返回统一的样本结构（全字段记录）
                            samples.append({
                                'sample_value': all_records,  # 数组形式，包含数据库完整记录（全字段）
                                'violated_conditions': all_violated_conditions,
                                'condition_mode': condition_mode,
                                'rule_type': rule.rule_type
                            })

                            print(f"[DEBUG] 最终返回 samples={samples}")
                            return samples
                        except Exception as e:
                            print(f"[WARN] 精确检测违规条件失败: {str(e)}")

                    # 单列规则或多条件检测失败，回退到简单模式
                    # 直接使用 raw_samples（全字段来自数据库原始查询）
                    violated_list = [{
                        'column': ','.join(sample_cols),
                        'condition': where_clause,
                        'negated_condition': where_clause
                    }]
                    return [{
                        'sample_value': raw_samples,  # 数组形式，数据库完整原始记录（全字段）
                        'violated_conditions': violated_list,
                        'rule_type': rule.rule_type,
                        'condition_mode': 'AND'
                    }] 

            # 策略2：无 sql_text，兜底动态生成样本查询
            condition = rule.condition_expr or ''
            conditions_config = rule.conditions_config

            # 优先处理多条件模式
            if conditions_config:
                try:
                    import json
                    if isinstance(conditions_config, str):
                        config = json.loads(conditions_config)
                    else:
                        config = conditions_config

                    conditions = config.get('conditions', [])
                    condition_mode = config.get('condition_mode', 'AND')

                    if conditions and len(conditions) > 0:
                        # 存储的是【业务条件】，需要取反后查询违规行
                        # De Morgan：业务 AND → 违规 OR，业务 OR → 违规 AND
                        where_clauses = []
                        for cond in conditions:
                            cond_col = cond.get('column', '')
                            cond_expr_item = cond.get('condition', '')
                            if not cond_col or not cond_expr_item:
                                continue
                            quoted_cond_col = self._quote_identifier(cond_col)
                            adapted_cond = re.sub(
                                r'\bcolumn\b',
                                quoted_cond_col,
                                cond_expr_item.strip(),
                                flags=re.IGNORECASE
                            )
                            # 业务条件取反
                            negated = f"NOT ({adapted_cond})"
                            where_clauses.append((cond_col, cond_expr_item, f"({negated})"))

                        if where_clauses:
                            sql_mode = 'OR' if condition_mode == 'AND' else 'AND'
                            all_where = f"\n    {sql_mode} ".join([c[2] for c in where_clauses])
                            first_col = where_clauses[0][0]
                            quoted_first_col = self._quote_identifier(first_col)

                            # 构建返回列 - 优先使用全字段
                            sample_cols = [c[0] for c in where_clauses]
                            all_columns = self._get_table_columns(table)
                            if all_columns:
                                select_parts = [self._quote_identifier(c) for c in all_columns]
                            else:
                                select_parts = [self._quote_identifier(c) + f" as {self._quote_identifier(c)}" for c in sample_cols]
                            select_clause = ", ".join(select_parts)

                            # 先获取所有违规记录，然后精确检测每条记录违反了哪个条件
                            sql = f"""
                                SELECT {select_clause}
                                FROM {full_table}
                                WHERE {all_where}
                                LIMIT :limit
                            """
                            with self.engine.begin() as conn:
                                result = conn.execute(text(sql), {'limit': limit})
                                raw_samples = [dict(row) for row in result.mappings().all()]  # 全字段原始记录

                                # 精确检测每条记录违反了哪个条件
                                all_records = []
                                all_violated_conditions = []

                                for row in raw_samples:
                                    # 提取目标字段值用于违规检测（兼容带引号的key）
                                    row_values = {}
                                    for c in sample_cols:
                                        qc = self._quote_identifier(c)
                                        if c in row:
                                            row_values[c] = row[c]
                                        elif qc in row:
                                            row_values[c] = row[qc]
                                        else:
                                            for k in row.keys():
                                                if str(k).lower() == str(c).lower():
                                                    row_values[c] = row[k]
                                                    break

                                    # 检测该记录违反了哪些条件
                                    violated_list = []
                                    for cond_col, cond_expr_item, adapted_cond_clause in where_clauses:
                                        quoted_col = self._quote_identifier(cond_col)

                                        # 构建该记录的判断条件
                                        row_identifiers = []
                                        for c in sample_cols:
                                            val = row_values.get(c)
                                            qc = self._quote_identifier(c)
                                            if val is None:
                                                row_identifiers.append(f"{qc} IS NULL")
                                            elif isinstance(val, (int, float)):
                                                row_identifiers.append(f"{qc} = {val}")
                                            else:
                                                safe_val = str(val).replace("'", "''")
                                                row_identifiers.append(f"{qc} = '{safe_val}'")

                                        row_where = " AND ".join(row_identifiers)

                                        # 检查该行是否违反此条件（NOT原始条件 = TRUE）
                                        adapted_cond = re.sub(
                                            r'\bcolumn\b',
                                            quoted_col,
                                            cond_expr_item.strip(),
                                            flags=re.IGNORECASE
                                        )
                                        check_sql = f"""
                                            SELECT CASE WHEN NOT ({adapted_cond}) THEN 1 ELSE 0 END as violated
                                            FROM {full_table}
                                            WHERE {row_where}
                                        """

                                        try:
                                            check_result = conn.execute(text(check_sql), {})
                                            check_row = check_result.fetchone()
                                            if check_row and check_row[0] == 1:
                                                violated_list.append({
                                                    'column': cond_col,
                                                    'condition': cond_expr_item,
                                                    'negated_condition': f"NOT ({adapted_cond})"
                                                })
                                        except Exception:
                                            pass

                                    # 如果没有检测到违反条件，但该记录在违规结果中
                                    if not violated_list:
                                        violated_list.append({
                                            'column': ','.join(sample_cols),
                                            'condition': cond_expr_item,
                                            'negated_condition': all_where
                                        })

                                    # 收集全字段记录和违反条件
                                    all_records.append(row)
                                    for vc in violated_list:
                                        if vc not in all_violated_conditions:
                                            all_violated_conditions.append(vc)

                                # 返回统一的样本结构
                                return [{
                                    'sample_value': all_records,  # 数组形式，数据库完整原始记录（全字段）
                                    'violated_conditions': all_violated_conditions,
                                    'condition_mode': condition_mode,
                                    'rule_type': rule.rule_type
                                }] 
                except Exception as e:
                    print(f"[WARN] 多条件样本查询失败: {str(e)}")

            # 单条件模式
            if not column:
                return []

            quoted_column = self._quote_identifier(column)

            # 专家模式优先：有 condition_expr 时直接使用，忽略 rule_type 的特殊处理
            # 这样手动输入 "column IS NOT NULL" 时，样本查询与检测SQL保持一致
            if condition and condition.strip():
                # 专家模式：附带原始条件表达式
                adapted_condition = re.sub(
                    r'\bcolumn\b',
                    quoted_column,
                    condition.strip(),
                    flags=re.IGNORECASE
                )
                # 优先使用全字段查询，便于用户追溯
                all_columns = self._get_table_columns(table)
                if all_columns:
                    select_clause = ", ".join([self._quote_identifier(c) for c in all_columns])
                else:
                    select_clause = quoted_column
                # condition 是"必须满足的业务条件"
                # 取反后得到"违规条件"，用于筛选违规样本
                sql = f"""
                    SELECT {select_clause}
                    FROM {full_table}
                    WHERE NOT ({adapted_condition})
                    LIMIT :limit
                """
                with self.engine.begin() as conn:
                    result = conn.execute(text(sql), {'limit': limit})
                    all_records = []
                    for row in result.mappings().all():
                        all_records.append(dict(row))
                    return [{
                        'sample_value': all_records,  # 数组形式，数据库完整原始记录（全字段）
                        'condition_expr': condition.strip()
                    }]

            # 以下为自动模式（无 condition_expr）：根据 rule_type 生成默认样本条件
            # 样本采集逻辑与 _generate_sql 保持完全一致：
            # 自动模式的"业务条件"取反后得到违规样本的 WHERE 子句
            # 优先查询全字段，便于用户追溯
            all_columns = self._get_table_columns(table)
            base_select = ", ".join([self._quote_identifier(c) for c in all_columns]) if all_columns else quoted_column

            if rule.rule_type == 'null_check':
                # 业务条件：字段必须有值；违规条件：NOT(IS NOT NULL AND != '')
                sql = f"""
                    SELECT {base_select}
                    FROM {full_table}
                    WHERE NOT ({quoted_column} IS NOT NULL AND {quoted_column} != '')
                    LIMIT :limit
                """
            elif rule.rule_type == 'unique':
                # 自动模式：找出重复值（额外保留 count 字段）
                if all_columns:
                    extra_cols = ", ".join([f"{self._quote_identifier(c)} as dup_{c}" for c in all_columns])
                    select_clause = f"{quoted_column}, {extra_cols}, COUNT(*) as count"
                else:
                    select_clause = f"{quoted_column}, COUNT(*) as count"
                sql = f"""
                    SELECT {select_clause}
                    FROM {full_table}
                    WHERE {quoted_column} IS NOT NULL AND {quoted_column} != ''
                    GROUP BY {quoted_column}
                    HAVING COUNT(*) > 1
                    LIMIT :limit
                """
            else:
                # 业务条件：adapted_condition；违规条件：NOT(adapted_condition)
                sql = f"""
                    SELECT {base_select}
                    FROM {full_table}
                    WHERE {quoted_column} IS NOT NULL AND NOT ({self.dialect_adapter.adapt_condition_expr(condition, column)})
                    LIMIT :limit
                """

            with self.engine.begin() as conn:
                result = conn.execute(text(sql), {'limit': limit})
                all_records = []
                for row in result.mappings().all():
                    all_records.append(dict(row))
                return [{
                    'sample_value': all_records,  # 数组形式，数据库完整原始记录（全字段）
                    'condition_expr': condition.strip() if condition.strip() else None,
                    'rule_type': rule.rule_type
                }] 

        except Exception as e:
            # 失败样例采集异常：打印详细错误（包含规则ID便于追溯），
            # 返回空数组而不是中断规则执行——样本采集是辅助，不应阻断主流程
            print(
                f"[WARN] 获取失败样本失败 | rule_id={rule.id} | "
                f"rule_name={rule.rule_name} | error={str(e)}"
            )
            return []

    def execute_rule(self, rule: GovernanceRule) -> RuleExecutionResult:
        """执行单条规则

        Args:
            rule: 规则对象

        Returns:
            RuleExecutionResult 对象
        """
        import time as time_module

        result = RuleExecutionResult()
        result.library_id = rule.library_id
        result.rule_id = rule.id
        result.rule_name = rule.rule_name
        result.rule_type = rule.rule_type
        result.severity = rule.severity
        result.table_name = rule.target_table
        result.column_name = self._resolve_column_name(rule)
        result.status = 'error'
        result.execution_source = RuleExecutionResult.SOURCE_RULE_LIBRARY

        # 确定执行模式
        if rule.target_table:
            if rule.conditions_config:
                result.rule_mode = RuleExecutionResult.MODE_SCOPED_MULTI_COND
            else:
                result.rule_mode = RuleExecutionResult.MODE_SCOPED_SINGLE
        else:
            result.rule_mode = RuleExecutionResult.MODE_UNSCOPED

        print(f"\n[环节二 - 执行规则] 开始执行")
        print(f"  规则ID:     {rule.id}")
        print(f"  规则名称:   {rule.rule_name}")
        print(f"  规则类型:   {rule.rule_type}")
        print(f"  执行模式:   {result.rule_mode}")
        print(f"  目标表:     {rule.target_table}")
        print(f"  目标列:     {rule.target_column or '(无，多条件模式)'}")
        print(f"  条件表达式: {rule.condition_expr or '(无)'}")
        if rule.conditions_config:
            print(f"  多条件配置: {rule.conditions_config[:200]}{'...' if len(rule.conditions_config) > 200 else ''}")

        try:
            # 生成检测 SQL
            start_time = time_module.time()
            sql, params = self._generate_sql(rule)
            elapsed_ms = round((time_module.time() - start_time) * 1000, 2)

            result.executed_sql_text = sql

            print(f"  生成SQL耗时: {elapsed_ms}ms")
            print(f"  执行的SQL:\n{sql}")
            if params:
                print(f"  SQL参数: {params}")

            # 执行 SQL
            start_exec = time_module.time()
            with self.engine.begin() as conn:
                result_query = conn.execute(text(sql), params)
                rows = [dict(row) for row in result_query.mappings().all()]

            exec_ms = round((time_module.time() - start_exec) * 1000, 2)
            result.execution_time_ms = exec_ms

            print(f"  SQL执行耗时: {exec_ms}ms")

            # 处理结果
            processed = self._process_result(rule, rows)
            result.total_count = processed['total_count']
            result.passed_count = processed['passed_count']
            result.failed_count = processed['failed_count']
            result.failed_rate = processed['failed_rate']
            result.status = processed['status']
            # 存储 SQL 原始返回结果（先做 JSON 清洗，避免 datetime/UUID 等类型无法序列化）
            result.raw_result = _sanitize_for_json(processed['raw_row'])

            print(f"  执行结果:")
            print(f"    total_count = {result.total_count}")
            print(f"    passed_count = {result.passed_count}")
            print(f"    failed_count = {result.failed_count}")
            print(f"    failed_rate  = {result.failed_rate}%")
            print(f"    status       = {result.status}")
            print(f"    raw_result   = {result.raw_result}")

            # 获取失败样本
            if result.status == 'failed' and result.failed_count > 0:
                print(f"  正在获取失败样本...")
                samples = self._get_sample_data(rule, limit=20)
                # 样本可能包含数据库返回的 datetime/Decimal 等不可 JSON 序列化类型
                result.failed_samples = _sanitize_for_json(samples)
                print(f"  失败样本数: {len(samples)}")

            print(f"[环节二 - 执行规则] ✅ {rule.rule_name} 执行完成 | status={result.status}")

        except Exception as e:
            result.status = 'error'
            result.error_message = _get_friendly_sql_error_message(e, rule)
            result.execution_time_ms = None
            print(f"[环节二 - 执行规则] ❌ {rule.rule_name} 执行异常: {e}")

        print()
        return result

    def execute_rules(self, rules: List[GovernanceRule]) -> List[RuleExecutionResult]:
        """批量执行规则

        Args:
            rules: 规则列表

        Returns:
            执行结果列表
        """
        results = []

        for rule in rules:
            if not rule.enabled:
                continue

            result = self.execute_rule(rule)
            results.append(result)

        return results


class AuditExecutor:
    """治理盘点执行器 - 完整的执行流程"""

    def __init__(self, engine: Engine, db_type: str, db_name: str, schema_name: str = None,
                 connect_info: Optional[Dict[str, Any]] = None):
        """初始化执行器

        Args:
            engine: SQLAlchemy Engine 对象
            db_type: 数据库类型
            db_name: 数据库名
            schema_name: 模式名
            connect_info: 原始连接信息 dict，供 Oracle/Trino 等需要 username/catalog/schema
                          的场景使用；PG/MySQL/MSSQL/SQLite 可为 None
        """
        self.engine = engine
        self.db_type = db_type
        self.db_name = db_name
        self.schema_name = schema_name
        self.connect_info = connect_info or {}
        self.rule_executor = RuleExecutor(engine, db_type, db_name, schema_name)
        # 初始化方言适配器（供基础空值检测使用）
        self.dialect_adapter = DialectAdapter(db_type)

    def _quote_identifier(self, name: str) -> str:
        """根据数据库类型添加标识符引号"""
        return self.dialect_adapter.quote_identifier(name)

    def _save_basic_audit_result(
        self,
        report_id: str,
        table_name: str,
        column_name: str,
        col_type: str,
        total_count: int,
        null_count: int,
        empty_count: int,
        executed_sql: str,
        execution_time_ms: int,
        raw_result: dict,
        failed_samples: list = None
    ) -> None:
        """
        将单列的基础空值检测结果保存到 rule_execution_results 表

        Args:
            report_id: 报告ID
            table_name: 表名
            column_name: 列名
            col_type: 列数据类型
            total_count: 总记录数
            null_count: NULL 数量
            empty_count: 空字符串数量
            executed_sql: 执行的 SQL 文本
            execution_time_ms: 执行耗时（毫秒）
            raw_result: SQL 原始返回结果
            failed_samples: 失败样本数据
        """
        try:
            failed_count = null_count + empty_count
            failed_rate = round(failed_count / total_count * 100, 2) if total_count > 0 else 0.0
            passed_count = total_count - failed_count

            # 判断状态：失败率 >= 5% 为 failed，否则 passed
            status = RuleExecutionResult.STATUS_FAILED if failed_rate >= 5.0 else RuleExecutionResult.STATUS_PASSED

            result = RuleExecutionResult(
                report_id=report_id,
                library_id=None,
                rule_id=None,
                rule_name=f'基础空值检测:{table_name}.{column_name}',
                rule_type='basic_null_check',
                severity='warning',
                table_name=table_name,
                column_name=column_name,
                rule_mode=RuleExecutionResult.MODE_SCOPED_SINGLE,
                total_count=total_count,
                passed_count=passed_count,
                failed_count=failed_count,
                failed_rate=failed_rate,
                executed_sql_text=executed_sql,
                execution_time_ms=execution_time_ms,
                raw_result=raw_result,
                status=status,
                execution_source=RuleExecutionResult.SOURCE_BASIC_AUDIT
            )
            if failed_samples is not None:
                result.failed_samples = failed_samples
            db.session.add(result)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[WARN] 保存基础检测结果失败 {table_name}.{column_name}: {e}")

    def _get_all_table_names(self, tables: List[str] = None) -> List[Tuple[str, str]]:
        """
        获取数据库中所有用户可访问的表和视图列表（复用 /data_audit 接口的实现）。

        返回 [(name, type), ...]，type 为 'TABLE' 或 'VIEW'。
        基础空值检测对表和视图同等处理——视图同样可以执行 COUNT(*) 等聚合查询。

        实现策略：
        1) 优先使用 database_schema_extractor.get_tables()，它对 6 种数据库都做了适配
           （Oracle 走 all_tables + all_views、MySQL/PG 走 information_schema.tables、
            SQLite 走 sqlite_master + pragma、Trino 走 catalog.information_schema.tables）。
        2) 兜底用 SQLAlchemy Inspector（仅适用 PG/MySQL/MSSQL/SQLite）。

        Args:
            tables: 指定表名集合，None 表示全部；若传入则只保留在该集合内的表/视图

        Returns:
            [(object_name, object_type), ...] 列表，type 为 'TABLE' 或 'VIEW'
        """
        # 构造 payload 供 get_tables 用（Oracle 需 username，Trino 需 catalog）
        payload = dict(self.connect_info or {})
        if self.db_name:
            payload.setdefault('database', self.db_name)
        if self.schema_name:
            payload.setdefault('schema', self.schema_name)
            # Oracle 把 target_schema 作为 owner；Trino 拆 catalog/schema 时也要
            payload.setdefault('target_schema', self.schema_name)

        try:
            from sqlalchemy import inspect as _sa_inspect
            inspector = _sa_inspect(self.engine)
            from controllers.datasource.database_schema_extractor import get_tables as _get_tables
            records = _get_tables(inspector, self.engine, payload)
            # 同时保留 TABLE 和 VIEW；过滤掉其他类型（如 SYSTEM TABLE 等）
            names = [(r['name'], r.get('type', 'TABLE')) for r in records
                     if r.get('type', 'TABLE') in ('TABLE', 'VIEW')]
        except Exception as e:
            print(f"[WARN] get_tables 失败，兜底用 SQLAlchemy Inspector: {e}")
            try:
                from sqlalchemy import inspect as _sa_inspect
                inspector = _sa_inspect(self.engine)
                if self.schema_name:
                    table_names = list(inspector.get_table_names(schema=self.schema_name))
                else:
                    table_names = list(inspector.get_table_names())
                names = [(t, 'TABLE') for t in table_names]
            except Exception as e2:
                print(f"[ERROR] SQLAlchemy Inspector 也失败: {e2}")
                return []

        if tables:
            names = [(n, t) for n, t in names if n in tables]
        return names

    def run_basic_audit(self, report_id: str, tables: List[str] = None) -> List[Dict]:
        """
        执行基础空值检测（批量扫描所有表/列）

        **实现策略**：完全复用 controllers/datasource/dataaudit/data_audit.py 的核心逻辑
        （perform_data_audit），保证与 /data_audit 接口最终效果一致，包括：
        - PostgreSQL/MySQL/MSSQL：通过 data_audit_<db>.txt 创建存储过程/函数，再调用一次拿结果
        - Oracle/SQLite/Trino：应用层循环统计，零遗漏覆盖所有支持的边界情况
        本方法在它之上，每一列的检测结果会同时落库到 rule_execution_results 表
        （execution_source='basic_audit'）。

        Args:
            report_id: 关联的报告ID
            tables: 指定表列表，None 表示全部

        Returns:
            完整审计数据列表，格式参考 dataaudit 的 audited_data：
            [{
                "db_type": "...", "database": "...", "schema": "public",
                "table": "sales_orders",
                "report": [{"column_name": "id", "data_type": "integer",
                            "total_rows": 7, "null_count": 0, "empty_str_count": 0,
                            "missing_count": 0, "missing_pct": 0.0}, ...]
            }, ...]
        """
        # 懒加载 data_audit 模块（避免循环 import）
        from controllers.datasource.dataaudit import data_audit as _da

        # 1. 获取所有表和视图（[(Name, Type), ...]）
        all_table_entries = self._get_all_table_names(tables)
        print(f"[基础检测] 开始扫描 {len(all_table_entries)} 张表/视图 ...")

        # 2. 一次性下发 DDL（仅 PG/MySQL/MSSQL 需要；Oracle/SQLite/Trino 自动 no-op）
        try:
            _da.load_data_audit_ddl(
                self.engine,
                self.db_type,
                mysql_database=self.db_name or (self.connect_info.get('database') if self.connect_info else None),
            )
        except Exception as e:
            print(f"[WARN] 预下发 data_audit DDL 失败（部分数据库 DDL 是应用层兜底，影响有限）: {e}")

        all_audit_data = []
        for table_name, table_type in all_table_entries:
            try:
                # 复用 /data_audit 的核心实现：perform_data_audit
                import time as _time_table
                _t0 = _time_table.time()
                result = _da.perform_data_audit(
                    engine=self.engine,
                    db_type=self.db_type,
                    database_name=self.db_name,
                    table_name=table_name,
                    schema_name=self.schema_name,
                    connect_info=self.connect_info or None,
                )
                _table_ms = int((_time_table.time() - _t0) * 1000)
                column_report = result.get('report', []) or []

                # 3. 把每列的检测结果落库到 rule_execution_results
                if report_id:
                    self._save_basic_audit_columns(
                        report_id=report_id,
                        table=table_name,
                        table_type=table_type,
                        column_report=column_report,
                        execution_time_ms=_table_ms,
                    )

                # 4. 拼装返回结构（与旧实现兼容）
                all_audit_data.append({
                    "db_type": result.get('db_type', self.db_type),
                    "database": result.get('database', self.db_name),
                    "schema": result.get('schema', self.schema_name or ''),
                    "table": table_name,
                    "table_type": table_type,
                    "report": column_report,
                })
            except Exception as e:
                print(f"[WARN] 表/视图 {table_name} 基础检测失败: {e}")

        print(f"[基础检测] 完成，共扫描 {len(all_audit_data)} 张表/视图")
        return all_audit_data

    def _save_basic_audit_columns(
        self,
        report_id: str,
        table: str,
        column_report: List[Dict],
        execution_time_ms: int = 0,
        table_type: str = 'TABLE',
    ) -> None:
        """
        将 perform_data_audit 返回的列级数据，逐列写入 rule_execution_results。

        设计要点：
        - raw_result 严格匹配 perform_data_audit 返回的单行格式
          （与存储过程 SELECT * FROM data_audit(...) 的列顺序一致），
          满足"executed_sql_text 和 raw_result 严格对应"。
        - executed_sql_text 不再硬编码拼装，而是写明"实际调用了哪个 SQL/proc"：
          对 PG/MySQL/MSSQL 写 `SELECT * FROM data_audit(<schema>, <table>)` 或
          `CALL data_audit(<schema>, <table>)` / `EXEC dbo.data_audit ...`；
          对 Oracle/Trino/SQLite 写明"应用层循环实现"。
        - execution_time_ms 记录本次对单张表执行 perform_data_audit 的耗时（毫秒），
          对该表的所有列都填同一值，便于按表聚合查看慢表。
        - raw_result 中额外包含 table_type 字段，标识当前行来源是 TABLE 还是 VIEW。

        Args:
            report_id: 关联的报告ID
            table: 表/视图名
            column_report: perform_data_audit 返回的列级数据
            execution_time_ms: 该表/视图的 perform_data_audit 执行耗时（毫秒）
            table_type: 'TABLE' 或 'VIEW'，用于追溯
        """
        # 描述本次执行实际走的 SQL/proc（便于审计追溯）
        schema_label = self.schema_name or ''
        # 人大金仓（KingBase）基于 PostgreSQL，复用 PostgreSQL 的存储过程调用方式
        if self.db_type in ('postgresql', 'kingbase'):
            executed_sql = (
                f"SELECT * FROM data_audit('{schema_label}', '{table}')"
            )
        elif self.db_type == 'mysql':
            # MySQL 使用 data_audit 存储过程
            executed_sql = (
                f"CALL data_audit('{schema_label}', '{table}')"
            )
        elif self.db_type == 'oceanbase':
            # OceanBase MySQL 模式使用独立的 ob_data_audit 存储过程
            executed_sql = (
                f"CALL ob_data_audit('{schema_label}', '{table}')"
            )
        elif self.db_type in ('mssql',):
            executed_sql = (
                f"EXEC dbo.data_audit @schema='{schema_label}', @table='{table}'"
            )
        elif self.db_type == 'dm':
            # 达梦 DM：与 Oracle PL/SQL 兼容，使用独立的过程调用（与 MySQL 同样的 CALL 语法）
            executed_sql = (
                f"CALL data_audit('{schema_label}', '{table}')"
            )
        else:
            # Oracle / SQLite / Trino：应用层循环统计
            executed_sql = (
                f"-- {self.db_type}: 应用层循环（基于 perform_data_audit）"
                f"统计每列 NULL 与空字符串数量，table={table}"
            )

        for col in column_report:
            col_name = col.get('column_name') or ''
            if not col_name:
                continue
            col_type = (col.get('data_type') or '').lower()
            total_count = int(col.get('total_rows') or 0)
            null_count = int(col.get('null_count') or 0)
            empty_count = int(col.get('empty_str_count') or 0)
            failed_count = int(col.get('missing_count') or (null_count + empty_count))
            failed_rate = float(col.get('missing_pct') or 0.0)

            # raw_result 严格等于存储过程 SELECT * FROM data_audit(...) 的一行返回值，
            # 包括 column_name / data_type / total_rows / null_count / empty_str_count /
            # missing_count / missing_pct 这 7 个字段，外加 table_type 便于追溯来源。
            raw_result = {
                "column_name": col_name,
                "data_type": col.get('data_type') or '',
                "total_rows": total_count,
                "null_count": null_count,
                "empty_str_count": empty_count,
                "missing_count": failed_count,
                "missing_pct": failed_rate,
                "table_type": table_type,
            }

            self._save_basic_audit_result(
                report_id=report_id,
                table_name=table,
                column_name=col_name,
                col_type=col_type,
                total_count=total_count,
                null_count=null_count,
                empty_count=empty_count,
                executed_sql=executed_sql,
                execution_time_ms=execution_time_ms,
                raw_result=raw_result,
            )

    def execute_multi_table(
        self,
        report: GovernanceReport,
        rules: List[GovernanceRule],
        tables: List[str] = None
    ) -> GovernanceReport:
        """
        多表批量执行模式

        用于：用户不指定具体表，由系统自动识别相关表并执行规则

        Args:
            report: 报告对象
            rules: 规则列表
            tables: 指定表列表，不指定则对所有表执行

        Returns:
            更新后的报告对象
        """
        from controllers.governance.condition_generator import (
            MultiTableExecutor,
            ConditionGenerator
        )

        all_results = []

        # 1. 获取所有表的列信息
        # 规则自身有 target_table → 只扫描该表（表级规则）
        # 规则无 target_table → 扫描用户指定的表或全库（全局规则）
        multi_executor = MultiTableExecutor(self.engine, self.db_type, self.schema_name)
        # 先用全局表列表初始化，再按规则逐个过滤
        candidate_tables = tables  # 用户指定的表范围
        all_columns = multi_executor.get_all_columns(candidate_tables)

        # 2. 创建条件生成器
        generator = ConditionGenerator()

        # 3. 为每条规则生成多表条件
        for rule in rules:
            if not rule.enabled:
                continue

            # 规则有目标表 → 仅扫描该表；无目标表 → 使用全局表列表
            if rule.target_table:
                rule_scope_columns = [c for c in all_columns if c.table_name == rule.target_table]
            else:
                rule_scope_columns = all_columns

            # 根据规则生成多表条件
            conditions = generator.batch_generate_for_tables(
                rule_type=rule.rule_type,
                user_input=rule.condition_expr or "",
                is_natural_language=False,
                tables_columns=rule_scope_columns
            )

            # 为每个条件执行规则
            for condition in conditions:
                # 临时创建一个规则对象用于执行
                from models.governance_rule import GovernanceRule

                temp_rule = GovernanceRule()
                temp_rule.id = rule.id
                temp_rule.library_id = rule.library_id
                temp_rule.rule_name = rule.rule_name
                temp_rule.rule_type = rule.rule_type
                temp_rule.target_table = condition.table_name
                temp_rule.target_column = condition.column_name
                temp_rule.condition_expr = condition.condition_expr
                temp_rule.severity = rule.severity

                try:
                    result = self.rule_executor.execute_rule(temp_rule)
                    result.report_id = report.id
                    all_results.append(result)
                except Exception as e:
                    print(f"[WARN] 执行规则 {rule.rule_name} 在表 {condition.table_name} 上失败: {str(e)}")
                    continue

        # 4. 注意：不在此处 commit，由调用方 AuditExecutor.execute() 统一管理事务
        # 5. 计算汇总统计
        total_rules = len(all_results)
        passed_rules = sum(1 for r in all_results if r.status == 'passed')
        failed_rules = sum(1 for r in all_results if r.status == 'failed')
        error_rules = sum(1 for r in all_results if r.status == 'error')

        # 计算质量评分
        if total_rules > 0:
            pass_rate = (passed_rules / total_rules) * 100
            if failed_rules > 0:
                critical_count = sum(1 for r in all_results if r.severity == 'critical' and r.status == 'failed')
                if critical_count > 0:
                    pass_rate = max(0, pass_rate - critical_count * 5)
            quality_score = max(0, min(100, pass_rate))

            if quality_score >= 95:
                grade = '优秀'
            elif quality_score >= 85:
                grade = '良好'
            elif quality_score >= 70:
                grade = '一般'
            elif quality_score >= 60:
                grade = '较差'
            else:
                grade = '差'
        else:
            quality_score = 100
            grade = '优秀'

        # 6. 更新报告
        report.quality_score = quality_score
        report.grade = grade
        report.rules_applied = total_rules
        report.scope_tables = list(set(r.table_name for r in all_results if r.table_name))
        report.summary = {
            'total_rules': total_rules,
            'passed_rules': passed_rules,
            'failed_rules': failed_rules,
            'error_rules': error_rules,
            'quality_score': quality_score,
            'grade': grade
        }
        report.details = {
            'execution_results': [r.to_dict() for r in all_results],
            'execution_time': datetime.now().isoformat(),
            'multi_table_mode': True
        }

        # 不在此处 commit，由调用方 AuditExecutor.execute() 统一管理事务
        # 直接返回结果列表，避免重复 commit 和重复查询
        return all_results

    def execute(self,
                report: GovernanceReport,
                rules: List[GovernanceRule],
                include_basic_audit: bool = False,
                multi_table_mode: bool = False) -> GovernanceReport:
        """执行治理盘点

        智能规则执行策略：
        - 有 target_table + target_column 的规则 → 直接执行
        - 无表/列的规则 → 启用多表批量执行模式，自动发现相关列

        Args:
            report: 报告对象
            rules: 要执行的规则列表
            include_basic_audit: 是否包含基础空值检测
            multi_table_mode: 是否强制启用多表批量执行模式

        Returns:
            更新后的报告对象
        """
        # 分类规则：有作用域的 vs 无作用域的
        # - 有 target_table → 有作用域（直接执行）
        #   - 单列/单条件规则：有 target_table + target_column（无 conditions_config）
        #   - 多条件规则：  有 target_table + conditions_config（无 target_column）
        # - 无 target_table → 无作用域（全局规则，多表批量执行）
        scoped_rules = []   # 有 target_table 的规则
        unscoped_rules = []  # 无 target_table 的全局规则

        for rule in rules:
            if rule.target_table:
                scoped_rules.append(rule)
            else:
                unscoped_rules.append(rule)

        # 统计各类规则数量
        single_cond_count = sum(1 for r in scoped_rules if not r.conditions_config)
        multi_cond_count = sum(1 for r in scoped_rules if r.conditions_config)
        print(f"[环节二 - 规则执行] 规则分类完成:")
        print(f"  有作用域-单列规则: {single_cond_count} 条")
        print(f"  有作用域-多条件规则: {multi_cond_count} 条")
        print(f"  无作用域-全局规则: {len(unscoped_rules)} 条")

        all_results = []

        # 1. 执行有作用域的规则（直接执行）
        if scoped_rules:
            print(f"[环节二 - 规则执行] 开始执行 {len(scoped_rules)} 条有作用域规则（单列 + 多条件）")
            scoped_results = self.rule_executor.execute_rules(scoped_rules)
            all_results.extend(scoped_results)

        # 2. 执行无作用域的规则（多表批量执行）
        if unscoped_rules:
            print(f"[环节二 - 规则执行] 开始批量执行 {len(unscoped_rules)} 条无作用域规则（全局规则）")
            multi_results = self.execute_multi_table(report, unscoped_rules)
            # execute_multi_table 返回原始结果列表，直接 extend
            all_results.extend(multi_results)

        # 3. 如果强制多表模式且没有无作用域规则，则对所有规则启用
        if multi_table_mode and not unscoped_rules and scoped_rules:
            print(f"[环节二 - 规则执行] 强制多表模式，执行 {len(scoped_rules)} 条规则")
            multi_results = self.execute_multi_table(report, scoped_rules)
            all_results.extend(multi_results)

        # 4. 基础空值检测（不写 rule_execution_results，只存 JSONB）
        basic_audit_data = None
        if include_basic_audit:
            print(f"[环节二 - 规则执行] 开始执行基础空值检测...")
            basic_audit_data = self.run_basic_audit(str(report.id))

        # 5. 保存执行结果到数据库（统一在末尾 commit）
        for result in all_results:
            if not result.id:  # 新结果需要添加
                result.report_id = report.id
                db.session.add(result)

        # 5. 计算汇总统计
        stats = self.compute_quality_from_results(all_results)
        quality_score = stats['quality_score']
        grade = stats['grade']
        summary = stats['summary']
        summary['scoped_rules'] = len(scoped_rules)
        summary['unscoped_rules'] = len(unscoped_rules)

        # 6. 更新报告（写入 JSONB 字段前统一做序列化清洗，避免 datetime/UUID 等类型无法被序列化）
        report.quality_score = quality_score
        report.grade = grade
        report.rules_applied = len(all_results)
        report.summary = _sanitize_for_json(summary)
        report.basic_audit_result = _sanitize_for_json(basic_audit_data)
        report.details = _sanitize_for_json({
            'execution_results': [r.to_dict() for r in all_results],
            'execution_time': datetime.now().isoformat(),
            'multi_table_mode': len(unscoped_rules) > 0
        })

        db.session.commit()

        return report

    def execute_only(
        self,
        report_id: str,
        rules: List[GovernanceRule],
        include_basic_audit: bool = False,
        multi_table_mode: bool = False
    ) -> List[RuleExecutionResult]:
        """执行治理规则（仅执行，不生成报告）

        仅遍历规则执行 SQL，将结果写入 rule_execution_results 表。
        不更新 governance_reports 表的质量评分等字段。

        Args:
            report_id: 关联的报告ID（由调用方预创建）
            rules: 要执行的规则列表
            include_basic_audit: 是否包含基础空值检测
            multi_table_mode: 是否强制启用多表批量执行模式

        Returns:
            RuleExecutionResult 对象列表
        """
        scoped_rules = []
        unscoped_rules = []
        for rule in rules:
            if rule.target_table:
                scoped_rules.append(rule)
            else:
                unscoped_rules.append(rule)

        # 统计各类规则数量
        single_cond_count = sum(1 for r in scoped_rules if not r.conditions_config)
        multi_cond_count = sum(1 for r in scoped_rules if r.conditions_config)
        print(f"[环节二 - 规则执行] 规则分类完成:")
        print(f"  有作用域-单列规则: {single_cond_count} 条")
        print(f"  有作用域-多条件规则: {multi_cond_count} 条")
        print(f"  无作用域-全局规则: {len(unscoped_rules)} 条")

        all_results = []

        if scoped_rules:
            scoped_results = self.rule_executor.execute_rules(scoped_rules)
            all_results.extend(scoped_results)

        if unscoped_rules:
            multi_results = self._execute_multi_table_no_report(
                unscoped_rules, report_id
            )
            all_results.extend(multi_results)

        if multi_table_mode and not unscoped_rules and scoped_rules:
            multi_results = self._execute_multi_table_no_report(
                scoped_rules, report_id
            )
            all_results.extend(multi_results)

        # 基础空值检测（不写 rule_execution_results，只存 JSONB）
        basic_audit_data = None
        if include_basic_audit:
            print(f"[环节二 - 规则执行] 开始执行基础空值检测...")
            basic_audit_data = self.run_basic_audit(report_id)

        # 保存结果到数据库
        for result in all_results:
            if not result.id:
                result.report_id = report_id
                db.session.add(result)

        db.session.commit()
        return all_results, basic_audit_data

    def _execute_multi_table_no_report(
        self,
        rules: List[GovernanceRule],
        report_id: str
    ) -> List[RuleExecutionResult]:
        """多表批量执行（不更新报告），内部使用临时 report_id 占位"""
        # 构造一个最小化 report 对象供 execute_multi_table 内部使用
        class _FakeReport:
            def __init__(self, rid):
                self.id = rid
        fake_report = _FakeReport(report_id)
        results = self.execute_multi_table(fake_report, rules)
        return results

    @staticmethod
    def compute_quality_from_results(results: List[RuleExecutionResult]) -> dict:
        """根据执行结果计算质量评分和统计信息

        质量分计算策略（按失败率加权）：
        - status='passed' 的规则：贡献 100 分
        - status='failed' 的规则：贡献 (100 - failed_rate) 分
        - status='error' 的规则：贡献 0 分
        - critical 级别且失败的规则：额外扣 5 分/条

        Args:
            results: RuleExecutionResult 对象列表

        Returns:
            {
                'quality_score': float,
                'grade': str,
                'summary': dict,
                'scoped_rules': int,
                'unscoped_rules': int
            }
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == 'passed')
        failed = sum(1 for r in results if r.status == 'failed')
        errors = sum(1 for r in results if r.status == 'error')

        if total == 0:
            quality_score = 100.0
            grade = '优秀'
        else:
            # 按失败率加权计算质量分
            total_score = 0.0
            for r in results:
                if r.status == 'passed':
                    total_score += 100.0
                elif r.status == 'failed':
                    # failed_rate 本身是百分比值（如 11.11 表示 11.11%）
                    # 质量贡献分 = 100 - 失败率
                    failed_rate_val = float(r.failed_rate) if r.failed_rate else 0.0
                    total_score += max(0, 100.0 - failed_rate_val)
                else:  # error
                    total_score += 0.0

            pass_rate = total_score / total

            # critical 级别且失败的规则额外扣分
            critical_count = sum(
                1 for r in results
                if r.severity == 'critical' and r.status == 'failed'
            )
            if critical_count > 0:
                pass_rate = max(0, pass_rate - critical_count * 5)

            quality_score = max(0, min(100, pass_rate))

            if quality_score >= 95:
                grade = '优秀'
            elif quality_score >= 85:
                grade = '良好'
            elif quality_score >= 70:
                grade = '一般'
            elif quality_score >= 60:
                grade = '较差'
            else:
                grade = '差'

        return {
            'quality_score': quality_score,
            'grade': grade,
            'summary': {
                'total_rules': total,
                'passed_rules': passed,
                'failed_rules': failed,
                'error_rules': errors,
                'quality_score': quality_score,
                'grade': grade,
            },
        }


def execute_audit(datasource_id: str,
                  user_id: str,
                  library_ids: List[str] = None,
                  rule_ids: List[str] = None,
                  tables: List[str] = None,
                  include_basic_audit: bool = False) -> Dict[str, Any]:
    """执行治理盘点的便捷函数

    Args:
        datasource_id: 数据源ID
        user_id: 用户ID
        library_ids: 规则库ID列表
        rule_ids: 规则ID列表
        tables: 指定的表列表（可选）
        include_basic_audit: 是否包含基础空值检测

    Returns:
        执行结果字典
    """
    from models.datasource import Datasource

    # 1. 获取数据源信息
    datasource = Datasource.query.filter_by(id=datasource_id, user_id=user_id).first()
    if not datasource:
        raise ValueError(f"数据源不存在: {datasource_id}")

    # 2. 构建连接信息
    connect_info = {
        'dbType': datasource.db_type,
        'host': datasource.host,
        'port': datasource.port,
        'database': datasource.database_name,
        'username': datasource.username,
        'password': datasource.password,
        'schema': getattr(datasource, 'schema', None)
    }

    # 3. 获取引擎
    from controllers.datasource.database_schema_extractor import build_db_url_from_json, _to_raw_conn_str
    connection_string_URL = build_db_url_from_json(connect_info)
    connection_string_str = _to_raw_conn_str(connection_string_URL)

    # 实际获取 engine 对象（使用 datasource.db_type 以便 KingBase/OceanBase 特殊处理生效）
    from controllers.datasource.database_schema_extractor import get_db_engine
    engine = get_db_engine(connection_string_str, db_type=datasource.db_type)

    # 4. 获取规则（只获取当前数据源下的规则）
    rules_query = GovernanceRule.query.join(
        GovernanceRule.library
    ).filter(
        GovernanceRule.enabled == True,
        GovernanceRule.library.has(datasource_id=datasource_id),
        GovernanceRule.library.has(created_by=user_id)
    )

    if library_ids:
        rules_query = rules_query.filter(GovernanceRule.library_id.in_(library_ids))

    if rule_ids:
        rules_query = rules_query.filter(GovernanceRule.id.in_(rule_ids))

    rules = rules_query.all()

    # 5. 过滤指定表
    if tables:
        rules = [r for r in rules if not r.target_table or r.target_table in tables]

    # 6. 创建报告
    report = GovernanceReport(
        user_id=user_id,
        datasource_id=datasource_id,
        report_name=f"治理盘点报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        scope_tables=tables,
        include_quality=True,
        include_relationship=False
    )
    db.session.add(report)
    db.session.commit()

    # 7. 执行规则
    db_name = connect_info.get('database', '')
    schema_name = connect_info.get('schema')
    executor = AuditExecutor(engine, datasource.db_type, db_name, schema_name)
    executor.execute(report, rules, include_basic_audit)

    return {
        'report_id': str(report.id),
        'quality_score': float(report.quality_score) if report.quality_score else 0,
        'grade': report.grade,
        'summary': report.summary
    }
