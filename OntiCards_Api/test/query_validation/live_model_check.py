"""Opt-in smoke test using synthetic data and a real model; never imports app.py.

Run in an API container with --server-config to read ONLY the configured model,
or set QUERY_TEST_API_KEY / QUERY_TEST_API_URL / QUERY_TEST_MODEL. No business
tables are queried. SQL uses temporary tables on one connection and rolls back.
SQLite is the default; --database postgresql requires a test DB URL or server config.
"""
import argparse
import contextlib
import json
import os
import sys
import time

import requests
from sqlalchemy import create_engine, text

import conftest  # isolate query modules from application startup
from test_completeness import SQL
from controllers.query.query_validation import (
    plan_query, ensure_valid_sql, QueryValidationError, DISPLAY_RULES,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server-config', action='store_true')
    parser.add_argument('--database', choices=['sqlite', 'postgresql'], default='sqlite')
    parser.add_argument('--case', default=os.getenv('QUERY_TEST_CASE'))
    args = parser.parse_args()
    database_url = os.getenv('QUERY_TEST_DATABASE_URL')
    key = os.getenv('QUERY_TEST_API_KEY')
    url = os.getenv('QUERY_TEST_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    model = os.getenv('QUERY_TEST_MODEL', 'qwen3.7-max')
    if args.server_config:
        # Config only: no create_app, scheduler, user seeding or data-card changes.
        sys.path.append('/onticards_api')
        from config import Config
        config = Config()
        database_url = database_url or config.SQLALCHEMY_DATABASE_URI
        engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            row = connection.execute(text("SELECT model_api_key, url, model_name FROM model_config WHERE model_class='base' LIMIT 1")).mappings().one()
            key, url, model = row['model_api_key'], row['url'], row['model_name']
        engine.dispose()
    if not key:
        raise SystemExit('Set QUERY_TEST_API_KEY or use --server-config')
    if not url.rstrip('/').endswith('/chat/completions'):
        url = url.rstrip('/') + '/chat/completions'
    calls = 0
    def llm(prompt, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 16:
            raise RuntimeError('Smoke-test model-call limit reached')
        started = time.monotonic()
        response = requests.post(url, headers={'Authorization': 'Bearer ' + key},
                                 json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                                       'temperature': 0, 'stream': False}, timeout=120)
        if response.status_code != 200:
            raise RuntimeError('Model HTTP status ' + str(response.status_code))
        data = response.json()
        if os.getenv('QUERY_TEST_TRACE'):
            with open(os.environ['QUERY_TEST_TRACE'], 'a', encoding='utf-8') as trace:
                trace.write(json.dumps({'prompt': prompt, 'content': data['choices'][0]['message']['content']}, ensure_ascii=False) + '\n')
        usage = data.get('usage', {})
        usage['generation_ms'] = int((time.monotonic() - started) * 1000)
        return data['choices'][0]['message']['content'], usage

    tables = [
        {'table_name': 'projects', 'columns': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'TEXT', 'comment': '项目名称'},
         {'name': 'stage', 'type': 'TEXT', 'comment': '阶段 cxt_slwc:设立完成； other:其他阶段'},
         {'name': 'company_id', 'type': 'INTEGER', 'comment': '关联 companies.id'},
         {'name': 'currency_id', 'type': 'BYTEA' if args.database == 'postgresql' else 'BLOB', 'comment': '关联 currencies.id，展示币种名称'},
         {'name': 'industry_id', 'type': 'INTEGER', 'comment': '关联 industries.id'},
         {'name': 'source', 'type': 'TEXT', 'comment': '项目来源 source_:自主开发； other_:其他来源'}]},
        {'table_name': 'people', 'columns': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'TEXT', 'comment': '人员姓名'}]},
        {'table_name': 'team', 'columns': [{'name': 'project_id', 'type': 'INTEGER'}, {'name': 'person_id', 'type': 'INTEGER'},
         {'name': 'role', 'type': 'TEXT', 'comment': '角色 a_:A角； b_:B角'}, {'name': 'ratio', 'type': 'DECIMAL', 'comment': '分配系数'}],
         'foreign_keys': [{'column': 'project_id', 'ref_table': 'projects', 'ref_column': 'id'}, {'column': 'person_id', 'ref_table': 'people', 'ref_column': 'id'}]},
        {'table_name': 'companies', 'columns': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'TEXT', 'comment': '企业名称'}]},
        {'table_name': 'currencies', 'columns': [{'name': 'id', 'type': 'BYTEA' if args.database == 'postgresql' else 'BLOB'}, {'name': 'name', 'type': 'TEXT', 'comment': '币种名称'}]},
        {'table_name': 'industries', 'columns': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'TEXT', 'comment': '行业名称'}]}]
    if args.database == 'postgresql' and not database_url:
        raise SystemExit('Set QUERY_TEST_DATABASE_URL or use --server-config for PostgreSQL')
    engine = create_engine('sqlite://' if args.database == 'sqlite' else database_url)
    # TEMP tables and a fixed connection prevent any writes to business tables.
    connection = engine.connect()
    transaction = connection.begin()
    try:
        if args.database == 'postgresql':
            connection.execute(text('SET LOCAL search_path TO pg_temp'))
        raw_type = 'BYTEA' if args.database == 'postgresql' else 'BLOB'
        for ddl in [
            f'CREATE TEMP TABLE projects(id INTEGER, name TEXT, stage TEXT, company_id INTEGER, currency_id {raw_type}, industry_id INTEGER, source TEXT)',
            'CREATE TEMP TABLE people(id INTEGER, name TEXT)',
            'CREATE TEMP TABLE team(project_id INTEGER, person_id INTEGER, role TEXT, ratio DECIMAL)',
            'CREATE TEMP TABLE companies(id INTEGER, name TEXT)',
            f'CREATE TEMP TABLE currencies(id {raw_type}, name TEXT)',
            'CREATE TEMP TABLE industries(id INTEGER, name TEXT)',
        ]:
            connection.execute(text(ddl))
        currency = bytes.fromhex('ff0123')
        connection.execute(text("INSERT INTO projects VALUES (1,'测试甲','cxt_slwc',1,:currency,1,'source_'),(2,'测试乙','cxt_slwc',1,:currency,2,'source_'),(3,'测试丙','other',1,:currency,1,'source_'),(4,'无团队','cxt_slwc',1,:currency,1,'source_')"), {'currency': currency})
        connection.execute(text("INSERT INTO people VALUES (1,'测试成员甲'),(2,'其他人')"))
        connection.execute(text("INSERT INTO team VALUES (1,1,'a_',0),(2,2,'b_',1),(3,1,'a_',1)"))
        connection.execute(text("INSERT INTO companies VALUES (1,'测试企业')"))
        connection.execute(text("INSERT INTO currencies VALUES (:currency,'人民币')"), {'currency': currency})
        connection.execute(text("INSERT INTO industries VALUES (1,'信息技术'),(2,'其他行业')"))
        class FixtureConnection:
            def connect(self):
                return contextlib.nullcontext(connection)
        run_sql = conftest.endpoint_namespace('query_by_datacards_agg.py')['run_sql_safe_new']
        reports = []
        cases = [
            ('missing_person', '查询测试成员甲参与且阶段为设立完成的项目，只输出项目名称。', SQL.replace("u.name='测试成员甲' AND ", ''), ['项目名称']),
            ('enum_and_zero', '查询测试成员甲参与且阶段为设立完成的项目，只输出项目名称、角色、分配系数。角色显示中文。',
             SQL.replace('p.name AS 项目名称', 'p.name AS 项目名称, t.role AS 角色, t.ratio AS 分配系数'), ['项目名称','角色','分配系数']),
            ('industry_currency_eight_columns', '查询信息技术行业中有团队记录且阶段为设立完成的项目。只输出项目名称、企业名称、角色、分配系数、项目阶段、币种、项目来源、行业。枚举和币种显示中文名称。',
             "SELECT p.name AS 项目名称, c.name AS 企业名称, t.role AS 角色, t.ratio AS 分配系数, p.stage AS 项目阶段, p.currency_id AS 币种, p.source AS 项目来源, i.name AS 行业 FROM projects p LEFT JOIN team t ON p.id=t.project_id LEFT JOIN companies c ON c.id=p.company_id LEFT JOIN industries i ON i.id=p.industry_id WHERE p.stage='cxt_slwc'",
             ['项目名称','企业名称','角色','分配系数','项目阶段','币种','项目来源','行业']),
        ]
        for case, question, initial_sql, labels in cases:
            if args.case and args.case != case:
                continue
            started = time.monotonic()
            plan = plan_query(question, question, llm)
            plan['cluster_count'] = 1
            for table in tables:
                table['_query_contract'] = plan
            generation_prompt = DISPLAY_RULES + '\n原始问题：' + question + '\n数据库：' + args.database + '\n白名单：' + json.dumps([{k:v for k,v in t.items() if not k.startswith('_')} for t in tables], ensure_ascii=False)
            try:
                sql, validation, _ = ensure_valid_sql(initial_sql, args.database, tables, llm, generation_prompt)
                columns = []
                rows, _, _ = run_sql(FixtureConnection(), sql, tables, args.database, columns_out=columns)
                assert columns == labels
                assert len(rows) == 1 and list(rows[0]) == labels
                if case == 'enum_and_zero':
                    assert rows[0]['角色'] == 'A角' and rows[0]['分配系数'] == 0
                if case == 'industry_currency_eight_columns':
                    assert rows[0] == dict(zip(labels, ['测试甲','测试企业','A角',0,'设立完成','人民币','自主开发','信息技术']))
                reports.append({'case': case, 'database': args.database, 'status': 'passed', 'synthetic_rows': len(rows), 'columns': labels,
                                'repairs': validation['repairs'], 'elapsed_seconds': round(time.monotonic()-started, 2)})
            except QueryValidationError as exc:
                reports.append({'case': case, 'status': 'blocked', 'issues': exc.report['issues']})
            print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
    print(json.dumps({'model': model, 'calls': calls, 'results': reports}, ensure_ascii=False), flush=True)
    if any(report['status'] != 'passed' for report in reports):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
