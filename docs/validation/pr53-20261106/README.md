# PR #53 列名引用验证

## 修复了什么

原贡献只替换了创建规则的两处引用，遗漏复合预览；原引用工具也没有转义列名内的闭合符。
本轮补全创建、复合更新和预览的统一引用，转义双引号、反引号和右方括号；占位符替换跳过字符串与已引用的标识符，避免名为 column 的列被预览再次替换。

## 有什么作用

MySQL、SQL Server 等生成的列引用跟随数据源方言；含引号的列名不会因本轮引用过程逃出标识符。
例如名为 a"b 的列在双引号方言生成 "a""b"。本变更不声称限制任意 SQL 表达式的能力。

## 验证结果

- 基线：main 2e597d05f3673891f9ffdef08e2c45084dbd42dc；原贡献 63cc0dccfc6a078043e329ace34802e78b886891。
- 初轮生产代码及测试版本：2043e4099e2437a439e387461471e7d99e6db9b1；独审发现公开预览构建器仍重复替换，补充第6方法在修正前复现10失败/10错误（[review-red.log](review-red.log)），本目录最终日志对应包含修正的提交，文件SHA256见下。
- 运行于 kol-stage2，宿主 Python 3.12.3，无镜像构建；只传输审阅过的四个 Python 文件，无环境文件或应用凭据。
- 隔离目录 /tmp/onticards-pr53-b4799bf7。
- 修正前 python3 test_column_quoting.py：exit 1，5方法中30失败、12错误（含子用例），见 [red.log](red.log)。
- 修正后 python3 test_column_quoting.py：exit 0，6方法通过（含真实预览入口调用的两种 SQL 构建器）；覆盖10方言引用、重复适配、字面量、反斜杠和 SQLite 内存数据库真实查询，见 [green.log](green.log)。
- python3 test_dialect_adapter.py：exit 0，原31测试通过，见 [dialect.log](dialect.log)。
- [实际测试文件 SHA256](tested-files.sha256)。
- 预览测试从真实源码 AST 提取两方法，跳过应用初始化；不是完整 HTTP/API 集成测试。
- 独立审查与清理结果由原 PR 正文及工单最终报告记录。

## 剩余限制

没有执行真实 MySQL、SQL Server、Oracle 等引擎或完整业务服务/浏览器；无 UI 改动，无截图要求。
没有运行 GitHub-hosted CI、调用模型或访问生产数据库。
引用和占位符处理不是完整 SQL 验证器；表达式本身的安全治理属于另一项独立工作。
