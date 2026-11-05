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

# ============================================================
# 数据库迁移（Alembic）
#
# 放在这里的理由：
#   1. Dockerfile 的 RUN 发生在「构建镜像时」，构建机不一定连得上生产库，
#      而且镜像可能被多处部署，构建期改库完全不可控。
#      迁移是「部署时」动作，必须放在容器启动阶段。
#   2. 本脚本在 gunicorn 之前顺序执行，此时只有当前这一个进程，
#      不存在多 worker 并发跑迁移的问题（--preload 只会 fork worker，
#      不会重复执行到此行之前的命令）。
#
# 开关：
#   RUN_DB_MIGRATION=false   跳过迁移，用于「迁移已单独执行」或
#                            「迁移出问题需要先起服务排查」的应急场景。
#   默认 true。
#
# 并发：
#   单容器部署无需额外处理。若改为多副本同时启动（K8s / compose 多实例），
#   多个容器会同时 upgrade —— Alembic 自身没有分布式锁，
#   应改用「首个副本执行、其余等待」的 initContainer 或单独的 Job 来跑迁移。
# ============================================================
if [ "${RUN_DB_MIGRATION:-true}" = "true" ]; then
  echo "[entrypoint] 检查数据库迁移状态..."
  flask db current || true
  echo "[entrypoint] 执行 flask db upgrade..."
  if ! flask db upgrade; then
    echo "[entrypoint] 错误：数据库迁移失败，容器将退出。" >&2
    echo "[entrypoint] 排查建议：" >&2
    echo "  1) 确认 DB_HOST / DB_DATABASE / 账号密码正确" >&2
    echo "  2) 查看 migrations/versions/ 是否有冲突的迁移链（多个 head）" >&2
    echo "  3) 确认目标库的 alembic_version 与脚本目录能对上" >&2
    echo "  4) 应急：设 RUN_DB_MIGRATION=false 先起服务，再手工排查" >&2
    exit 1
  fi
  echo "[entrypoint] 迁移完成，当前版本："
  flask db current
else
  echo "[entrypoint] 已跳过数据库迁移（RUN_DB_MIGRATION=${RUN_DB_MIGRATION}）"
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
  --bind "${API_BIND_ADDRESS:-0.0.0.0}:${PORT:-9103}" \
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