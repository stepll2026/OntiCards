# OntiCards

**Enterprise AI Data Hub | Making corporate databases readable by AI — and instantly usable by business**

[![Version](https://img.shields.io/badge/version-2.4.0-blue)](https://github.com/stepll2026/OntiCards/releases)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-%E4%B8%AD%E6%96%87%E6%96%87%E6%A1%A3-8A2BE2)](https://www.step2.com.cn/docs/zh-cn/)
[![Docker Compose](https://img.shields.io/badge/deploy-Docker%20Compose%20ready-2496ED)](https://www.step2.com.cn/docs/zh-cn/deployment.html)

[简体中文](README.md) | [繁體中文(香港)](README_zh-HK.md) | **English**

**Open source and free · Self-hosted · End-to-end intelligent data governance**

**Project**: [https://github.com/stepll2026/OntiCards/releases](https://github.com/stepll2026/OntiCards/releases)

**Documentation**: [https://www.step2.com.cn/docs/zh-cn/](https://www.step2.com.cn/docs/zh-cn/)

**License**: [AGPL-3.0](./LICENSE)

## 💡 Foreword: The Real Bottleneck of Enterprise AI Is Never the LLM

Most enterprises pushing AI-driven digital transformation run into the same wall: **the LLM works great, but their own data doesn't**.

Data is scattered across MySQL, Oracle, domestic Chinese databases, and countless business systems — with no unified inventory, no business definitions, and no quality controls. Engineering teams burn out writing ad-hoc SQL, wiring up data sources, and chasing data errors. Business teams wait on engineering backlogs for every number, and cross-department reconciliation takes days. On top of that, risks pile up: sensitive data leaks, AI misuse, and no audit trail.

**Data should be the core asset of enterprise AI — instead, it becomes the biggest cost and obstacle.**

What you need is not a more powerful LLM, but a **bridge between your business databases and AI applications** — making data identifiable, queryable, governable, and safely reusable.

**That is exactly what OntiCards is built for**: an open-source, enterprise-grade AI data hub. It connects to your existing databases with zero intrusion, lets AI automatically understand data semantics, and supports natural-language self-service queries, cross-source federation, intelligent quality checks, and permission-based auditing. **Plug it in and go — dramatically lowering the barrier to enterprise data-AI adoption.**

## ✨ Core Value: Solving the Four Biggest Pain Points of Enterprise Data AI

- **Breaks down data silos**: Compatible with 9 mainstream and domestic Chinese databases, unifying multi-source heterogeneous data on a single platform

- **Solves "AI can't read your data"**: AI automatically generates Smart Data Cards that structure table purposes, column definitions, sensitivity flags, and business relationships — so LLMs can precisely understand your proprietary data

- **Solves slow data access**: No more hand-written SQL or cross-department coordination. Business users query in natural language, with multi-step reasoning and cross-database federation in one click

- **Solves unsafe, unregulated rollouts**: Built-in data masking, permission isolation, operation auditing, and SSO — balancing intelligence with enterprise-grade security and compliance

## 🚀 Real-World Deployments: Production-Grade, Proven at Scale

OntiCards is not an experimental demo. It runs stably in production at leading enterprises across **automotive, finance, government, manufacturing, education, and real estate**, adapted to real-world complexity:

- **Automotive (automaker with million-unit annual sales)**: Rebuilt marketing data workflows with conversational natural-language queries — replacing 5-day cross-department manual rollups, covering 14 BI dashboards, with query accuracy above 85% and response rate above 90%

- **Finance (city commercial bank with RMB 600 billion in assets)**: Consolidated bank-wide policies and business data into a unified knowledge-and-data Q&A entry point; AI output at 4x the speed of human experts, delivering second-level self-service answers

- **Government transportation (provincial group, 6,000+ km of roads)**: Intelligent monitoring-data analysis — AI precisely identifies 8 types of abnormal events and 7 types of equipment faults with ≥85% accuracy and <5-second response, shifting from "humans watching screens" to "AI-driven alerts"

- **High-end manufacturing (leading PCB manufacturer)**: Multimodal AI automatically extracts structured parameters from order drawings — "drawings in, data out" — replacing manual entry and verification, sharply reducing error rates and labor costs

- **Real estate legal**: AI-powered contract review compresses per-contract review from 40 minutes to 4, automatically flagging risky clauses with tiered alerts and structured annotations

More industry solutions: [https://www.step2.com.cn/zh-cn/solutions](https://www.step2.com.cn/zh-cn/solutions)

## 🔥 Full Capability Overview

### 1. Universal Multi-Source Data Connectivity

Zero-intrusion access to mainstream open-source, commercial, and domestic Chinese databases — fully aligned with localization requirements:

- Open source: MySQL 5.7+, PostgreSQL 10+, SQLite 3.x

- Commercial: Oracle 11g+, SQL Server 2012+

- Domestic Chinese: DMDB V8 (达梦), KingBase (人大金仓), OceanBase (MySQL tenant)

- Big data engine: Trino

### 2. AI-Powered Data Understanding (Core Differentiator)

Automated, domain-wide data asset inventory — turning cryptic database metadata into assets that are business-readable and AI-recognizable:

- Smart Data Cards: auto-generated business manuals for every table, covering purpose, column definitions, enum rules, and applicable scenarios

- Intelligent identification: automatic sensitive-column flagging, table relationship mapping, and domain-wide data profiling

- Business glossary: custom industry metrics and business definitions, unifying the company's data language and eliminating ambiguity

- Column annotation enhancement: bulk import of Excel data dictionaries to precisely correct AI parsing errors

### 3. Natural-Language Data Querying (NL2SQL)

- Zero SQL barrier: ask questions in business language; the system adapts to each database's dialect and generates executable, safe SQL

- Complex reasoning: multi-step decomposition, nested queries, and aggregations for complex analytical scenarios

- Cross-source federation: one question joins data across databases, automatically aligning columns and merging results — breaking down silos for good

- Safety validation: high-risk DML/DDL statements are automatically blocked; only read-only queries pass through

### 4. Fully Automated Data Quality Checks

14 built-in quality rule types, plus AI-assisted modeling and custom rules — a closed-loop data governance system:

- Coverage: validity, uniqueness, consistency, completeness, value-range compliance, date compliance, and more

- Output: automated checks, quality scoring, root-cause tracing, bulk remediation, and standardized report export

- Fit: routine data inspections, go-live validation, data reconciliation, and continuous governance

### 5. Enterprise-Grade Security and Integration

Built for production-grade private deployment, meeting compliance, access-control, and integration requirements:

- Security: data masking, row/column-level permission isolation, query auditing, and operation log tracing

- Login integration: JWT-SSO single sign-on and multi-account permission management

- Open integration: API-Key interfaces for seamless connection to AI agents, RPA, BI platforms, and in-house systems

- Operations: query traffic monitoring, token cost statistics, service health alerts, and log diagnostics

## 💻 Quick Deployment (3 Steps, One Command)

### Requirements

| Item | Minimum | Recommended |
| --- | --- | --- |
| OS | Linux x86_64 | Ubuntu 22.04/24.04 |
| CPU / RAM | 2 cores, 4 GB | 4 cores, 8 GB+ |
| Disk | 20 GB | 50 GB+ |
| Runtime | Docker 20.10+, Docker Compose 2.0+ | Latest stable |

### Deployment Commands

```bash
# 1. 克隆项目
git clone https://github.com/stepll2026/OntiCards.git
cd OntiCards

# 2. 初始化环境变量
cp .env.example .env
chmod 600 .env

# 3. 校验配置并一键启动
docker compose config -q
docker compose up -d --build

# 访问地址
http://your-ip:9107
```

⚠️ **Must change for production**: database passwords, secret keys, SSO secret, domain allowlist, and other core configuration

Full deployment, offline deployment, upgrades, and HTTPS setup: [Deployment Guide](https://www.step2.com.cn/docs/zh-cn/deployment.html)

## ⚡ 5-Minute Quick Start

1. Log in and configure an LLM (GPT, Claude, Qwen, DeepSeek, Zhipu, and local Ollama models are supported)

2. Add a business data source; the system automatically pulls metadata and generates Smart Data Cards

3. (Optional) Upload a business dictionary, create a glossary, and run domain-wide or targeted data inventory to sharpen understanding

4. Query in natural language, configure quality rules, review monitoring dashboards, and integrate third-party systems

Full walkthrough: [User Guide](https://www.step2.com.cn/docs/zh-cn/user-guide.html)

## 👥 Who It's For

- **Tech leads / architects**: Stand up an enterprise data-AI foundation — unified access, governance, and security — at lower cost

- **Developers / data engineers**: Less repetitive SQL, cross-database debugging, and reconciliation; more dev and ops efficiency

- **Data analysts**: Self-serve ad-hoc queries and cross-source analysis; focus on insight, not data wrangling

- **Data governance specialists**: Standardized data inventory, quality checks, terminology alignment, and quality reporting

- **Business / management**: Zero technical barrier to self-service data access — real-time numbers for business decisions

- **AI application developers**: A unified, secure data entry point for AI agents, RPA, and BI

## 🛠️ Tech Stack

**Frontend**: Next.js 14, React 18, TypeScript 5, Ant Design 5, Tailwind CSS, Recharts, i18n internationalization

**Backend**: Flask, SQLAlchemy, PostgreSQL, Weaviate vector database, APScheduler, pandas

**AI**: Compatible with major public LLMs and local private models; supports Embedding semantic retrieval, Rerank, and multi-step reasoning

## 📚 Official Documentation

- [Deployment Guide](https://www.step2.com.cn/docs/zh-cn/deployment.html): environment setup, one-command deployment, production tuning, upgrades

- [User Guide](https://www.step2.com.cn/docs/zh-cn/user-guide.html): full feature walkthrough, data source management, governance, NL querying

- [API Reference](https://www.step2.com.cn/docs/zh-cn/api-reference.html): third-party integration and API conventions

- [SSO-JWT Integration](https://www.step2.com.cn/docs/zh-cn/sso-jwt.html): enterprise single sign-on

- [Troubleshooting](https://www.step2.com.cn/docs/zh-cn/troubleshooting.html): startup errors, model calls, database connection issues

- [FAQ](https://www.step2.com.cn/docs/zh-cn/faq.html): answers to common questions

## 🤝 Contributing

Issues, feature requests, and pull requests are all welcome — let's build this together!

Contribution guidelines: see `./CONTRIBUTING.md`

## 📄 License

The open-source edition of OntiCards is released under **AGPL-3.0**. If you modify the project and offer it as a network service, you must release your modified source code. For commercial private deployment, custom development, or multi-tenant enterprise capabilities, contact us for a commercial license.

## 💼 Commercial Services

The open-source edition is **free forever** and can be self-hosted in production. For the following enterprise capabilities, ask about our commercial services:

- **Industry-specific ontology customization**: tailored data ontologies, business glossaries, and knowledge graphs for manufacturing, automotive, finance, government, and other verticals

- **Enterprise permission architecture**: private multi-tenant setups with fine-grained row/column-level and field-level access control, fitting large-group organizational structures and data-isolation compliance

- **Advanced data governance services**: intelligent reconciliation, bulk anomaly remediation, and custom governance rules for a standardized, traceable governance system

- **Private deployment services**: dedicated deployment, environment adaptation, upgrades, and fail-safe operations support for stable production

- **Custom development & dedicated advisors**: iterative feature development, integration with existing systems, and one-on-one technical consultation

## 📞 Contact

- Bug reports & feature requests: [GitHub Issues](https://github.com/stepll2026/OntiCards/issues)

- Product website & industry solutions: [https://www.step2.com.cn](https://www.step2.com.cn)

**OntiCards — Bringing every enterprise's private data safely, efficiently, and affordably into the AI era**

> (Note: Some content may be AI-generated)
