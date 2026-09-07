# OntiCards 🃏

> **企业级 AI 数据中枢** ｜ 让企业的数据「会说话、能听懂、可治理」

[![Version](https://img.shields.io/badge/version-2.4.0-blue)](https://github.com/stepll2026/OntiCards/releases)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-%E4%B8%AD%E6%96%87%E6%96%87%E6%A1%A3-8A2BE2)](https://www.step2.com.cn/docs/zh-cn/)
[![Docker Compose](https://img.shields.io/badge/deploy-Docker%20Compose%20ready-2496ED)](https://www.step2.com.cn/docs/zh-cn/deployment.html)

OntiCards 是面向企业的 AI 数据中枢（AI Data Hub），**不只是简单的 NL2SQL**。
围绕业务数据库，一站式完成：数据源连接、元数据理解、自然语言自助查询、跨源融合、数据质检、查询审计与数据资产管理。

让企业的数据从「只有会写 SQL 的人才能用」，变成**懂业务语言的人都能查询、质检、管理、审计数据**。

> 📌 开源版完全免费、支持私有化自托管；多租户、行列级权限等企业能力以商业服务形式提供，见文末[商业服务](#-商业服务)。

---

## ✨ 核心能力

- 📡 **多源数据接入**：支持 MySQL、PostgreSQL、Oracle、SQL Server、SQLite、Trino，以及达梦、人大金仓、OceanBase 等国产数据库，共 9 类数据源
- 🧠 **智能数据理解**：每张表自动生成「智能数据卡片」业务说明书，含字段画像、敏感字段识别、业务术语库与 AI 表关系盘点
- 🔍 **自然语言查询**：NL2SQL 多步推理、多数据库方言适配、业务术语自动展开、SQL 安全校验，业务人员即可自助取数
- 🔗 **跨源融合查询**：一次提问跨多个数据库，自动对齐与合并结果，打破数据孤岛
- ✅ **数据质检**：14 种质检规则类型、AI 自然语言建规则、质量评分与质检报告导出
- 🏢 **企业级平台能力**：数据源隔离、敏感信息脱敏、查询审计、API-Key 集成、JWT-SSO 单点登录、查询监控与成本统计

## 🚀 Quick Start

### 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Linux x86_64（推荐 Ubuntu 22.04/24.04） |
| Docker | Docker Engine + Docker Compose 插件 **v2.24.0+** |
| 最低配置 | 2 核 CPU / 4 GB 内存 |
| 浏览器 | 现代桌面浏览器（Chrome / Edge） |

### 三步启动

```bash
# 1. 克隆仓库
git clone https://github.com/stepll2026/OntiCards.git
cd OntiCards

# 2. 配置环境变量（.env.example 提供可直接启动的开发默认值）
cp .env.example .env
chmod 600 .env
#    生产环境请至少修改：DB_PASSWORD、SECRET_KEY、SSO_SECRET_KEY、
#    CONNECT_INFO_MASTER_KEY、PUBLIC_BASE_URL、ALLOWED_ORIGINS

# 3. 校验配置并一键启动（首次会构建 API 与 Web 镜像）
docker compose config -q
docker compose up -d --build

# 访问（Nginx :9107 为唯一对外入口，数据库/向量库/API/Web 均在内网）
open http://your-ip:9107
```

> 📖 完整部署说明（含国内镜像加速、离线部署、端口变更、升级流程）见官方文档：[部署指南](https://www.step2.com.cn/docs/zh-cn/deployment.html)

### ⏱️ 5 分钟体验流程

1. 登录系统，配置大模型（支持通义千问、DeepSeek、智谱 AI、GPT、Claude 等）
2. 添加业务数据源
3. 等待自动生成**智能数据卡片**，补充业务术语与表关系盘点
4. 用自然语言提问，自助查询数据
5. 体验数据质检、查询历史、监控面板与 API 集成

详细操作步骤见官方文档：[用户手册](https://www.step2.com.cn/docs/zh-cn/user-guide.html)

## 📦 支持数据源

| 数据库 | 版本 | 备注 |
| --- | --- | --- |
| MySQL | 5.7+ | 主流开源数据库 |
| PostgreSQL | 10+ | 兼容人大金仓 |
| Oracle | 11g+ | 商业数据库 |
| SQL Server | 2012+ | 微软数据库 |
| SQLite | 3.x | 轻量测试 |
| Trino | Latest | OLAP 引擎 |
| 达梦 DMDB | V8 | 国产数据库 |
| KingBase（人大金仓） | 最新版 | 国产数据库 |
| OceanBase | MySQL 租户 | 分布式国产数据库 |

## 🛠️ 技术栈

### 🎨 前端

| 分类 | 技术 | 说明 |
| --- | --- | --- |
| 核心框架 | Next.js 14 · React 18 · TypeScript 5 | 全栈框架 + SSR |
| UI 组件 | Ant Design 5 · Tailwind CSS 3 · Sass/SCSS | 企业级组件 + 主题切换 |
| 数据可视化 | Recharts · D3.js | 图表与图形 |
| 国际化 | i18next · next-i18n-router | 多语言 + 路由切换 |
| Markdown | react-markdown · remark-gfm · KaTeX | 文档渲染、公式、代码高亮 |

### ⚙️ 后端

| 分类 | 技术 | 说明 |
| --- | --- | --- |
| 核心框架 | Flask 2.3.3 · Flask-RESTful · Gunicorn | RESTful API + WSGI |
| 主数据库 | PostgreSQL 10+ · SQLAlchemy 2.0 | 元数据与业务数据存储 |
| 向量库 | Weaviate 1.36.0 | 语义向量存储与检索 |
| AI / LLM | 通义千问 · DeepSeek · 智谱 AI · GPT · Claude · Azure OpenAI | 支持 Embedding / Rerank |
| 定时任务 | APScheduler | 定时盘点与质检调度 |
| 数据处理 | pandas · numpy · openpyxl · python-docx | 数据处理 + 报告生成 |
| 安全 | cryptography · PyJWT · passlib/bcrypt | AES 加密 + JWT + 密码哈希 |

## 👥 使用场景

- **业务运营**：自助取数、日常监控、异常排查
- **数据分析师**：临时查询、跨库数据整合、快速验证分析假设
- **数据治理专员**：配置质检规则、输出数据质量报告、统一业务术语
- **管理层**：多数据源汇总对比分析
- **IT & 数据团队**：数据源管理、权限管控、查询审计监控
- **第三方系统集成**：通过 API-Key 对接智能体、RPA、BI 平台（支持 [SSO-JWT 集成](https://www.step2.com.cn/docs/zh-cn/sso-jwt.html)）

## 📚 文档中心

全部文档已迁移至官方网站文档中心，请访问：**[https://www.step2.com.cn/docs/zh-cn/](https://www.step2.com.cn/docs/zh-cn/)**

| 文档 | 链接 |
| --- | --- |
| 部署指南 | [deployment](https://www.step2.com.cn/docs/zh-cn/deployment.html) |
| 用户手册 | [user-guide](https://www.step2.com.cn/docs/zh-cn/user-guide.html) |
| API 接口参考 | [api-reference](https://www.step2.com.cn/docs/zh-cn/api-reference.html) |
| SSO-JWT 集成 | [sso-jwt](https://www.step2.com.cn/docs/zh-cn/sso-jwt.html) |
| FAQ | [faq](https://www.step2.com.cn/docs/zh-cn/faq.html) |
| 问题排查指南 | [troubleshooting](https://www.step2.com.cn/docs/zh-cn/troubleshooting.html) |
| 更新日志 | [changelog](https://www.step2.com.cn/docs/zh-cn/changelog.html) |

## 🤝 参与贡献

欢迎提交 Issue、Feature Request 和 Pull Request！
请先阅读：[贡献指南](./CONTRIBUTING.md)

## 📄 License

OntiCards 开源版基于 **[AGPL-3.0](./LICENSE)** 协议开源。

> 简单理解：如果你基于本项目修改并对外提供网络服务，需要公开修改后的源代码。商业授权需求请参考下方[商业服务](#-商业服务)。

## 💼 商业服务

OntiCards 开源版可免费部署使用。如需以下能力，欢迎联系我们：

- 多租户版本、行列级权限
- 企业版数据治理增强、数据校验对账
- 定制开发与私有化实施服务
- 专业技术支持

## 📮 联系我们

- **GitHub Issues**：[stepll2026/OntiCards/issues](https://github.com/stepll2026/OntiCards/issues) — 提交 Bug 与需求反馈
- **产品官网**：[https://www.step2.com.cn](https://www.step2.com.cn) — 产品介绍、解决方案与文档中心

---

**OntiCards** — 让企业的数据「会说话、能听懂、可治理」
