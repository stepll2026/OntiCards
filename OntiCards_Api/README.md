# flask-scaffold
一个简单的flask脚手架

## 安装

克隆代码

```
git clone https://e.coding.net/g-qbgp7780/snaildy/api.git
```

安装依赖

```
pip install -r requirements.txt
```

环境配置

```
cp .env.copy .env
```

## 常用命令

 - python直接启动，适合本地开发调试

```
python app.py
```

 - Start backend

```
poetry run python -m flask run --host 0.0.0.0 --port=5001 --debug
 ```

 - gunicorn启动，适合生产环境

```
gunicorn app:app -c gunicorn.py --reload
```

 - Celery异步任务，开启5个子进程，默认值是电脑系统可用的cpu数量

```
celery -A app.celery_app worker --concurrency=5 --loglevel INFO
```

 - 数据库迁移
 - 
```
## 📦 Flask + Alembic 数据库迁移流程说明
适用于首次初始化数据库迁移环境，或在迁移版本冲突、升级失败等情况下进行重建。
---

### 初始化迁移环境（仅在需要时执行）
当出现以下情况时建议重置迁移环境：
- 初次使用 Flask-Migrate
- 数据库迁移版本冲突或迁移失败
- 升级过程中出现版本错误

**操作步骤：**
1. 删除本地迁移脚本目录：rm -rf migrations/
2. 删除数据库中的迁移版本记录表（alembic_version）：可使用数据库客户端或命令手动删除该表。
3. 重新初始化迁移环境：flask db init

# 生成迁移脚本
flask db migrate -m "版本描述，例如：添加用户表"

# 应用迁移脚本到数据库 将迁移脚本执行并同步数据库结构：
flask db upgrade
```



 - 进行docker服务打包(xxx代表公开的私人远程镜像仓库地址)

```
docker build -t xxx/snaildy-api:1.0.1 .
```

## 目录说明

```
- **顶层目录**：整个项目的目录结构被划分为多个功能模块，并采用了模块化、分层的设计模式，便于开发、调试和部署。
- **controllers/**：视图函数（控制器）目录，负责业务逻辑的路由和视图函数，按功能模块组织代码（如 `chat` 和 `user`）。
- **core/**：包含项目核心逻辑，例如调度器、环境变量管理、日志管理和通用工具方法（如 `scheduler` 和 `tools`）。
- **docker/**：Docker相关配置文件，支持容器化部署。
  - **entrypoint.sh**：Docker容器的启动入口脚本，负责在容器启动时执行必要的初始化步骤。
- **extensions/**：第三方扩展模块的初始化和配置，用于初始化第三方扩展（如数据库、JWT、Redis 等），使扩展逻辑独立。
- **libs/**：自定义工具库，包含项目中的通用工具和辅助功能，如日志工具或特殊业务逻辑函数。。
- **migrations/**：数据库迁移目录，包含数据库模式的版本管理、数据库迁移相关文件，使用 Alembic 或 Flask-Migrate 生成版本脚本。。
- **models/**：数据库模型目录，定义数据库模型，通常结合 SQLAlchemy 等 ORM 工具。
- **static/**：存放静态资源文件的目录，包含前端页面所需的非动态内容，如图片、CSS、JavaScript，支持模板渲染。。
- **task/**：定时任务或异步任务的目录，处理需要定时执行或异步执行的任务，如 Celery 或 APScheduler。。
- **views/**：视图逻辑目录，包含处理与前端交互的功能，如渲染HTML页面或返回JSON数据。
- **app.py**：应用入口文件，启动应用的主脚本，初始化应用配置并运行服务器。
- **config.py**：项目的配置文件，包含全局参数配置（如调试模式、数据库连接、API密钥等），通常由开发人员根据环境调整。
- **settings.py**：应用的设置与配置文件，包含与应用运行相关的具体配置项，如日志级别、最大连接数等。
- **gunicorn.py**：Gunicorn配置文件，用于生产环境部署配置，如工作进程数、超时设置等。
- **docker-compose.yaml**：Docker Compose配置文件，定义如何使用多个容器协作工作（如数据库容器、Web应用容器等）。
- **Dockerfile**：Docker构建文件，包含如何构建Docker镜像的步骤，如基础镜像、安装依赖项、设置工作目录等。
- **.env.copy**：环境变量的示例文件，开发人员可以复制并修改为自己的环境配置文件。
- **.gitignore**：Git版本控制的忽略规则文件，列出不需要版本控制的文件或文件夹，如编译生成文件、临时文件等。
- **LICENSE**：项目的许可证文件，定义项目的授权方式和使用规则。
- **README.md**：项目的说明文件，提供项目背景、功能、安装和使用指南等信息。
- **requirements.txt**：Python依赖包列表文件，列出了项目所需的所有Python库及其版本，方便通过`pip`安装。
```
