🌐 語言切換：
[简体中文](README.md) | **繁體中文(香港)** | [English](README_en.md)

# OntiCards

![OntiCards — 企業級 AI 數據中樞](onticards-banner.jpg)

> **企業級 AI 數據中樞** ｜ 讓企業的數據「會說話、聽得懂、可治理」

[![Version](https://img.shields.io/badge/version-2.4.0-blue)](https://github.com/stepll2026/OntiCards/releases)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-%E4%B8%AD%E6%96%87%E6%96%87%E6%A1%A3-8A2BE2)](https://www.step2.com.cn/docs/zh-cn/)
[![Docker Compose](https://img.shields.io/badge/deploy-Docker%20Compose%20ready-2496ED)](https://www.step2.com.cn/docs/zh-cn/deployment.html)

## 你是否正在為這些事情頭痛？

- 業務同事想要一個數字，先提需求、再排隊、等數據團隊寫 SQL，一星期過去了報表還沒有影
- 系統裡躺著幾百上千張表，沒有人說得清每張表是做甚麼的、欄位是甚麼意思——想問數據，得先找到「當年建表的那個人」
- 數據散落在 MySQL、Oracle 和各個業務系統裡，跨庫取數靠匯出 Excel 人手拼接，拼完兩個部門的數字還對不上
- 數據質素全靠運氣，報表錯了沒有人知道，直到老闆在會議上指出來
- 不知道誰在甚麼時間查了甚麼數據，敏感資訊近乎裸奔，審計來了拿不出任何紀錄

這些問題的根源是同一個：**數據能力被鎖在少數會寫 SQL 的人手裡，而數據本身說不清、找不著、信不過、管不住。**

## OntiCards 是甚麼

OntiCards 是一個開源的企業級 AI 數據中樞（AI Data Hub），連接你現有的業務數據庫，讓數據從「只有會寫 SQL 的人才能用」，變成**每個懂業務的人都能直接查詢、質檢、管理、審計的資產**：

- **不用寫 SQL**：用日常業務語言提問，系統自動完成多步推理、數據庫方言適配與 SQL 安全校驗，業務人員即可自助取數
- **每張表都有說明書**：AI 自動生成智能數據卡片——欄位畫像、敏感欄位三層識別、業務術語與表關係盤點，數據第一次講得清自己是甚麼
- **一次提問，跨庫取數**：跨多個數據庫自動對齊與合併結果，不用再匯出 Excel 人手拼接
- **數據質素有人盯著**：14 種質檢規則類型、AI 自然語言建規則、質素評分與報告匯出，出問題先看報告，而不是先捱罵
- **企業級安全與審計**：數據源隔離、敏感資訊脫敏、全程查詢審計留痕、API-Key 整合與 JWT-SSO 單一登入，私有化部署，數據不出內網

> 📌 開源版完全免費、支援私有化自托管；多租戶、行列級權限等企業能力以商業服務形式提供，見文末[商業服務](#商業服務)。

## 核心能力一覽

- **多源數據接入**：支援 MySQL、PostgreSQL、Oracle、SQL Server、SQLite、Trino，以及達夢、人大金倉、OceanBase 等國產數據庫，共 9 類數據源
- **智能數據理解**：每張表自動生成「智能數據卡片」業務說明書，含欄位畫像、敏感欄位識別、業務術語庫與 AI 表關係盤點
- **自然語言查詢**：NL2SQL 多步推理、多數據庫方言適配、業務術語自動展開、SQL 安全校驗
- **跨源融合查詢**：一次提問跨多個數據庫，自動對齊與合併結果，打破數據孤島
- **數據質檢**：14 種質檢規則類型、AI 自然語言建規則、質素評分與質檢報告匯出
- **企業級平台能力**：數據源隔離、敏感資訊脫敏、查詢審計、API-Key 整合、JWT-SSO 單一登入、查詢監控與成本統計

## 快速開始

### 環境要求

| 項目 | 要求 |
| --- | --- |
| 作業系統 | Linux x86_64（推薦 Ubuntu 22.04/24.04） |
| Docker | Docker Engine + Docker Compose 外掛 **v2.24.0+** |
| 最低配置 | 2 核 CPU / 4 GB 記憶體 |
| 瀏覽器 | 現代桌面瀏覽器（Chrome / Edge） |

### 三步啟動

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

> 📖 完整部署說明（含國內鏡像加速、離線部署、端口變更、升級流程）見官方文件：[部署指南](https://www.step2.com.cn/docs/zh-cn/deployment.html)

### 5 分鐘體驗流程

1. 登入系統，設定大模型（支援通義千問、DeepSeek、智譜 AI、GPT、Claude 等）
2. 新增業務數據源
3. 等待自動生成**智能數據卡片**，補充業務術語與表關係盤點
4. 用自然語言提問，自助查詢數據
5. 體驗數據質檢、查詢歷史、監控面板與 API 整合

詳細操作步驟見官方文件：[用戶手冊](https://www.step2.com.cn/docs/zh-cn/user-guide.html)

## 支援數據源

| 數據庫 | 版本 | 備註 |
| --- | --- | --- |
| MySQL | 5.7+ | 主流開源數據庫 |
| PostgreSQL | 10+ | 兼容人大金倉 |
| Oracle | 11g+ | 商業數據庫 |
| SQL Server | 2012+ | 微軟數據庫 |
| SQLite | 3.x | 輕量測試 |
| Trino | Latest | OLAP 引擎 |
| 達夢 DMDB | V8 | 國產數據庫 |
| KingBase（人大金倉） | 最新版 | 國產數據庫 |
| OceanBase | MySQL 租戶 | 分散式國產數據庫 |

## 適用場景

- **業務營運**：自助取數、日常監控、異常排查
- **數據分析師**：臨時查詢、跨庫數據整合、快速驗證分析假設
- **數據治理專員**：設定質檢規則、輸出數據質素報告、統一業務術語
- **管理層**：多數據源匯總對比分析
- **IT 與數據團隊**：數據源管理、權限管控、查詢審計監控
- **第三方系統整合**：透過 API-Key 對接智能體、RPA、BI 平台（支援 [SSO-JWT 整合](https://www.step2.com.cn/docs/zh-cn/sso-jwt.html)）

## 技術棧

### 前端

| 分類 | 技術 | 說明 |
| --- | --- | --- |
| 核心框架 | Next.js 14 · React 18 · TypeScript 5 | 全棧框架 + SSR |
| UI 元件 | Ant Design 5 · Tailwind CSS 3 · Sass/SCSS | 企業級元件 + 主題切換 |
| 數據可視化 | Recharts · D3.js | 圖表與圖形 |
| 國際化 | i18next · next-i18n-router | 多語言 + 路由切換 |
| Markdown | react-markdown · remark-gfm · KaTeX | 文件渲染、公式、程式碼高亮 |

### 後端

| 分類 | 技術 | 說明 |
| --- | --- | --- |
| 核心框架 | Flask 2.3.3 · Flask-RESTful · Gunicorn | RESTful API + WSGI |
| 主數據庫 | PostgreSQL 10+ · SQLAlchemy 2.0 | 元數據與業務數據儲存 |
| 向量數據庫 | Weaviate 1.36.0 | 語義向量儲存與檢索 |
| AI / LLM | 通義千問 · DeepSeek · 智譜 AI · GPT · Claude · Azure OpenAI | 支援 Embedding / Rerank |
| 定時任務 | APScheduler | 定時盤點與質檢調度 |
| 數據處理 | pandas · numpy · openpyxl · python-docx | 數據處理 + 報告生成 |
| 安全 | cryptography · PyJWT · passlib/bcrypt | AES 加密 + JWT + 密碼雜湊 |

## 文件中心

全部文件已遷移至官方網站文件中心，請瀏覽：**[https://www.step2.com.cn/docs/zh-cn/](https://www.step2.com.cn/docs/zh-cn/)**

| 文件 | 連結 |
| --- | --- |
| 部署指南 | [deployment](https://www.step2.com.cn/docs/zh-cn/deployment.html) |
| 用戶手冊 | [user-guide](https://www.step2.com.cn/docs/zh-cn/user-guide.html) |
| API 介面參考 | [api-reference](https://www.step2.com.cn/docs/zh-cn/api-reference.html) |
| SSO-JWT 整合 | [sso-jwt](https://www.step2.com.cn/docs/zh-cn/sso-jwt.html) |
| FAQ | [faq](https://www.step2.com.cn/docs/zh-cn/faq.html) |
| 問題排查指南 | [troubleshooting](https://www.step2.com.cn/docs/zh-cn/troubleshooting.html) |
| 更新日誌 | [changelog](https://www.step2.com.cn/docs/zh-cn/changelog.html) |

## 參與貢獻

歡迎提交 Issue、Feature Request 和 Pull Request！
請先閱讀：[貢獻指南](./CONTRIBUTING.md)

## License

OntiCards 開源版基於 **[AGPL-3.0](./LICENSE)** 協議開源。

> 簡單理解：如果你基於本項目修改並對外提供網絡服務，需要公開修改後的源碼。商業授權需求請參考下方[商業服務](#商業服務)。

## 商業服務

OntiCards 開源版可免費部署使用。如需以下能力，歡迎聯絡我們：

- 多租戶版本、行列級權限
- 企業版數據治理增強、數據校驗對賬
- 定製開發與私有化實施服務
- 專業技術支援

## 聯絡我們

- **GitHub Issues**：[stepll2026/OntiCards/issues](https://github.com/stepll2026/OntiCards/issues) — 提交 Bug 與需求反饋
- **產品官網**：[https://www.step2.com.cn](https://www.step2.com.cn) — 產品介紹、解決方案與文件中心

---

**OntiCards** — 讓企業的數據「會說話、聽得懂、可治理」
