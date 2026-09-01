#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from flask import Flask
import logging
from logging.handlers import TimedRotatingFileHandler

def init(app: Flask):
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    log_dir = f'{basedir}/logs'
    os.makedirs(log_dir, exist_ok=True)  # 确保目录存在

    # 文件处理器
    loghandler = TimedRotatingFileHandler(
        f'{log_dir}/flask.log', when="MIDNIGHT", interval=1, backupCount=12,
        encoding="UTF-8", delay=False, utc=True
    )
    loghandler.setLevel(logging.DEBUG)

    # 标准输出处理器（使用 app.py 中已经设置好 UTF-8 编码的 sys.stdout）
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)

    # 日志格式
    logging_format = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(lineno)s - %(message)s')
    loghandler.setFormatter(logging_format)
    stream_handler.setFormatter(logging_format)

    # 添加处理器并设置级别
    app.logger.addHandler(loghandler)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    pass