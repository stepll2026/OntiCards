#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os

from environs import Env

env = Env()
env.read_env()


DEFAULTS = {
    'DB_USERNAME': 'postgres',
    'DB_PASSWORD': '',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
    'DB_DATABASE': '',
    'DB_CHARSET': '',
    'REDIS_HOST': 'localhost',
    'REDIS_PORT': '6379',
    'REDIS_DB': '0',
    'REDIS_USE_SSL': 'False',
    'OAUTH_REDIRECT_PATH': '/console/api/oauth/authorize',
    'OAUTH_REDIRECT_INDEX_PATH': '/',
    'CONSOLE_WEB_URL': '',
    'CONSOLE_API_URL': '',
    'SERVICE_API_URL': '',
    'APP_WEB_URL': '',
    'FILES_URL': '',
    'STORAGE_TYPE': 'local',
    'STORAGE_LOCAL_PATH': 'storage',
    # 'CHECK_UPDATE_URL': '',
    'DEPLOY_ENV': 'PRODUCTION',
    'SQLALCHEMY_POOL_SIZE': 30,
    'SQLALCHEMY_POOL_RECYCLE': 3600,
    'SQLALCHEMY_ECHO': 'False',
    'SENTRY_TRACES_SAMPLE_RATE': 1.0,
    'SENTRY_PROFILES_SAMPLE_RATE': 1.0,
    'WEAVIATE_GRPC_ENABLED': 'True',
    'WEAVIATE_BATCH_SIZE': 100,
    'QDRANT_CLIENT_TIMEOUT': 20,
    'CELERY_BACKEND': 'database',
    'LOG_LEVEL': 'INFO',
    'HOSTED_OPENAI_QUOTA_LIMIT': 200,
    'HOSTED_OPENAI_TRIAL_ENABLED': 'False',
    'HOSTED_OPENAI_PAID_ENABLED': 'False',
    'HOSTED_OPENAI_PAID_INCREASE_QUOTA': 1,
    'HOSTED_OPENAI_PAID_MIN_QUANTITY': 1,
    'HOSTED_OPENAI_PAID_MAX_QUANTITY': 1,
    'HOSTED_AZURE_OPENAI_ENABLED': 'False',
    'HOSTED_AZURE_OPENAI_QUOTA_LIMIT': 200,
    'HOSTED_ANTHROPIC_QUOTA_LIMIT': 600000,
    'HOSTED_ANTHROPIC_TRIAL_ENABLED': 'False',
    'HOSTED_ANTHROPIC_PAID_ENABLED': 'False',
    'HOSTED_ANTHROPIC_PAID_INCREASE_QUOTA': 1,
    'HOSTED_ANTHROPIC_PAID_MIN_QUANTITY': 1,
    'HOSTED_ANTHROPIC_PAID_MAX_QUANTITY': 1,
    'HOSTED_MODERATION_ENABLED': 'False',
    'HOSTED_MODERATION_PROVIDERS': '',
    'CLEAN_DAY_SETTING': 30,
    'UPLOAD_FILE_SIZE_LIMIT': 15,
    'UPLOAD_FILE_BATCH_LIMIT': 5,
    'UPLOAD_IMAGE_FILE_SIZE_LIMIT': 10,
    'OUTPUT_MODERATION_BUFFER_SIZE': 300,
    'MULTIMODAL_SEND_IMAGE_FORMAT': 'base64',
    'INVITE_EXPIRY_HOURS': 72,
    'BILLING_ENABLED': 'False',
    'CAN_REPLACE_LOGO': 'False',
    'ETL_TYPE': '',
}


def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


def get_bool_env(key):
    value = get_env(key)
    return value.lower() == 'true' if value is not None else False

class BaseConfig(object):
    TESTING = True
    DEBUG = True
    # SQLALCHEMY_DATABASE_URI = env.str('DATABASE_URI')
    # SQLALCHEMY_TRACK_MODIFICATIONS = False

    def __init__(self):
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
        # Database Configurations.
        # ------------------------
        db_credentials = {
            key: get_env(key) for key in
            ['DB_USERNAME', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_CHARSET']
        }

        # 连接参数：客户端字符编码
        db_extras = f"?client_encoding={db_credentials['DB_CHARSET']}" if db_credentials['DB_CHARSET'] else ""

        self.SQLALCHEMY_DATABASE_URI = f"postgresql://{db_credentials['DB_USERNAME']}:{db_credentials['DB_PASSWORD']}@{db_credentials['DB_HOST']}:{db_credentials['DB_PORT']}/{db_credentials['DB_DATABASE']}{db_extras}"
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(get_env('SQLALCHEMY_POOL_SIZE')),
            'pool_recycle': int(get_env('SQLALCHEMY_POOL_RECYCLE')),
            # 通过 connect_args 设置会话时区，确保 TIMESTAMPTZ 按中国时区显示
            'connect_args': {
                'options': '-cTimeZone=Asia/Shanghai'
            }
        }

        self.SQLALCHEMY_ECHO = get_bool_env('SQLALCHEMY_ECHO')


class ProductionConfig(BaseConfig):
    TESTING = False
    DEBUG = False


class DevelopConfig(BaseConfig):
    TESTING = True
    DEBUG = True


configs = {
    # 生产环境
    'production': ProductionConfig,
    # 测试环境
    'development': DevelopConfig
}
