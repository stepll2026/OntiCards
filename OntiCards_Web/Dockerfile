# ============================================================
# Base Stage: 基础镜像定义
# ============================================================
FROM node:20.11-alpine3.19 AS base
LABEL maintainer="takatost@gmail.com"

# 安装时区数据（所有阶段共享）
RUN apk add --no-cache tzdata

# ============================================================
# Dependencies Stage: 依赖安装阶段
# ============================================================
FROM base AS deps
WORKDIR /onticards_web

# 仅复制锁文件，确保依赖缓存稳定
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 100000

# ============================================================
# Builder Stage: 构建阶段
# ============================================================
FROM base AS builder
WORKDIR /onticards_web

# 复制依赖（利用 Docker 缓存层）
COPY --from=deps /onticards_web/node_modules ./node_modules
COPY . .

RUN yarn build

# ============================================================
# Production Stage: 生产环境阶段
# ============================================================
FROM base AS production
WORKDIR /onticards_web

# 设置环境变量
ENV NODE_ENV=production
ENV DEPLOY_ENV=PRODUCTION
ENV CONSOLE_API_URL=https://impluto.ai
ENV PORT=3000
ENV TZ=Asia/Shanghai

# 配置时区
RUN ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone

# 复制构建产物
COPY --from=builder /onticards_web/public ./public
COPY --from=builder /onticards_web/.next/standalone ./
COPY --from=builder /onticards_web/.next/static ./.next/static

# 复制启动脚本
COPY docker/entrypoint.sh ./entrypoint.sh

# 构建参数（用于记录构建信息）
ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

# 暴露端口
EXPOSE 3000

# 启动命令
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
