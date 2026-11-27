# 应用 JWT 和 SSO 签名配置

`SECRET_KEY` 专用于 OntiCards 应用会话签发和校验。请使用 Python `secrets.token_hex(32)` 生成 32 个随机字节的 64 个十六进制字符，直接写入受控秘密存储。多个 API 副本必须使用同一部署秘密版本，发布时用两个副本交叉验证正常登录后的应用 Token。

`SSO_SECRET_KEY` 专用于外部身份提供商的入站令牌验签。去除首尾空白后至少 32 字符，保持与外部提供商现有协议相同的字节。换钥需单独协调。两把键必须独立。启动时拒绝缺失、短键、明显重复或规律字节、历史模板值和相同键。程序能拒绝常见弱输入，随机性由生成与秘密管理流程保证。

## Compose

首次执行 `python scripts/init_env.py`，在本地生成两份权限受限的秘密文件和缺失的 `.env`。Compose 仅将两份文件挂载到 API。Compose 仅呈现文件引用。Web 和 Nginx 不挂载签名秘密。

已有部署须通过受控秘密管理渠道，将当前有效的 SSO 字节放入 `.secrets/onticards_sso_verification_key`。将已批准可继续使用的应用键放入 `.secrets/onticards_jwt_signing_key`，或按下文走换钥。也可用 `ONTICARDS_JWT_KEY_PATH` 和 `ONTICARDS_SSO_KEY_PATH` 指定相应文件路径。Linux 上使用服务运行用户拥有的普通文件，权限 `0600`，避免符号链接。启动前移除旧 `.env` 中的两项明文设置或将其另存于批准的凭据存储。脚本保留已有配置和已存在的秘密文件。

## 独立 API

`python scripts/init_env.py --api-only` 为缺失的本地 `OntiCards_Api/.env` 分别生成高熵应用和 SSO 键。独立运行可由秘密管理器注入 `SECRET_KEY` 与 `SSO_SECRET_KEY`，也可使用 `SECRET_KEY_FILE` 与 `SSO_SECRET_KEY_FILE` 指向绝对路径。单把键仅配置一种输入，文件限制与 Compose 相同。所有 API 运行入口使用同一种启动校验。新库先在 API 目录执行 `flask initialize-schema` 和 `flask db upgrade`，再启动 `gunicorn 'app:create_runtime_app()'` 或 `python app.py`。

## 应用键轮换

1. 维护者生成新的应用键和独立的秘密版本 ID，记录实例覆盖情况。外部 SSO 继续沿用已约定的键。
2. 摘除全部旧 API，统一更新所有 API 的秘密版本并重建。确认新旧副本不会同时对外提供流量。用一个副本上的新登录 Token 访问另一副本，再确认旧 Token 被拒绝。
3. 确认 readiness 和登录正常，重新放流。通知用户重新登录，撤销旧秘密版本的读取权限，保留轮换时间与批准记录。
4. 如果新版本出现问题，回滚应用镜像到支持当前安全密钥的版本，继续使用新密钥。若无法统一配置，保持摘流。历史已公开或疑似泄露的键不可重新启用。

## 数据源加密密钥

两个初始化模式均在新建的 `.env` 中保存独立生成的 `CONNECT_INFO_MASTER_KEY`。API 启动需要有效的持久值，会拒绝已知公开模板、空值和无效值，错误消息只包含配置名和操作说明。有效的历史值继续使用原有密钥派生，保留现有密文的解密行为。

已有 `.env` 保持原样。若脚本提示公开模板、无效密钥或缺失，先确认是否存在已加密的连接凭据。没有存量密文时，通过安全配置途径补齐独立随机的 32 字节 Base64 值。有存量密文时，须按备份、隔离重加密和回滚流程办理变更。先恢复获批准的原始有效密钥，避免覆盖仍需解密的数据。
