"""
@File: init.py
@Description: 全局蓝图注册
@Author: 韩小豪 849631113@qq.com
@Create: 2025-10-27 14:56
@Update: 2026-02-12 重构：定向盘点(target_inventory)和全域盘点(global_inventory)模块分离
@Update: 2026-03-30 新增：查询历史(query_history)、监控(monitoring)、系统配置(system_config)模块
@Update: 2026-06-01 新增：数据治理(governance)模块
"""

from controllers.apikey.api_keys_api import api_keys_api
from controllers.changelog.version_update_log_api import version_update_log_api
from controllers.datacard.data_card_tool import datacard_tool_bp
from controllers.datasource.dataaudit.data_audit import bp_data_audit
from controllers.datasource.database_schema_extractor import extract_schema_from_db
from controllers.datasource.datasource_tool import datasource_tool_bp
from controllers.datasource.filedfill.extract_field_data_by_excle import extract_field_data_excel
from controllers.model_config.model_config_api import model_config_api
from controllers.query.query_by_datacards_agg import query_by_datacards_agg
from controllers.query.query_by_datacards_agg_plugin import query_by_datacards_agg_plugin
from controllers.user.userManagement import user_bp
from controllers.user.user_group import user_group_bp

# 定向盘点模块（用户手动选择表进行字段注释推荐和表关系确认）
from controllers.target_inventory.target_inventory_tool import target_inventory_bp
from controllers.target_inventory.dict_file_api import dict_file_bp

# 全域盘点模块（真正的全域盘点，多数据源表关系发现和关系卡片生成）
from controllers.global_inventory.global_inventory_tool import global_inventory_bp

# 查询历史与监控模块
from controllers.query_history.query_history_api import query_history_api
from controllers.monitoring.monitoring_api import monitoring_api
from controllers.system_config.system_config_api import system_config_api
from controllers.prompt_config.prompt_config_api import prompt_config_api

# 业务术语库模块
from controllers.business_term.business_term_api import business_term_api

# SSO单点登录模块
from controllers.sso.sso_api import sso_bp

# 数据治理模块
from controllers.governance.governance_api import governance_api

# 注册所有蓝图
def init_app(app):
    app.register_blueprint(user_bp, url_prefix='/console/api')
    app.register_blueprint(user_group_bp, url_prefix='/console/api')

    # 多数据源对接模块
    app.register_blueprint(extract_schema_from_db, url_prefix='/console/api')
    app.register_blueprint(extract_field_data_excel, url_prefix='/console/api')
    app.register_blueprint(datasource_tool_bp, url_prefix='/console/api')
    app.register_blueprint(datacard_tool_bp, url_prefix='/console/api')
    app.register_blueprint(query_by_datacards_agg, url_prefix='/console/api')
    app.register_blueprint(version_update_log_api, url_prefix='/console/api')
    app.register_blueprint(bp_data_audit, url_prefix='/console/api')
    app.register_blueprint(model_config_api, url_prefix='/console/api')
    app.register_blueprint(query_by_datacards_agg_plugin, url_prefix='/console/api')
    app.register_blueprint(api_keys_api, url_prefix='/console/api')

    # 定向盘点模块（原全域盘点，用户手动选择表）
    app.register_blueprint(target_inventory_bp, url_prefix='/console/api/target_inventory')
    app.register_blueprint(dict_file_bp, url_prefix='/console/api/target_inventory')  # 字典文件接口

    # 全域盘点模块（真正的全域盘点，多数据源表关系发现）
    app.register_blueprint(global_inventory_bp, url_prefix='/console/api/global_inventory')

    # 查询历史与监控模块
    app.register_blueprint(query_history_api, url_prefix='/console/api/query_history')
    app.register_blueprint(monitoring_api, url_prefix='/console/api/monitoring')
    app.register_blueprint(system_config_api, url_prefix='/console/api/system_config')
    app.register_blueprint(prompt_config_api, url_prefix='/console/api/prompt_config')

    # 业务术语库模块
    app.register_blueprint(business_term_api, url_prefix='/console/api/business_term')

    # SSO单点登录模块（独立入口，不受其他模块影响）
    app.register_blueprint(sso_bp, url_prefix='/sso')

    # 数据治理模块
    app.register_blueprint(governance_api, url_prefix='/console/api/governance')