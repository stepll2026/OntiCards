# -*- coding:utf-8 -*-
"""
@File: test_dialect_adapter.py
@Description: DialectAdapter 单元测试 - 标识符引用及表引用回归测试
@Create: 2026-10-25

覆盖范围：
1. Oracle/Trino/DM 标识符引用修复验证（Issue #36）
2. 带 schema 的表引用（quote_table_reference）
3. 未受影响方言的回归测试（PostgreSQL/MySQL/MSSQL/SQLite/KingBase/OceanBase/MariaDB）
4. 边界情况：空字符串、None schema

运行方式：
    python -m pytest controllers/governance/test_dialect_adapter.py -v
    或独立运行：
    python controllers/governance/test_dialect_adapter.py
"""

import importlib.util
import os
import sys
import unittest

# 支持独立运行和 pytest 两种模式
_MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dialect_adapter.py')
_spec = importlib.util.spec_from_file_location('dialect_adapter', _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DialectAdapter = _mod.DialectAdapter


class TestOracleIdentifierQuoting(unittest.TestCase):
    """Oracle 方言标识符引用测试（Issue #36 修复验证）"""

    def setUp(self):
        self.adapter = DialectAdapter('oracle')

    def test_quote_identifier_simple(self):
        """Oracle: 简单标识符引用不应包含多余右括号"""
        result = self.adapter.quote_identifier('users')
        self.assertEqual(result, '"users"')

    def test_quote_identifier_no_trailing_paren(self):
        """Oracle: 引用结果不应以 ) 结尾"""
        result = self.adapter.quote_identifier('users')
        self.assertFalse(result.endswith(')'), f"Expected no trailing paren, got {result!r}")

    def test_quote_table_reference_with_schema(self):
        """Oracle: schema.table 引用格式正确"""
        result = self.adapter.quote_table_reference('users', 'business')
        self.assertEqual(result, '"business"."users"')

    def test_quote_table_reference_without_schema(self):
        """Oracle: 无 schema 时只返回带引号的表名"""
        result = self.adapter.quote_table_reference('users')
        self.assertEqual(result, '"users"')

    def test_quote_table_column(self):
        """Oracle: 同时引用表名和列名"""
        table, col = self.adapter.quote_table_column('orders', 'amount')
        self.assertEqual(table, '"orders"')
        self.assertEqual(col, '"amount"')


class TestTrinoIdentifierQuoting(unittest.TestCase):
    """Trino 方言标识符引用测试（Issue #36 修复验证）"""

    def setUp(self):
        self.adapter = DialectAdapter('trino')

    def test_quote_identifier_simple(self):
        """Trino: 简单标识符引用不应包含多余右括号"""
        result = self.adapter.quote_identifier('users')
        self.assertEqual(result, '"users"')

    def test_quote_identifier_no_trailing_paren(self):
        """Trino: 引用结果不应以 ) 结尾"""
        result = self.adapter.quote_identifier('users')
        self.assertFalse(result.endswith(')'), f"Expected no trailing paren, got {result!r}")

    def test_quote_table_reference_with_schema(self):
        """Trino: schema.table 引用格式正确"""
        result = self.adapter.quote_table_reference('users', 'business')
        self.assertEqual(result, '"business"."users"')

    def test_quote_table_reference_without_schema(self):
        """Trino: 无 schema 时只返回带引号的表名"""
        result = self.adapter.quote_table_reference('users')
        self.assertEqual(result, '"users"')


class TestDMIdentifierQuoting(unittest.TestCase):
    """达梦 DM 方言标识符引用测试（Issue #36 修复验证）"""

    def setUp(self):
        self.adapter = DialectAdapter('dm')

    def test_quote_identifier_simple(self):
        """DM: 简单标识符引用不应包含多余右括号"""
        result = self.adapter.quote_identifier('users')
        self.assertEqual(result, '"users"')

    def test_quote_identifier_no_trailing_paren(self):
        """DM: 引用结果不应以 ) 结尾"""
        result = self.adapter.quote_identifier('users')
        self.assertFalse(result.endswith(')'), f"Expected no trailing paren, got {result!r}")

    def test_quote_table_reference_with_schema(self):
        """DM: schema.table 引用格式正确"""
        result = self.adapter.quote_table_reference('users', 'business')
        self.assertEqual(result, '"business"."users"')

    def test_quote_table_reference_without_schema(self):
        """DM: 无 schema 时只返回带引号的表名"""
        result = self.adapter.quote_table_reference('users')
        self.assertEqual(result, '"users"')


class TestUnaffectedDialectsRegression(unittest.TestCase):
    """未受影响方言的回归测试，确保修复不引入副作用"""

    def test_postgresql_quote_identifier(self):
        adapter = DialectAdapter('postgresql')
        self.assertEqual(adapter.quote_identifier('users'), '"users"')

    def test_postgresql_quote_table_reference(self):
        adapter = DialectAdapter('postgresql')
        self.assertEqual(adapter.quote_table_reference('users', 'public'), '"public"."users"')

    def test_mysql_quote_identifier(self):
        adapter = DialectAdapter('mysql')
        self.assertEqual(adapter.quote_identifier('users'), '`users`')

    def test_mysql_quote_table_reference(self):
        adapter = DialectAdapter('mysql')
        self.assertEqual(adapter.quote_table_reference('users', 'mydb'), '`mydb`.`users`')

    def test_mssql_quote_identifier(self):
        adapter = DialectAdapter('mssql')
        self.assertEqual(adapter.quote_identifier('users'), '[users]')

    def test_mssql_quote_table_reference(self):
        adapter = DialectAdapter('mssql')
        self.assertEqual(adapter.quote_table_reference('users', 'dbo'), '[dbo].[users]')

    def test_sqlite_quote_identifier(self):
        adapter = DialectAdapter('sqlite')
        self.assertEqual(adapter.quote_identifier('users'), '"users"')

    def test_sqlite_quote_table_reference(self):
        adapter = DialectAdapter('sqlite')
        self.assertEqual(adapter.quote_table_reference('users', 'main'), '"main"."users"')

    def test_kingbase_quote_identifier(self):
        adapter = DialectAdapter('kingbase')
        self.assertEqual(adapter.quote_identifier('users'), '"users"')

    def test_kingbase_quote_table_reference(self):
        adapter = DialectAdapter('kingbase')
        self.assertEqual(adapter.quote_table_reference('users', 'public'), '"public"."users"')

    def test_oceanbase_quote_identifier(self):
        adapter = DialectAdapter('oceanbase')
        self.assertEqual(adapter.quote_identifier('users'), '`users`')

    def test_oceanbase_quote_table_reference(self):
        adapter = DialectAdapter('oceanbase')
        self.assertEqual(adapter.quote_table_reference('users', 'mydb'), '`mydb`.`users`')

    def test_mariadb_quote_identifier(self):
        adapter = DialectAdapter('mariadb')
        self.assertEqual(adapter.quote_identifier('users'), '`users`')

    def test_mariadb_quote_table_reference(self):
        adapter = DialectAdapter('mariadb')
        self.assertEqual(adapter.quote_table_reference('users', 'mydb'), '`mydb`.`users`')


class TestEdgeCases(unittest.TestCase):
    """边界情况测试"""

    def test_empty_identifier(self):
        """空字符串标识符应原样返回"""
        adapter = DialectAdapter('oracle')
        self.assertEqual(adapter.quote_identifier(''), '')

    def test_none_schema_table_reference(self):
        """schema=None 时应只返回表名"""
        adapter = DialectAdapter('oracle')
        self.assertEqual(adapter.quote_table_reference('users', None), '"users"')

    def test_whitespace_only_schema(self):
        """空白 schema 应视为无 schema"""
        adapter = DialectAdapter('oracle')
        self.assertEqual(adapter.quote_table_reference('users', '   '), '"users"')

    def test_all_affected_dialects_consistent(self):
        """Oracle/Trino/DM 三个受影响方言的引用行为应一致"""
        for db_type in ('oracle', 'trino', 'dm'):
            adapter = DialectAdapter(db_type)
            with self.subTest(db_type=db_type):
                self.assertEqual(adapter.quote_identifier('test_col'), '"test_col"')
                self.assertEqual(
                    adapter.quote_table_reference('test_table', 'test_schema'),
                    '"test_schema"."test_table"'
                )


if __name__ == '__main__':
    unittest.main(verbosity=2)
