# 贡献指南

感谢您对 OntiCards 的关注！我们欢迎各种形式的贡献，包括但不限于：

- 报告 Bug
- 提出新功能建议
- 完善文档
- 提交代码修复
- 添加新的数据库支持

---

## 一、如何贡献

### 1.1 报告 Bug

如果您发现了 Bug，请通过 GitHub Issues 报告，包含以下信息：

- Bug 描述（清晰、具体）
- 复现步骤
- 预期行为 vs 实际行为
- 环境信息（操作系统、Docker 版本、数据库类型等）
- 错误日志（敏感信息请脱敏）

### 1.2 提出功能建议

我们非常欢迎功能建议！请通过 GitHub Issues 提出，包含：

- 功能描述
- 使用场景
- 可能的实现方案（可选）

### 1.3 完善文档

文档改进同样重要，包括：

- 修正错别字或错误描述
- 补充遗漏的内容
- 改进示例代码
- 翻译文档

### 1.4 提交代码

#### 开发环境准备

```bash
# 1. Fork 项目
# 2. 克隆您 fork 的仓库
git clone https://github.com/your-username/onticards.git
cd onticards

# 3. 创建分支
git checkout -b feature/your-feature-name

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置本地开发环境
cp .env.prod .env
# 编辑 .env 填入必要配置
```

#### 开发规范

- **代码风格**：遵循 PEP 8
- **命名规范**：使用有意义的变量和函数名
- **注释**：复杂逻辑需要添加注释
- **测试**：新增功能请添加测试用例

#### 提交代码

```bash
# 1. 添加修改的文件
git add .

# 2. 提交（使用清晰简洁的提交信息）
git commit -m "feat: 添加 XXX 功能"
git commit -m "fix: 修复 XXX 问题"
git commit -m "docs: 更新 XXX 文档"

# 3. 推送到您的 fork
git push origin feature/your-feature-name

# 4. 创建 Pull Request
```

#### 提交信息规范

建议使用以下前缀：

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档更新 |
| `style:` | 代码格式调整 |
| `refactor:` | 代码重构 |
| `test:` | 测试相关 |
| `chore:` | 构建/工具相关 |

---

## 二、新增数据库支持

如果您想添加新的数据库支持，请：

1. 先通过 Issue 与我们讨论
2. 参考现有数据库适配器的实现
3. 确保支持以下基本功能：
   - 连接测试
   - 表结构读取
   - 数据查询

---

## 三、问题解答

如果您有任何问题，欢迎通过以下方式联系我们：

- GitHub Issues：https://github.com/your-org/onticards/issues
- 提交 Issue 时请选择合适的模板

---

## 四、许可证

通过贡献代码，您同意将您的代码以 AGPLv3 许可证开源。

---

再次感谢您的贡献！
