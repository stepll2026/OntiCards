# OntiCards 🃏

> 企业级智能数据中枢｜开源版

[GitHub Release](https://github.com/your-org/onticards/releases)
[License: AGPL-3.0](LICENSE)
[Docker Compose ready](https://docs.docker.com/compose/)
[Last Commit](https://github.com/your-org/onticards/commits/main)

OntiCards 是面向企业的 AI 数据中枢，**不只是简单 NL2SQL**。
围绕业务数据库，一站式完成：数据源连接、元数据理解、自然语言自助查询、跨源融合、数据质检、查询审计与数据资产管理。

让企业数据库从「只有会写SQL才能使用」变成**懂业务语言就可以查询、质检、管理、审计数据**。

> 📌 开源版完全免费可自托管；高级企业能力请参考商业服务。

## ✨ 核心能力概览

- 📡 **多源数据接入**：MySQL、PostgreSQL、Oracle、达梦、人大金仓、OceanBase、SQL Server、Trino 等
- 🧠 **智能数据理解**：智能数据卡片、字段画像、敏感字段识别、业务术语库、AI表关系盘点
- 🔍 **自然语言查询**：NL2SQL，多步推理，多数据库方言适配，业务术语自动展开，安全校验
- 🔗 **跨源融合查询**：打破数据孤岛，一次提问跨多库查询，自动对齐结果
- ✅ **数据质检平台**：多类型质检规则、质量评分、自动质检报告
- 🏢 **企业级平台能力**：数据源隔离、敏感脱敏、操作审计、API-Key、JWT-SSO、查询监控与成本统计



## 🚀 Quick Start



### 环境要求

- Docker & Docker Compose
- 最低配置：2-Core CPU / 4GB RAM
- 系统存储库：PostgreSQL 10+

```bash
# 1. Clone repo
git clone https://github.com/stepll2026/OntiCards.git
cd OntiCards

# 2. 一键启动
docker-compose up -d

# 3. 访问
open http://your-ip:9107
```

> 📖 完整部署、配置步骤见：[部署指南](./docs_open/部署指南.md)



### ⏱️ 5分钟快速体验流程

1. 登录系统，配置大模型
2. 添加业务数据源
3. 等待生成**智能数据卡片**，补充业务术语与表关系盘点
4. 使用自然语言提问自助查询数据
5. 体验数据质检、查询历史、监控面板、API集成

完整操作手册：[用户手册](./docs_open/用户手册.md)

## 📦 支持数据源


| Database       | 版本      | 备注     |
| -------------- | ------- | ------ |
| MySQL          | 5.7+    |        |
| PostgreSQL     | 10+     | 兼容人大金仓 |
| Oracle         | 11g+    |        |
| SQL Server     | 2012+   |        |
| 达梦 DMDB        | V8      | 国产数据库  |
| KingBase(人大金仓) | 最新版     | 国产数据库  |
| OceanBase      | MySQL租户 | 分布式国产库 |
| SQLite         | 3.x     | 轻量测试   |
| Trino          | Latest  | OLAP引擎 |




## 🛠️ 技术栈

### 🎨 前端技术栈


| 分类       | 技术                                                          | 说明           |
| -------- | ----------------------------------------------------------- | ------------ |
| 核心框架     | Next.js 14, React 18, TypeScript 5                          | 全栈框架 + SSR   |
| UI组件     | Ant Design 5, Tailwind CSS 3, Sass/SCSS                     | 企业级组件 + 主题切换 |
| 数据可视化    | Recharts, D3.js, wavesurfer.js                              | 图表、图形、音频波形   |
| 国际化      | i18next, react-i18next, next-i18n-router                    | 多语言 + 路由切换   |
| Markdown | react-markdown, remark-gfm, KaTeX, react-syntax-highlighter | 文档渲染、公式、代码高亮 |
| 工具库      | lucide-react, lodash, next-nprogress-bar                    | 图标、工具函数、进度条  |


### ⚙️ 后端技术栈


| 分类     | 技术                                                         | 说明                     |
| -------- | ------------------------------------------------------------ | ------------------------ |
| 核心框架 | Flask 2.3.3, Flask-RESTful, Gunicorn 21.2.0                  | RESTful API + WSGI服务器 |
| 数据库   | PostgreSQL 10+, SQLAlchemy 2.0.36                            | 主数据库 + ORM           |
| 向量库   | Weaviate 4.20.4                                              | 语义向量存储与检索       |
| AI/LLM   | 通义千问、DeepSeek、智谱AI、GPT、Claude、Azure OpenAI等      | 支持 Embedding/Rerank    |
| 任务队列 | APScheduler 3.10.4                                           | 定时任务                 |
| 数据处理 | pandas 2.0.3, numpy 1.24.4, openpyxl, python-docx、LibreOffice | 数据处理 + 文档生成      |
| 安全     | cryptography 44.0.2, PyJWT 2.9.0, passlib/bcrypt             | AES加密 + JWT + 密码哈希 |


### 🗄️ 支持的数据源


| Database         | 备注          |
| ---------------- | ----------- |
| MySQL 5.7+       | 主流开源数据库     |
| PostgreSQL 10+   | 兼容 KingBase |
| Oracle 11g+      | 商业数据库       |
| SQL Server 2012+ | 微软数据库       |
| 达梦 DMDB V8       | 国产数据库       |
| KingBase (人大金仓)  | 国产数据库       |
| OceanBase        | MySQL 租户    |
| SQLite 3.x       | 轻量测试        |
| Trino            | OLAP 引擎     |




## 👥 使用场景

- 业务运营：自助取数、日常监控、异常排查
- 数据分析师：临时查询、跨库数据整合、快速验证分析假设
- 数据治理专员：配置质检规则、输出数据质量报告、统一业务术语
- 管理层：多数据源汇总对比分析
- IT & 数据团队：数据源管理、权限管控、查询审计监控
- 第三方系统集成：通过API-Key对接智能体、RPA、BI平台



## 📚 文档导航


| 文档    | 链接                                |
| ----- | --------------------------------- |
| 部署文档  | [部署指南](./docs_open/部署指南.md)       |
| 用户手册  | [用户手册](./docs_open/用户手册.md)       |
| API参考 | [API接口文档](./docs_open/API接口文档.md) |
| FAQ   | [FAQ](./docs_open/FAQ.md)         |
| 故障排查  | [问题排查指南](./docs_open/问题排查指南.md)   |




## 🤝 参与贡献

欢迎 Issue、Feature Request 和 Pull Request！
阅读：[贡献指南](./CONTRIBUTING.md)

## 📄 License

OntiCards 开源版本基于 **AGPL-3.0** 开源协议开源，请遵守协议约束。

> 简单理解：如果你修改并对外提供服务，需要公开修改后的源代码。

- [完整协议文本](./LICENSE)



## 💼 商业服务

OntiCards 开源版可以免费部署使用。
如果需要：多租户版本、行列级权限、定制开发、技术支持、企业版数据治理、私有化实施服务，欢迎联系我们商业团队。

## 📮 联系我们

- GitHub Issues：[https://github.com/stepll2026/OntiCards/issues](https://github.com/stepll2026/OntiCards/issues)提交bug、需求反馈
- 产品官网：[https://onticards.com/](https://onticards.com/)

> OntiCards — 让企业的数据「会说话、能听懂、可治理」
