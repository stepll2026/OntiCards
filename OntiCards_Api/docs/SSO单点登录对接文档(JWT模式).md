# OntiCards API SSO单点登录接入指南（JWT模式）

## 概述

本文档描述第三方系统如何通过JWT Token方式接入OntiCards单点登录系统。

---

## 一、什么是JWT Token

JWT（JSON Web Token）是一种开放标准（RFC 7519），用于在各方之间安全地传输信息。JWT由**三部分**组成，用点号分隔：

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InpoYW5nX3NhbiIsInVzZXJfaWQiOiJTWVNfVVNFUl8wMDEifQ.signature
|______________|.|__________________________________________|.______________|
    Header      |              Payload                      |   Signature
     头部        |              用户数据                      |     签名
```


| 部分   | 名称            | 作用                | 示例内容                                           |
| ---- | ------------- | ----------------- | ---------------------------------------------- |
| 第一部分 | Header（头部）    | 声明算法和类型           | `{"alg":"HS256","typ":"JWT"}`                  |
| 第二部分 | Payload（负载）   | 存放实际的用户数据         | `{"username":"zhang_san","user_id":"001",...}` |
| 第三部分 | Signature（签名） | 用密钥对前两部分签名，确保不被篡改 | `SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`  |


---

## 二、快速开始

### 2.1 客户需要准备的配置


| 配置项                 | 说明                | 示例值                                          |
| ------------------- | ----------------- | -------------------------------------------- |
| **SSO共享密钥**         | 用于JWT签名的密钥，两端必须一致 | `真实共享秘钥`                                     |
| **OntiCards API地址** | 我们的SSO登录接口地址      | `https://OntiCards【后端】真实ip:端口（或域名）`          |
| **回调跳转地址**          | 登录成功后跳转的前端页面      | `https://OntiCards【前端】真实ip:端口（或域名）/overview` |


### 2.2 整体流程

```
1. 客户后端生成 JWT Token
   ↓
2. 拼接 SSO 登录 URL（带上 token 和 redirect_url）
   ↓
3. 用户浏览器跳转到我们的 SSO 接口
   ↓
4. 我们验证 JWT、创建/关联用户、生成自己的 Token
   ↓
5. 浏览器跳转到 redirect_url，带上我们的 Token
   ↓
6. 客户前端接收 Token，登录完成
```

---

## 三、Token 生成详解（必须由客户后端完成）

### 3.1 第一部分：Header（头部）

固定格式，声明使用HS256算法：

```json
{
    "alg": "HS256",
    "typ": "JWT"
}
```

然后对这个JSON对象进行 **Base64URL编码**。

### 3.2 第二部分：Payload（负载/用户数据）

这是最重要的部分，包含要传递的用户信息：

```json
{
    "username": "zhang_san",
    "user_id": "SYS_USER_001",
    "nickname": "张三",
    "email": "zhangsan@example.com",
    "source": "your_app",
    "iat": 1713000000,
    "exp": 1713000600
}
```

**字段说明**：


| 字段         | 类型     | 必填  | 说明                           |
| ---------- | ------ | --- | ---------------------------- |
| `username` | string | ✅   | 用户的唯一标识，不能为空                 |
| `user_id`  | string | ✅   | 客户系统中的用户ID，不能为空              |
| `nickname` | string | ❌   | 用户昵称                         |
| `email`    | string | ❌   | 用户邮箱                         |
| `source`   | string | ❌   | 来源标识，用于区分不同系统，默认 `default`   |
| `iat`      | number | ❌   | Token签发时间（Unix时间戳）           |
| `exp`      | number | ✅   | Token过期时间（Unix时间戳），建议设置为5分钟后 |


然后对这个JSON对象进行 **Base64URL编码**。

### 3.3 第三部分：Signature（签名）

将第一部分和第二部分用点号连接，然后用共享密钥对这段字符串进行签名：

```
签名字符串 = Header_base64 + "." + Payload_base64
签名 = HMAC-SHA256(签名字符串, 共享密钥)
```

### 3.4 最终的JWT Token

```
JWT Token = Header_base64 + "." + Payload_base64 + "." + Signature_base64
```

---

## 四、各语言生成JWT示例

### 4.1 Python 示例

```python
import jwt
from datetime import datetime, timedelta, timezone

# 客户需要配置的共享密钥（需要提供给OntiCards）
SECRET_KEY = "your_shared_secret_key"

# Payload（用户数据）
payload = {
    "username": "zhang_san",
    "user_id": "SYS_USER_001",
    "nickname": "张三",
    "email": "zhangsan@example.com",
    "source": "your_app",
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(minutes=5)  # 5分钟后过期
}

# 生成 JWT Token
token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
# 输出类似：eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InpoYW5nX3NhbiJ9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

### 4.2 Java 示例

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
    "source", "your_app"
);

String token = Jwts.builder()
    .claims(payload)
    .issuedAt(new Date())
    .expiration(new Date(System.currentTimeMillis() + 5 * 60 * 1000)) // 5分钟后过期
    .signWith(Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8)))
    .compact();

System.out.println(token);
```

### 4.3 Node.js 示例

```javascript
const jwt = require('jsonwebtoken');

const secretKey = 'your_shared_secret_key';

const payload = {
    username: 'zhang_san',
    user_id: 'SYS_USER_001',
    nickname: '张三',
    email: 'zhangsan@example.com',
    source: 'your_app'
};

const token = jwt.sign(payload, secretKey, {
    algorithm: 'HS256',
    expiresIn: '5m'  // 5分钟后过期
});

console.log(token);
```

### 4.4 纯前端生成（仅供测试使用）

```javascript
// ⚠️ 仅用于测试，生产环境Token生成必须在后端完成！

async function generateJWT(payload, secret) {
    // Header
    const header = { "alg": "HS256", "typ": "JWT" };
    const headerB64 = btoa(JSON.stringify(header))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    
    // Payload
    const payloadB64 = btoa(JSON.stringify(payload))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    
    // Signature
    const signatureInput = headerB64 + '.' + payloadB64;
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
        'raw', encoder.encode(secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false, ['sign']
    );
    const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(signatureInput));
    const signatureB64 = btoa(String.fromCharCode(...new Uint8Array(signature)))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    
    return signatureInput + '.' + signatureB64;
}

// 使用示例
const payload = {
    username: 'test_user',
    user_id: 'TEST_001',
    nickname: '测试用户',
    exp: Math.floor(Date.now() / 1000) + 300  // 5分钟后过期
};
generateJWT(payload, 'your_secret_key').then(token => console.log(token));
```

---

## 五、拼接登录URL并跳转

### 5.1 构造URL

```
{OntiCards API地址}/sso/login?token={JWT Token}&redirect_url={回调地址}
```

**示例**：

```
https://api.onticards.com/sso/login?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...&redirect_url=https://your-app.com/dashboard
```

### 5.2 跳转方式

**方式1：直接跳转（推荐）**

```javascript
// 生成Token后跳转
const ssoUrl = `${API_BASE}/sso/login?token=${encodeURIComponent(token)}&redirect_url=${encodeURIComponent(FRONTEND_URL)}`;
window.location.href = ssoUrl;
```

**方式2：新窗口打开**

```javascript
window.open(`${API_BASE}/sso/login?token=${encodeURIComponent(token)}`, '_blank');
```

---

## 六、回调地址接收Token

登录成功后，浏览器会跳转到：

```
https://frontend.onticards.com/overview?access_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 6.1 前端接收Token的代码

```javascript
// 从URL获取 access_token 参数
function getAccessToken() {
    const params = new URLSearchParams(window.location.search);
    return params.get('access_token');
}

// 存储Token
const token = getAccessToken();
if (token) {
    localStorage.setItem('access_token', token);
    
    // 可选：解析Token获取用户信息（不推荐用于安全验证，仅用于显示）
    const parts = token.split('.');
    if (parts.length === 3) {
        const payload = JSON.parse(atob(parts[1]));
        console.log('登录用户:', payload.nickname || payload.username);
        console.log('用户角色:', payload.role);
    }
    
    // 清理URL中的token参数（防止token泄露）
    window.history.replaceState({}, document.title, window.location.pathname);
}
```

### 6.2 后续请求携带Token

```javascript
// 后续API请求时在Header中携带Token
fetch('/api/your-endpoint', {
    headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('access_token')
    }
});
```

---

## 七、用户创建/登录逻辑

当用户首次通过SSO访问时，OntiCards系统会：

1. **接收JWT Token** → 获取URL中的token参数
2. **解析Header** → 获取算法信息
3. **验证签名** → 用共享密钥验证token是否被篡改
4. **检查过期** → 验证exp是否有效
5. **提取Payload** → 获取username、user_id等用户信息
6. **查询用户** → 根据 `idp_user_id` + `idp_source` 查找已存在用户
7. **创建/关联** → 新用户自动创建，老用户关联登录
8. **生成Token** → 生成OntiCards自己的登录Token
9. **跳转回调** → 携带新Token跳转到 redirect_url

---

## 八、错误码说明


| HTTP状态码 | error字段           | 原因                         |
| ------- | ----------------- | -------------------------- |
| 400     | `缺少token参数`       | URL中没有传token               |
| 400     | `token中缺少必要的用户信息` | Payload中username或user_id为空 |
| 401     | `token已过期`        | Token的exp已过期               |
| 401     | `token无效`         | 签名验证失败（密钥不匹配或内容被篡改）        |


---

## 九、配置汇总

### 9.1 OntiCards提供


| 项目      | 值                                                      | 用途        |
| ------- | ------------------------------------------------------ | --------- |
| SSO登录接口 | `https://api.onticards.com{OntiCards API地址}/sso/login` | 客户跳转的地址   |
| SSO共享密钥 | **客户提供，我们存储**                                          | 用于验证JWT签名 |


### 9.2 客户提供


| 项目   | 示例值                                       | 说明            |
| ---- | ----------------------------------------- | ------------- |
| 共享密钥 | `K7x#9mP$2nL5@qR8`                        | 建议64位以上的随机字符串 |
| 回调地址 | `https://frontend.onticards.com/overview` | 登录成功后跳转的前端页面  |


### 9.3 环境变量配置

在OntiCards服务端配置：

```env
SSO_SECRET_KEY=客户提供的共享密钥
```

---

## 十、测试验证

### 10.1 使用测试页面

OntiCards提供了本地测试页面：

- **SSO测试中心**：`http://localhost:9000/static/sso_test.html`
- **回调测试页面**：`http://localhost:9000/static/sso_callback.html`

### 10.2 对接检查清单

- 生成JWT Token（验证三部分结构：Header.Payload.Signature）
- Payload中包含必填字段：username、user_id、exp
- Token使用HS256算法签名
- 拼接SSO登录URL
- 测试跳转流程
- 验证回调页面能接收access_token
- 确认Token有效期（建议5分钟）
- 生产环境使用强密钥，不要使用示例密钥

---

## 十一、联系方式

如有问题，请联系OntiCards技术支持。