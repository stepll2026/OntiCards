# -*- coding:utf-8 -*-
import os

import dotenv

dotenv.load_dotenv()

DEFAULTS = {
    # 数据库配置
    'DB_USERNAME': 'postgres',
    'DB_PASSWORD': 'admin123',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
    'DB_DATABASE': 'Snaildy',
    'DB_CHARSET': '',
    
    # Redis 配置
    'REDIS_HOST': '119.29.91.37',
    'REDIS_PORT': '6379',
    'REDIS_DB': '0',
    'REDIS_USE_SSL': 'False',
    
    # URL 前缀配置
    'OAUTH_REDIRECT_PATH': '/console/api/oauth/authorize',
    'OAUTH_REDIRECT_INDEX_PATH': '/',
    'CONSOLE_WEB_URL': '',
    'CONSOLE_API_URL': '',
    'SERVICE_API_URL': '',
    'APP_WEB_URL': '',
    'APP_API_URL': '',
    'FILES_URL': '',
    
    # 文件存储配置
    'STORAGE_TYPE': 'local',
    'STORAGE_LOCAL_PATH': 'storage',
    
    # 环境配置
    'DEPLOY_ENV': 'PRODUCTION',
    
    # SQLAlchemy 配置
    'SQLALCHEMY_POOL_SIZE': 30,
    'SQLALCHEMY_POOL_RECYCLE': 3600,
    'SQLALCHEMY_ECHO': 'False',
    
    # Sentry 配置
    'SENTRY_TRACES_SAMPLE_RATE': 1.0,
    'SENTRY_PROFILES_SAMPLE_RATE': 1.0,
    
    # Weaviate 配置
    'WEAVIATE_GRPC_ENABLED': 'True',
    'WEAVIATE_BATCH_SIZE': 100,
    
    # Qdrant 配置
    'QDRANT_CLIENT_TIMEOUT': 20,
    
    # 日志配置
    'LOG_LEVEL': 'INFO',
    
    # OpenAI/Claude API 配置
    'HOSTED_OPENAI_QUOTA_LIMIT': 200,
    'HOSTED_OPENAI_ENABLED': 'False',
    'HOSTED_OPENAI_PAID_ENABLED': 'False',
    'HOSTED_AZURE_OPENAI_ENABLED': 'False',
    'HOSTED_AZURE_OPENAI_QUOTA_LIMIT': 200,
    'HOSTED_ANTHROPIC_QUOTA_LIMIT': 600000,
    'HOSTED_ANTHROPIC_ENABLED': 'False',
    'HOSTED_ANTHROPIC_PAID_ENABLED': 'False',
    
    # 用户邀请配置
    'INVITE_EXPIRY_HOURS': 72,
    
    # 文件上传配置
    'UPLOAD_FILE_SIZE_LIMIT': 15,
    'UPLOAD_FILE_BATCH_LIMIT': 5,
    'UPLOAD_IMAGE_FILE_SIZE_LIMIT': 10,
    
    # 向量搜索配置（数据卡片智能召回 + 重排序优化）
    'VECTOR_SEARCH_DISTANCE_THRESHOLD': '0.65',
    'VECTOR_SEARCH_QUERY_LIMIT': '80',
    'VECTOR_SEARCH_MIN_RESULTS': '2',
    'VECTOR_SEARCH_MAX_RESULTS': '20',
    'VECTOR_SEARCH_ADAPTIVE_MODE': 'smart',
    'VECTOR_SEARCH_SCORE_THRESHOLD': '0.35',
    'VECTOR_SEARCH_GAP_THRESHOLD': '0.15',

    # LibreOffice 容器服务配置（数据治理报告导出）
    'LIBREOFFICE_SERVICE_URL': 'http://localhost:3000',
    'LIBREOFFICE_SERVICE_TIMEOUT': '120',
    'LIBREOFFICE_SERVICE_ENABLED': 'true',
}


def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


# Weaviate 连接配置
Weaviate_url = get_env('WEAVIATE_URL')


def get_bool_env(key):
    return get_env(key).lower() == 'true'


def get_cors_allow_origins(env, default):
    cors_allow_origins = []
    if get_env(env):
        for origin in get_env(env).split(','):
            cors_allow_origins.append(origin)
    else:
        cors_allow_origins = [default]

    return cors_allow_origins


class Config:
    """Application configuration class."""

    def __init__(self):
        # ------------------------
        # General Configurations.
        # ------------------------
        self.CURRENT_VERSION = "0.4.4"
        self.EDITION = "SELF_HOSTED"
        self.DEPLOY_ENV = get_env('DEPLOY_ENV')
        self.TESTING = False
        self.LOG_LEVEL = get_env('LOG_LEVEL')

        # The backend URL prefix of the console API.
        self.CONSOLE_API_URL = get_env('CONSOLE_URL') if get_env('CONSOLE_URL') else get_env('CONSOLE_API_URL')

        # The front-end URL prefix of the console web.
        self.CONSOLE_WEB_URL = get_env('CONSOLE_URL') if get_env('CONSOLE_URL') else get_env('CONSOLE_WEB_URL')

        # WebApp API backend Url prefix.
        self.APP_API_URL = get_env('APP_URL') if get_env('APP_URL') else get_env('APP_API_URL')

        # WebApp Url prefix.
        self.APP_WEB_URL = get_env('APP_URL') if get_env('APP_URL') else get_env('APP_WEB_URL')

        # Service API Url prefix.
        self.SERVICE_API_URL = get_env('API_URL') if get_env('API_URL') else get_env('SERVICE_API_URL')

        # File preview or download Url prefix.
        self.FILES_URL = get_env('FILES_URL') if get_env('FILES_URL') else self.CONSOLE_API_URL

        # Fallback Url prefix.
        self.CONSOLE_URL = get_env('CONSOLE_URL')
        self.API_URL = get_env('API_URL')
        self.APP_URL = get_env('APP_URL')

        # Your App secret key will be used for securely signing the session cookie
        self.SECRET_KEY = get_env('SECRET_KEY')

        # cors settings
        self.CONSOLE_CORS_ALLOW_ORIGINS = get_cors_allow_origins(
            'CONSOLE_CORS_ALLOW_ORIGINS', self.CONSOLE_WEB_URL)
        self.WEB_API_CORS_ALLOW_ORIGINS = get_cors_allow_origins(
            'WEB_API_CORS_ALLOW_ORIGINS', '*')

        # ------------------------
        # Database Configurations.
        # ------------------------
        db_credentials = {
            key: get_env(key) for key in
            ['DB_USERNAME', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_CHARSET']
        }
        db_extras = f"?client_encoding={db_credentials['DB_CHARSET']}" if db_credentials['DB_CHARSET'] else ""

        self.SQLALCHEMY_DATABASE_URI = f"postgresql://{db_credentials['DB_USERNAME']}:{db_credentials['DB_PASSWORD']}@{db_credentials['DB_HOST']}:{db_credentials['DB_PORT']}/{db_credentials['DB_DATABASE']}{db_extras}"
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(get_env('SQLALCHEMY_POOL_SIZE')),
            'pool_recycle': int(get_env('SQLALCHEMY_POOL_RECYCLE')),
            'pool_pre_ping': True,
            'pool_timeout': 30,
            'connect_args': {
                'options': '-cTimeZone=Asia/Shanghai'
            }
        }

        self.SQLALCHEMY_ECHO = get_bool_env('SQLALCHEMY_ECHO')

        # ------------------------
        # Redis Configurations.
        # ------------------------
        self.REDIS_HOST = get_env('REDIS_HOST')
        self.REDIS_PORT = get_env('REDIS_PORT')
        self.REDIS_USERNAME = get_env('REDIS_USERNAME')
        self.REDIS_PASSWORD = get_env('REDIS_PASSWORD')
        self.REDIS_DB = get_env('REDIS_DB')
        self.REDIS_USE_SSL = get_bool_env('REDIS_USE_SSL')

        # ------------------------
        # File Storage Configurations.
        # ------------------------
        self.STORAGE_TYPE = get_env('STORAGE_TYPE')
        self.STORAGE_LOCAL_PATH = get_env('STORAGE_LOCAL_PATH')

        # ------------------------
        # Vector Store Configurations (Weaviate).
        # ------------------------
        self.WEAVIATE_ENDPOINT = get_env('WEAVIATE_ENDPOINT')
        self.WEAVIATE_API_KEY = get_env('WEAVIATE_API_KEY')
        self.WEAVIATE_GRPC_ENABLED = get_bool_env('WEAVIATE_GRPC_ENABLED')
        self.WEAVIATE_BATCH_SIZE = int(get_env('WEAVIATE_BATCH_SIZE'))

        # ------------------------
        # Workpace Configurations.
        # ------------------------
        self.INVITE_EXPIRY_HOURS = int(get_env('INVITE_EXPIRY_HOURS'))

        # ------------------------
        # Sentry Configurations.
        # ------------------------
        self.SENTRY_DSN = get_env('SENTRY_DSN')
        self.SENTRY_TRACES_SAMPLE_RATE = float(get_env('SENTRY_TRACES_SAMPLE_RATE'))
        self.SENTRY_PROFILES_SAMPLE_RATE = float(get_env('SENTRY_PROFILES_SAMPLE_RATE'))

        # ------------------------
        # Business Configurations.
        # ------------------------

        # File upload Configurations.
        self.UPLOAD_FILE_SIZE_LIMIT = int(get_env('UPLOAD_FILE_SIZE_LIMIT'))
        self.UPLOAD_FILE_BATCH_LIMIT = int(get_env('UPLOAD_FILE_BATCH_LIMIT'))
        self.UPLOAD_IMAGE_FILE_SIZE_LIMIT = int(get_env('UPLOAD_IMAGE_FILE_SIZE_LIMIT'))

        # ------------------------
        # Platform Configurations (AI API).
        # ------------------------
        self.HOSTED_OPENAI_ENABLED = get_bool_env('HOSTED_OPENAI_ENABLED')
        self.HOSTED_OPENAI_API_KEY = get_env('HOSTED_OPENAI_API_KEY')
        self.HOSTED_OPENAI_API_BASE = get_env('HOSTED_OPENAI_API_BASE')
        self.HOSTED_OPENAI_API_ORGANIZATION = get_env('HOSTED_OPENAI_API_ORGANIZATION')
        self.HOSTED_OPENAI_QUOTA_LIMIT = int(get_env('HOSTED_OPENAI_QUOTA_LIMIT'))
        self.HOSTED_OPENAI_PAID_ENABLED = get_bool_env('HOSTED_OPENAI_PAID_ENABLED')

        self.HOSTED_AZURE_OPENAI_ENABLED = get_bool_env('HOSTED_AZURE_OPENAI_ENABLED')
        self.HOSTED_AZURE_OPENAI_API_KEY = get_env('HOSTED_AZURE_OPENAI_API_KEY')
        self.HOSTED_AZURE_OPENAI_API_BASE = get_env('HOSTED_AZURE_OPENAI_API_BASE')
        self.HOSTED_AZURE_OPENAI_QUOTA_LIMIT = int(get_env('HOSTED_AZURE_OPENAI_QUOTA_LIMIT'))

        self.HOSTED_ANTHROPIC_ENABLED = get_bool_env('HOSTED_ANTHROPIC_ENABLED')
        self.HOSTED_ANTHROPIC_API_BASE = get_env('HOSTED_ANTHROPIC_API_BASE')
        self.HOSTED_ANTHROPIC_API_KEY = get_env('HOSTED_ANTHROPIC_API_KEY')
        self.HOSTED_ANTHROPIC_QUOTA_LIMIT = int(get_env('HOSTED_ANTHROPIC_QUOTA_LIMIT'))
        self.HOSTED_ANTHROPIC_PAID_ENABLED = get_bool_env('HOSTED_ANTHROPIC_PAID_ENABLED')

        # ------------------------
        # LibreOffice 容器服务配置（数据治理报告导出）
        # ------------------------
        self.LIBREOFFICE_SERVICE_URL = get_env('LIBREOFFICE_SERVICE_URL')
        self.LIBREOFFICE_SERVICE_TIMEOUT = int(get_env('LIBREOFFICE_SERVICE_TIMEOUT') or 120)
        self.LIBREOFFICE_SERVICE_ENABLED = get_bool_env('LIBREOFFICE_SERVICE_ENABLED')

        # ------------------------
        # 数据治理报告导出路径配置
        # ------------------------
        self.GOVERNANCE_EXPORT_PATH = get_env('GOVERNANCE_EXPORT_PATH')


default_language = get_env('default_language')  # 默认语言
