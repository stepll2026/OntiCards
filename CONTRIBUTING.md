# OntiCards 贡献指南

感谢您关注并参与 OntiCards！

我们欢迎各种形式的贡献，包括但不限于：

- 🐛 报告 Bug
- 🚀 反馈部署与升级问题
- 💡 提出功能建议
- 📚 完善项目文档
- 🔧 提交代码修复或新功能
- 🗄️ 添加新的数据库支持
- 💬 参与技术讨论与经验分享

---

## 一、问题反馈与社区交流

### 1.1 Bug 反馈

如果您发现 OntiCards 存在可复现的软件异常，请通过 GitHub Issues 提交：

https://github.com/stepll2026/OntiCards/issues

请选择：

**🐛 Bug Report**

提交时请尽量提供：

- OntiCards 版本
- 操作系统及运行环境
- 部署方式
- 问题描述
- 完整复现步骤
- 预期行为与实际行为
- 相关错误日志或截图

---

### 1.2 部署问题

如果您遇到以下问题：

- Docker Compose 启动失败
- 镜像构建失败
- 数据库初始化异常
- PostgreSQL / Weaviate 连接异常
- API 或 Web 服务启动异常
- Nginx 或页面访问异常
- LLM / Embedding / Rerank 配置问题
- 版本升级问题

请通过 GitHub Issues 提交，并选择：

**🚀 Deployment Issue**

建议提供：

- OntiCards 版本
- 操作系统
- Docker 版本
- Docker Compose 版本
- 问题发生阶段
- 执行过的命令
- 相关容器状态及日志
- 是否修改过默认配置

---

### 1.3 功能建议

如果您有明确的新功能需求或产品改进建议，请通过 GitHub Issues 提交，并选择：

**💡 Feature Request**

建议说明：

- 实际使用场景
- 当前存在的问题
- 希望实现的功能
- 已尝试的替代方案（如有）
- 可能的实现方案或参考项目（可选）

---

### 1.4 使用交流与技术讨论

如果属于以下内容：

- OntiCards 使用方法咨询
- 技术方案讨论
- 数据库或模型配置经验
- 产品想法交流
- 部署实践分享
- 应用案例分享
- 尚未形成明确开发需求的想法

请优先前往 GitHub Discussions：

https://github.com/stepll2026/OntiCards/discussions

> Issues 主要用于跟踪明确的 Bug、部署问题和功能需求；  
> Discussions 更适合一般交流、问答、想法讨论和经验分享。

---

## 二、提交代码

### 2.1 Fork 项目

首先在 GitHub Fork OntiCards：

https://github.com/stepll2026/OntiCards

然后克隆您自己的仓库：

```bash
git clone https://github.com/your-username/OntiCards.git
cd OntiCards
```

建议添加官方仓库作为 `upstream`：

```bash
git remote add upstream https://github.com/stepll2026/OntiCards.git
```

可以通过以下命令确认：

```bash
git remote -v
```

---

### 2.2 创建开发分支

请尽量不要直接在 `main` 分支进行功能开发。

新增功能建议使用：

```bash
git checkout -b feature/your-feature-name
```

Bug 修复建议使用：

```bash
git checkout -b fix/your-bug-name
```

文档修改可以使用：

```bash
git checkout -b docs/your-doc-change
```

---

## 三、项目结构

OntiCards 仓库主要结构如下：

```text
OntiCards/
├── .github/
│   └── ISSUE_TEMPLATE/        # GitHub Issue 模板及相关配置
│
├── nginx/                     # Nginx 配置
│
├── OntiCards_Api/             # 后端 API 服务
│   ├── extensions/
│   ├── libs/
│   ├── migrations/
│   ├── models/
│   ├── static/
│   ├── task/
│   ├── test/
│   ├── utils/
│   ├── views/
│   ├── .env.prod              # API 独立运行配置模板
│   ├── Dockerfile
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   └── ...
│
├── OntiCards_Web/             # 前端 Web 服务
│
├── .env.prod                  # 完整 Docker Compose 部署配置模板
├── .gitignore
├── CONTRIBUTING.md
├── docker-compose.yaml
├── LICENSE
├── README.md
├── README_en.md
└── README_zh-HK.md
```

---

## 四、环境配置

OntiCards 仓库中存在两份 `.env.prod`，两者用途不同。

### 4.1 根目录 `.env.prod`

根目录：

```text
.env.prod
```

用于通过 Docker Compose 部署完整的 OntiCards，包括前端、后端及相关依赖服务。

推荐使用方式：

```bash
python3 scripts/init_env.py
```

根据实际环境修改生成的：

```text
.env
```

全新数据库先完成 [首次管理员引导](docs/admin-bootstrap.md)。已有部署可按常规方式启动：

```bash
docker compose config -q
docker compose up -d --build
```

查看服务状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs --tail=200
```

> 根目录 `.env.prod` 是公开的部署配置模板。  
> 实际密码、密钥、域名等配置应写入本地生成的 `.env`。

---

### 4.2 `OntiCards_Api/.env.prod`

文件：

```text
OntiCards_Api/.env.prod
```

仅用于单独开发、调试或运行 OntiCards 后端 API。

如果您需要部署完整的 OntiCards，请使用仓库根目录 `.env.prod`，不要同时修改两份配置。

如果只需要独立运行 API，先在仓库根目录执行以下命令，再进入 API 目录：

```bash
python3 scripts/init_env.py --api-only
cd OntiCards_Api
```

根据实际开发环境参考：

```text
.env.prod
```

脚本保留已有的 OntiCards_Api/.env。全新数据库还需按 [首次管理员引导](docs/admin-bootstrap.md) 配置授权，并按 [签名配置](docs/signing-keys.md) 初始化、迁移和启动。可按需配置数据库、Weaviate、前端地址等参数。应用启动时，SSO_SECRET_KEY 去除首尾空白后须至少 32 个字符。现有 SSO 部署应与接入方协调换钥。

安装后端依赖：

```bash
pip install -r requirements.txt
```

具体启动方式请以当前后端源码及相关配置为准。

---

### 4.3 `.env` 文件管理规则

仓库中的：

```text
.env.prod
OntiCards_Api/.env.prod
```

属于配置模板，可以纳入 Git 版本管理。

实际运行时产生的：

```text
.env
OntiCards_Api/.env
```

不应提交到 Git 仓库。

请确保 `.gitignore` 正确忽略实际运行配置。

---

## 五、开发规范

### 5.1 后端开发

后端代码位于：

```text
OntiCards_Api/
```

开发时请注意：

- 遵循项目现有 Python 代码风格
- 使用清晰、有意义的变量、函数和类名称
- 复杂业务逻辑应添加必要注释
- 尽量保持现有模块职责和目录结构
- 修改现有接口时注意兼容性
- 新增功能应尽量补充对应测试
- 修复 Bug 时建议增加对应回归测试
- 避免在同一个 Pull Request 中进行无关的大范围重构

---

### 5.2 前端开发

前端代码位于：

```text
OntiCards_Web/
```

开发时请注意：

- 遵循项目现有 TypeScript / React / Next.js 代码风格
- 保持组件职责清晰
- 尽量复用现有组件和公共逻辑
- 避免无必要的大范围格式化
- 修改 UI 时注意现有布局和交互一致性
- 新增交互时注意加载、异常、空状态等场景
- 不要在功能修改中混入无关页面重构

前端依赖安装及独立开发方式，请以 `OntiCards_Web/` 中当前实际依赖配置为准。

---

### 5.3 修改范围

提交代码时建议遵循：

**一个 Pull Request 解决一个明确问题。**

尽量避免：

- 同时处理多个无关需求
- 无必要的大范围重构
- 无意义格式化整个文件
- 修改与当前需求无关的配置
- 删除或改变与本次修改无关的功能

这样可以降低代码审查难度，也方便问题回溯和版本维护。

---

## 六、提交前检查

提交 Pull Request 前，请至少确认：

- 修改内容可以正常运行
- 没有提交真实密码、Token、Secret 等敏感信息
- 没有意外提交 `.env`
- 没有提交临时文件、日志文件或构建产物
- 新增功能没有破坏原有主要功能
- 相关测试已经执行
- 文档与实际行为保持一致
- 如果修改了配置项，对应文档已同步更新

完整项目可以至少执行：

```bash
docker compose config -q
```

确认 Docker Compose 配置可以正常解析。

---

## 七、提交信息规范

建议使用清晰、统一的 Commit Message。

推荐前缀：

| 前缀        | 说明                     |
| ----------- | ------------------------ |
| `feat:`     | 新功能                   |
| `fix:`      | Bug 修复                 |
| `docs:`     | 文档更新                 |
| `style:`    | 不影响程序逻辑的格式调整 |
| `refactor:` | 代码重构                 |
| `test:`     | 测试相关                 |
| `chore:`    | 构建、工具或工程配置     |
| `perf:`     | 性能优化                 |

例如：

```bash
git commit -m "feat: add ClickHouse data source support"
```

```bash
git commit -m "fix: resolve PostgreSQL connection issue"
```

```bash
git commit -m "docs: update deployment guide"
```

请尽量避免含义不清的提交信息，例如：

```text
update
fix bug
modify
test
```

---

## 八、提交 Pull Request

开发完成后：

```bash
git add .
git commit -m "feat: describe your change"
git push origin feature/your-feature-name
```

然后在 GitHub 创建 Pull Request。

Pull Request 中请尽量说明：

- 本次修改解决了什么问题
- 主要修改内容
- 如何验证
- 是否涉及配置变化
- 是否存在兼容性影响
- 是否关联已有 Issue
- 如有 UI 调整，可提供截图

如果 PR 用于解决已有 Issue，可以在描述中使用：

```text
Fixes #123
```

GitHub 会在 Pull Request 合并后自动关闭对应 Issue。

---

## 九、新增数据库支持

如果您希望为 OntiCards 添加新的数据库类型，建议先通过 Issue 或 Discussions 与维护者沟通。

新增数据库适配时至少应考虑：

- 数据库连接
- 连接测试
- 数据库元数据读取
- 表结构读取
- 字段信息读取
- 数据类型兼容
- 只读数据查询
- SQL 方言适配
- 查询异常处理
- 与智能数据卡片能力的兼容
- 与自然语言查询能力的兼容
- 对应测试用例

请尽量参考项目中现有数据库适配实现，保持整体架构和行为一致。

---

## 十、文档贡献

文档贡献同样重要，我们欢迎：

- 修正错别字
- 修复错误描述
- 补充遗漏内容
- 完善部署说明
- 改进示例代码
- 补充 FAQ
- 完善 API 使用说明
- 优化问题排查文档
- 维护多语言文档

如果修改涉及 README，请注意同步维护：

```text
README.md
README_en.md
README_zh-HK.md
```

如果修改涉及环境变量、端口、部署方式或启动流程，也请同步检查相关 README 和部署文档。

---

## 十一、安全注意事项

> ⚠️ 请勿在 Issue、Discussion、Pull Request、代码提交、日志或截图中公开任何真实敏感信息。

包括但不限于：

- 数据库用户名和密码
- API Key
- Access Token
- JWT Secret
- SSO Secret
- Cookie
- 私钥
- 数据源连接凭据
- 企业内部敏感地址
- 真实生产账号
- 完整 `.env` 文件

仓库中的 `.env.prod` 应仅保存可以公开的模板值或安全默认值。

实际部署时生成的 `.env` 可能包含真实敏感配置，不应提交到 Git。

如果需要提供配置用于排查问题，请先完成脱敏。

如果发现可能被利用的安全漏洞，请避免在公开 Issue 或 Discussions 中直接披露完整攻击细节或敏感信息。

---

## 十二、问题与帮助

### 明确的 Bug、部署异常或功能需求

请提交 GitHub Issue：

https://github.com/stepll2026/OntiCards/issues

请选择对应模板：

- 🐛 Bug Report
- 🚀 Deployment Issue
- 💡 Feature Request

### 使用咨询、技术交流或经验分享

请前往 GitHub Discussions：

https://github.com/stepll2026/OntiCards/discussions

---

## 十三、许可证

OntiCards 开源版基于 **AGPL-3.0** 协议发布。

提交代码、文档或其他可版权化内容，即表示您同意您的贡献按照本项目适用的 **AGPL-3.0** 协议进行分发。

---

再次感谢您参与 OntiCards 的建设！
