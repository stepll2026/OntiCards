# OntiCards API SSO单点登录接入指南（JWT模式）

## 概述

本文档描述第三方系统如何通过JWT Token方式接入OntiCards单点登录系统。

---

## 一、接入流程

```
第三方系统 → 生成JWT Token → 拼接SSO登录URL → 用户浏览器跳转 → OntiCards验证并登录
```

---

## 二、JWT Token 规范

### 2.1 签名算法

- **算法**：`HS256`
- **编码**：`UTF-8`

### 2.2 Payload 参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `username` | string | ✅ | 用户唯一标识 |
| `user_id` | string | ✅ | 第三方系统用户ID |
| `nickname` | string | ❌ | 用户昵称，默认取username |
| `email` | string | ❌ | 用户邮箱 |
| `source` | string | ❌ | 来源标识，用于区分不同SSO来源，默认`default` |
| `exp` | number | ✅ | Token过期时间（Unix时间戳，UTC） |

### 2.3 Token生成示例

**Python**

```python
import jwt
from datetime import datetime, timedelta, timezone

# 共享密钥（需向OntiCards管理员获取）
SECRET_KEY = "your_shared_secret_key"

payload = {
    "username": "zhang_san",
    "user_id": "SYS_USER_001",
    "nickname": "张三",
    "email": "zhangsan@example.com",
    "source": "your_app_name",
    "exp": datetime.now(timezone.utc) + timedelta(minutes=5)  # 建议5分钟有效期
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
```

**Java**

```java
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

String secretKey = "your_shared_secret_key";

Map<String, Object> payload = Map.of(
    "username", "zhang_san",
    "user_id", "SYS_USER_001",
    "nickname", "张三",
    "email", "zhangsan@example.com",
    "source", "your_app_name"
);

String token = Jwts.builder()
    .claims(payload)
    .expiration(new Date(System.currentTimeMillis() + 5 * 60 * 1000)) // 5分钟
    .signWith(Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8)))
    .compact();

System.out.println(token);
```

**Node.js**

```javascript
const jwt = require('jsonwebtoken');

const secretKey = 'your_shared_secret_key';

const payload = {
    username: 'zhang_san',
    user_id: 'SYS_USER_001',
    nickname: '张三',
    email: 'zhangsan@example.com',
    source: 'your_app_name',
    exp: Math.floor(Date.now() / 1000) + 5 * 60  // 5分钟后过期
};

const token = jwt.sign(payload, secretKey, { algorithm: 'HS256' });
console.log(token);
```

---

## 三、构造SSO登录链接

### 3.1 基础URL

```
https://your-api-domain.com/sso/login
```

> 请将 `your-api-domain.com` 替换为OntiCards API的实际访问地址

### 3.2 URL参数

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `token` | ✅ | 上面生成的JWT Token |
| `redirect_url` | ❌ | 登录成功后跳转的前端地址，默认跳转到API根路径 `/` |

### 3.3 完整URL示例

**不带跳转地址（默认跳转到API根路径）**
```
https://api.example.com/sso/login?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**带跳转地址（跳转到前端首页）**
```
https://api.example.com/sso/login?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...&redirect_url=https://app.example.com/
```

### 3.4 注意事项

- `token` 参数需要URL编码，特别是包含特殊字符的情况
- 建议 `redirect_url` 使用完整URL（包含https://）
- `exp` 建议设置为5分钟，防止token泄露后被滥用

---

## 四、用户创建/登录逻辑

当用户首次通过SSO访问时，系统会：

1. **解析JWT Token** → 验证签名和过期时间
2. **提取用户信息** → 从payload获取 username、user_id、nickname等
3. **查询本地用户** → 根据 `idp_user_id` + `idp_source` 查找已存在用户
4. **创建新用户** → 如果是新用户，自动创建本地账户
5. **执行登录** → 调用 `login_user()` 完成会话建立
6. **跳转前端** → 根据 `redirect_url` 跳转到指定页面

### 4.1 用户名冲突处理

如果 `username` 已被本地普通用户（非SSO用户）使用，系统会自动重命名为 `username_sso`，避免冲突。

### 4.2 SSO用户标识

| 字段 | 说明 |
|------|------|
| `idp_user_id` | 第三方系统用户ID（来自JWT的 `user_id`） |
| `idp_source` | SSO来源标识（来自JWT的 `source`，默认`default`） |

这两个字段用于标识SSO用户，便于与本地用户区分。

---

## 五、错误码说明

| HTTP状态码 | error字段 | 说明 |
|------------|-----------|------|
| 400 | `缺少token参数` | URL中没有传token |
| 400 | `token中缺少必要的用户信息` | username或user_id为空 |
| 401 | `token已过期` | Token的exp已过期 |
| 401 | `token无效` | 签名验证失败 |
| 500 | `登录失败: xxx` | 服务器内部错误 |

---

## 六、前端适配说明

### 6.1 跳转方式

第三方系统只需将用户引导到上述SSO登录URL即可。可以使用以下方式：

**方式1：直接跳转（推荐）**
```javascript
window.location.href = `${SSO_BASE_URL}/sso/login?token=${token}&redirect_url=${encodeURIComponent(frontendUrl)}`;
```

**方式2：新窗口打开**
```javascript
window.open(`${SSO_BASE_URL}/sso/login?token=${token}`, '_blank');
```

### 6.2 前端是否需要修改

| 情况 | 是否需要适配 |
|------|-------------|
| 前端已有SSO跳转逻辑 | 只需修改跳转URL |
| 前端需要从URL获取用户信息 | 可能需要解析Token或调用API获取用户信息 |
| 前端完全依赖Cookie/Session | 无需修改，登录由后端处理 |

### 6.3 前端获取用户信息的建议

登录成功后，用户信息已存储在服务端Session中。前端可以通过以下方式获取：

**方式1：调用用户信息接口**
```
GET /console/api/user/me
Authorization: Bearer <your_token>
```

**方式2：后端Cookie自动携带**
如果前端和API同源，浏览器会自动携带Cookie，无需额外处理。

---

## 七、配置项

### 7.1 共享密钥配置

需要在OntiCards的 `.env` 文件中配置：

```env
SSO_SECRET_KEY=your_shared_secret_key
```

> ⚠️ 请联系OntiCards管理员获取实际的共享密钥

### 7.2 配置接口

可以访问 `/sso/config` 获取当前SSO配置信息：

```bash
curl https://api.example.com/sso/config
```

响应示例：
```json
{
    "callback_url": "https://api.example.com/sso/login",
    "required_fields": {
        "username": "string - 必填，用户唯一标识",
        "user_id": "string - 必填，第三方系统用户ID",
        "nickname": "string - 可选，用户昵称",
        "email": "string - 可选，用户邮箱",
        "source": "string - 可选，来源标识，默认default"
    },
    "token_expiry": "建议5分钟",
    "algorithm": "HS256"
}
```

---

## 八、接入检查清单

- [ ] 获取共享密钥（SSO_SECRET_KEY）
- [ ] 获取OntiCards API地址
- [ ] 确认前端跳转地址（redirect_url）
- [ ] 实现JWT Token生成逻辑
- [ ] 实现SSO跳转逻辑
- [ ] 测试登录流程
- [ ] 验证用户信息正确性

---

## 九、联系方式

如有问题，请联系OntiCards技术支持。