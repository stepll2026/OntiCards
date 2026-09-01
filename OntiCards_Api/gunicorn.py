# gunicorn配置文件
# 注意：默认使用 gthread 模式（稳定可靠）
# 如果需要切换到 gevent 协程模式，取消下面的 monkey patch

import os
from core import env

# # gevent 协程模式需要 monkey patch（如果使用 gevent 模式则取消注释）
# from gevent import monkey
# monkey.patch_all()

port = env.get('PORT', 9103)

# ==================== Gunicorn 配置 ====================
# 并行进程数（CPU核心数 * 2 + 1 是常见公式，对于I/O密集型可设更大）
workers = int(env.get('GUNICORN_WORKERS', 2))
# 工作模式：gevent (协程) / gthread (线程) / sync (同步)
# gthread: 线程模式，稳定可靠，推荐生产环境使用
# gevent: 协程模式，内存占用低，但需注意第三方库兼容性
worker_class = env.get('GUNICORN_WORKER_CLASS', 'gthread')
# 每个进程的线程数
threads = int(env.get('GUNICORN_THREADS', 6))
# 最大并发连接数（仅 gevent/gthread 模式有效）
worker_connections = int(env.get('GUNICORN_WORKER_CONNECTIONS', 200))
# 超时时间（秒）- 全域盘点等长计算任务需要较长时间
timeout = int(env.get('GUNICORN_TIMEOUT', 28800))
# 优雅重启超时
graceful_timeout = int(env.get('GUNICORN_GRACEFUL_TIMEOUT', 30))
# 最大请求数（超过后重启worker，防止内存泄漏）
# PR-C 辅助防御：与 worker_memory_limit 互补，双重兜底
#   - max_requests：请求计数触发，精确防止内存泄漏（但不够及时）
#   - worker_memory_limit：RSS 内存触发，更及时但阈值设置有讲究
# jitter = 随机偏移，避免所有 worker 同时重启
max_requests = int(env.get('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = int(env.get('GUNICORN_MAX_REQUESTS_JITTER', 100))

# ============================================================
# PR-C: worker_memory_limit 智能阈值计算
#
# 工作原理：
#   当单个 worker 的 RSS（Resident Set Size，物理内存占用）超过阈值时，
#   gunicorn master 对该 worker 发 SIGTERM → 30s 优雅退出 → SIGKILL 强制杀死
#   → 新 worker fork 出来顶位。整个过程容器不挂，其他 worker 正常处理请求。
#
# 阈值公式：
#   推荐值 = (容器内存上限 × 0.80) / workers
#
#   例如：容器 4G / workers=2 → 1600 MB/worker
#         容器 2G / workers=2 →  800 MB/worker
#
# 为什么用 80%？
#   - 留 20% 给：OS page cache、other processes、突发峰值
#   - 阈值太高 → 内存泄漏长期潜伏，最终触发 Linux 容器层 OOM（整个容器挂）
#   - 阈值太低 → 正常大请求也可能触发 worker 抖动
#   - 流式响应优化后（PR-A），单次 /all 请求内存峰值已降至几百 KB，
#     设 800-1600 MB 是绝对安全的，正常请求不会触发。
#
# 环境变量（优先级从高到低）：
#   WORKER_MEMORY_LIMIT_MB        显式指定（优先，精确控制）
#   CONTAINER_MEMORY_MB            容器内存上限（配合 workers 自动算）
#   GUNICORN_WORKER_MEMORY_LIMIT_AUTO 若设为 1，使用自动公式
#                                 （默认，当 WORKER_MEMORY_LIMIT_MB=0 时触发）
#
# 关闭：WORKER_MEMORY_LIMIT_MB=0（默认值 0，不启用）
# 需要：gunicorn >= 21.0，当前 requirements.txt 锁定 21.2.0
# ============================================================
_worker_mem_limit_mb = int(env.get('WORKER_MEMORY_LIMIT_MB', '0') or '0')

if _worker_mem_limit_mb > 0:
    # 显式指定优先
    worker_memory_limit = _worker_mem_limit_mb
    print(f"[gunicorn] worker_memory_limit = {worker_memory_limit} MB（显式指定）")
else:
    # 自动计算：当 WORKER_MEMORY_LIMIT_MB=0 且开启了自动模式时
    auto_enabled = env.get('GUNICORN_WORKER_MEMORY_LIMIT_AUTO', '0') == '1'
    if auto_enabled:
        container_mem = float(env.get('CONTAINER_MEMORY_MB', '0') or '0')
        if container_mem <= 0:
            # 尝试从 cgroup 读取（Kubernetes / Docker 标准路径）
            for _path in (
                '/sys/fs/cgroup/memory/memory.limit_in_bytes',
                '/sys/fs/cgroup/memory.max',
            ):
                try:
                    with open(_path, 'r') as f:
                        raw = f.read().strip()
                        if raw == 'max':
                            container_mem = 0
                        else:
                            container_mem = float(raw) / (1024 * 1024)
                    break
                except Exception:
                    pass
        if container_mem > 0:
            workers_count = int(env.get('GUNICORN_WORKERS', '2'))
            computed = int((container_mem * 0.80) / workers_count)
            # 兜底：最小 500MB，最大 3000MB
            computed = max(500, min(computed, 3000))
            worker_memory_limit = computed
            print(f"[gunicorn] worker_memory_limit = {worker_memory_limit} MB"
                  f"（自动：容器 {container_mem:.0f}MB / workers={workers_count} × 0.80）")
        else:
            print("[gunicorn] worker_memory_limit 未配置且无法自动检测，关闭内存限制")
    else:
        # 完全关闭
        pass

# 内网IP和端口
bind = '0.0.0.0:{port}'.format(port=port)

# 日志
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)   # gunicorn 日志阶段比 Flask app.init 早，提前建目录避免 FileNotFoundError
accesslog = '{log_dir}/gunicorn_access.log'.format(log_dir=log_dir)
errorlog = '{log_dir}/gunicorn_error.log'.format(log_dir=log_dir)
loglevel = env.get('GUNICORN_LOG_LEVEL', 'warning')

# ============================================================
# PR-D: access.log 瘦身
#
# 历史背景：/datacard_tool/all?parse_json=true 单次响应 20~30MB，
# gunicorn 默认 access_log_format = %(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"
# 会把 query string 完整写到一行日志 → 单行 30MB+。
# 后果：磁盘 IO 飙升、磁盘爆满 → 容器其他组件连带异常。
#
# 修复：
# 1) 用精简的 logformat：不记录 Referer / UA（生产一般用不着）
# 2) 把响应字节数 %(b)s 留作异常排查线索（注意它本身不会让行很长）
# 3) 关闭 accesslog 的 logger 单独记超大响应路径（可选）
# ============================================================
access_log_format = '%(t)s "%(r)s" %(s)s %(b)s %(D)sus'

# 预加载应用（共享内存，减少内存使用）
preload_app = True

# ============================================================
# PR-E: gunicorn 日志按大小自动切分（标准库内置，零额外进程）
#
# 原理：Python logging.handlers.RotatingFileHandler
#   - 文件达到 maxBytes → 自动 rename 成 .1 → 新建原文件继续写
#   - backupCount=N → 只保留 .1 ~ .N，超出的自动 unlink
#   - 切分时机 = 写满瞬间，无需定时任务、无需后台线程
#
# 适用范围：只接管 gunicorn 原生 accesslog / errorlog。
# 不影响 app.logger（core/log.py 已用 TimedRotatingFileHandler 按天切），
# 不影响 app.py 中的 _start_log_rotation_thread 守护线程（保留为兜底）。
#
# 容量上限（默认配置）：
#   access.log 最大占用 = 100MB × 6 = 600MB
#   error.log  最大占用 = 100MB × 6 = 600MB
#   gunicorn 日志总占用封顶 ≈ 1.2GB，彻底避免"磁盘满 → 容器挂"链路。
# ============================================================
from logging.handlers import RotatingFileHandler  # noqa: E402
from logging import Formatter                     # noqa: E402

_log_max_bytes = int(env.get('LOG_ROTATE_BYTES', 100 * 1024 * 1024))  # 默认 100MB
_log_backups   = int(env.get('LOG_ROTATE_BACKUPS', 5))                 # 默认保留 5 份

# ============================================================
# PR-E: gunicorn 日志按大小自动切分（标准库内置，零额外进程）
# 在 gunicorn 初始化完成后，用 RotatingFileHandler 替换掉默认的 FileHandler；
# 不使用 logconfig_dict（它会触发 logging.config.dictConfig()，与 gunicorn
# 内部日志系统冲突，导致 "Unable to configure root logger"）。
#
# 原理：Python logging.handlers.RotatingFileHandler
#   - 文件达到 maxBytes → 自动 rename 成 .1 → 新建原文件继续写
#   - backupCount=N → 只保留 .1 ~ .N，超出的自动 unlink
#   - 切分时机 = 写满瞬间，无需定时任务、无需后台线程
#
# 适用范围：只接管 gunicorn 原生 accesslog / errorlog。
# 不影响 app.logger（core/log.py 已用 TimedRotatingFileHandler 按天切），
# 不影响 app.py 中的 _start_log_rotation_thread 守护线程（保留为兜底）。
#
# 容量上限（默认配置）：
#   access.log 最大占用 = 100MB × 6 = 600MB
#   error.log  最大占用 = 100MB × 6 = 600MB
#   gunicorn 日志总占用封顶 ≈ 1.2GB，彻底避免"磁盘满 → 容器挂"链路。
# ============================================================


def _configure_rotating_logs(arbiter):
    """when_ready 钩子：在 gunicorn master 启动完成后，替换日志 Handler 为 RotatingFileHandler"""
    # gunicorn error logger
    error_logger = arbiter.log.error_log
    _swap_handler(error_logger, errorlog, _log_max_bytes, _log_backups)
    # gunicorn access logger
    access_logger = arbiter.log.access_log
    _swap_handler(access_logger, accesslog, _log_max_bytes, _log_backups)
    print(f"[gunicorn] 日志切分已启用：maxBytes={_log_max_bytes}, backupCount={_log_backups}")


def _swap_handler(logger, filepath, maxBytes, backupCount):
    """把 logger 上已挂的 Handler 全部移除并关闭，换成 RotatingFileHandler"""
    # 先把旧的 formatter 留着（没有就默认）
    old_formatter = logger.handlers[0].formatter if logger.handlers else Formatter(
        '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
        datefmt='[%Y-%m-%d %H:%M:%S %z]',
    )
    # 关闭所有旧 handler（释放文件描述符），再从 logger 移除
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)
    h = RotatingFileHandler(
        filepath,
        maxBytes=maxBytes,
        backupCount=backupCount,
        encoding='utf-8',
    )
    h.setFormatter(old_formatter)
    logger.addHandler(h)


# gunicorn 钩子（gunicorn 21.x 参数名）
when_ready = _configure_rotating_logs
