# syntax=docker/dockerfile:1

# ==========================================================
# 阶段一：基础镜像
# ==========================================================
FROM python:3.10-slim-bookworm AS base

LABEL maintainer="takatost@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ==========================================================
# 阶段二：Python 依赖构建
# 用于编译需要 C 扩展的 Python 包（如 cryptography）
# ==========================================================
FROM base AS packages

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        libcrypt-dev \
        unixodbc-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir --prefix=/pkg -r /requirements.txt

# ==========================================================
# 阶段三：最终运行镜像
# ==========================================================
FROM base AS production

# ----- 环境变量 -----
ENV FLASK_APP=app.py \
    DEPLOY_ENV=PRODUCTION \
    TZ=Asia/Shanghai

EXPOSE 9103

WORKDIR /onticards_api

# ----- 阶段四：系统依赖（运行时） -----
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # 基础工具
        curl \
        wget \
        unzip \
        gnupg2 \
        apt-transport-https \
        ca-certificates \
        # 通用动态库
        libaio1 \
        libssl-dev \
        libcrypt-dev \
        openssl \
        unixodbc \
        unixodbc-dev \
        # 字体支持
        fonts-noto \
        fonts-noto-cjk \
        fonts-dejavu \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ----- 阶段五：数据库客户端 -----
# Microsoft ODBC Driver 17（SQL Server）
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor > /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Oracle Instant Client
RUN mkdir -p /opt/oracle \
    && cd /opt/oracle \
    && wget -q https://download.oracle.com/otn_software/linux/instantclient/2114000/instantclient-basic-linux.x64-21.14.0.0.0dbru.zip \
    && unzip -q instantclient-basic-linux.x64-21.14.0.0.0dbru.zip \
    && rm -f instantclient-basic-linux.x64-21.14.0.0.0dbru.zip \
    && echo '/opt/oracle/instantclient_21_14' > /etc/ld.so.conf.d/30-oracle-instantclient.conf \
    && ldconfig

# ----- 阶段六：DM8 达梦数据库 -----
# 复制 DM8 Linux 客户端动态库
# 提取脚本：chmod +x extract_dm8_so.sh && ./extract_dm8_so.sh
# 提取结果位于：docker/dm8/client/ -> 镜像 /opt/dmdbms/
RUN mkdir -p /opt/dmdbms

COPY docker/dm8/client/ /opt/dmdbms/

# 注册 DM8 ODBC 驱动
# 不使用 DM_HOME/PATH/LD_LIBRARY_PATH，动态库目录直接写入 ld.so.conf.d
RUN DM_ODBC_DRIVER="$(find /opt/dmdbms \( -type f -o -type l \) -name 'libdodbc.so' -print -quit)" \
    && if [ -z "${DM_ODBC_DRIVER}" ]; then \
        echo 'ERROR: docker/dm8/client/ 中没有找到 libdodbc.so。' >&2; \
        exit 1; \
    fi \
    && mkdir -p /opt/dmdbms/bin \
    && if [ "${DM_ODBC_DRIVER}" != '/opt/dmdbms/bin/libdodbc.so' ]; then \
        ln -sfn "${DM_ODBC_DRIVER}" /opt/dmdbms/bin/libdodbc.so; \
    fi \
    && chmod -R a+rX /opt/dmdbms \
    && find /opt/dmdbms \( -type f -o -type l \) -name '*.so*' -printf '%h\n' \
        | sort -u > /etc/ld.so.conf.d/10-dm8.conf \
    && test -s /etc/ld.so.conf.d/10-dm8.conf \
    && ldconfig \
    && printf '%s\n' '[DM8 ODBC DRIVER]' 'Description=ODBC DRIVER FOR DM8' 'Driver=/opt/dmdbms/bin/libdodbc.so' \
        > /tmp/dm8-odbcinst.ini \
    && odbcinst -i -d -f /tmp/dm8-odbcinst.ini \
    && rm -f /tmp/dm8-odbcinst.ini \
    && echo '===== DM8 ODBC 依赖检查 =====' \
    && ldd /opt/dmdbms/bin/libdodbc.so | tee /tmp/dm8-odbc-ldd.txt \
    && if grep -q 'not found' /tmp/dm8-odbc-ldd.txt; then \
        echo 'ERROR: DM8 ODBC 驱动存在缺失依赖。' >&2; \
        echo '请从同一个达梦镜像补充缺失的 *.so* 文件。' >&2; \
        exit 1; \
    fi \
    && rm -f /tmp/dm8-odbc-ldd.txt \
    && echo '===== 已注册的 ODBC 驱动 =====' \
    && odbcinst -q -d

# ----- 阶段七：Python 依赖（运行时） -----
# 从构建阶段复制预编译的 Python 包
COPY --from=packages /pkg /usr/local

# ----- 阶段八：dmPython 加密模块配置 -----
# 连接链路：dmSQLAlchemy -> dmPython
# dmPython 自带的 dmssl 目录需要进入系统动态库搜索路径
RUN DMPYTHON_SSL_DIR="$(find /usr/local/lib/python3.10/site-packages -type d -name 'dmssl' -print -quit)" \
    && if [ -z "${DMPYTHON_SSL_DIR}" ]; then \
        echo 'ERROR: dmPython 已安装，但没有找到 site-packages/dmssl。' >&2; \
        echo '请检查 requirements.txt 中安装的 dmPython 版本。' >&2; \
        exit 1; \
    fi \
    && chmod -R a+rX "${DMPYTHON_SSL_DIR}" \
    && find "${DMPYTHON_SSL_DIR}" \( -type f -o -type l \) -name '*.so*' -printf '%h\n' \
        | sort -u > /etc/ld.so.conf.d/00-dmpython-dmssl.conf \
    && test -s /etc/ld.so.conf.d/00-dmpython-dmssl.conf \
    && ldconfig \
    && echo '===== dmPython dmssl 配置 =====' \
    && cat /etc/ld.so.conf.d/00-dmpython-dmssl.conf \
    && find "${DMPYTHON_SSL_DIR}" \( -type f -o -type l \) -name '*.so*' -print | sort \
    && echo '===== dmPython 模块依赖检查 =====' \
    && DMPYTHON_MODULE="$(python -c 'import dmPython; print(dmPython.__file__)')" \
    && if [ -f "${DMPYTHON_MODULE}" ]; then \
        ldd "${DMPYTHON_MODULE}" | tee /tmp/dmpython-ldd.txt; \
        if grep -q 'not found' /tmp/dmpython-ldd.txt; then \
            echo 'ERROR: dmPython 模块存在缺失依赖。' >&2; \
            exit 1; \
        fi; \
        rm -f /tmp/dmpython-ldd.txt; \
    fi

# ----- 阶段九：应用文件 -----
# 复制项目文件（排除 docker/dm8/client/ 重复部分）
COPY . /onticards_api

# 达梦动态库已复制到 /opt/dmdbms，删除应用目录中的重复副本
RUN rm -rf /onticards_api/docker/dm8/client

# 复制入口脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh \
    && chmod +x /entrypoint.sh

# ----- 阶段十：构建元信息 -----
ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
