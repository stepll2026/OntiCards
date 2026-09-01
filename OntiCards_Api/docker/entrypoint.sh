#!/bin/bash

set -e

# ============================================================
# ⚠️ 禁止使用 -d / --daemon 参数！
#
# 历史上若把 gunicorn 放到后台运行（-d 或 &），容器主进程会立即退出，
# docker 会判定容器已结束并按重启策略拉起新实例，
# 表现就是"每隔一段时间容器自己关停"。
# 当前配置让 gunicorn 跑在前台（容器主进程 = gunicorn master），
# 只有 worker 出现异常时才会被宿主 OOM Killer 杀。
# ============================================================

# 加载 .env 文件
if [ -f /onticards_api/.env ]; then
  set -a
  . /onticards_api/.env
  set +a
fi

# Gunicorn 配置（与 gunicorn.py 保持一致）
# workers: 并行进程数
# worker_class: gevent (协程) / gthread (线程) / sync (同步)
# threads: 每个进程的线程数
# worker_connections: 最大并发连接数
# timeout: 请求超时（秒），全域盘点等长任务需要较长超时
# graceful_timeout: 优雅重启超时
# max_requests: 最大请求数（超过后重启worker，防止内存泄漏）
# max_requests_jitter: 最大请求抖动值

gunicorn \
  --config gunicorn.py \
  --bind "${DIFY_BIND_ADDRESS:-0.0.0.0}:${DIFY_PORT:-9103}" \
  --workers ${GUNICORN_WORKERS:-2} \
  --worker-class ${GUNICORN_WORKER_CLASS:-gthread} \
  --threads ${GUNICORN_THREADS:-6} \
  --worker-connections ${GUNICORN_WORKER_CONNECTIONS:-200} \
  --timeout ${GUNICORN_TIMEOUT:-28800} \
  --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} \
  --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
  --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
  --log-level ${GUNICORN_LOG_LEVEL:-warning} \
  --preload \
  app:app