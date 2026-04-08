---
inclusion: fileMatch
fileMatchPattern: "**/core/security*,**/auth*,**/dependencies*,**/*token*,**/*encrypt*,**/*secret*"
---

# 安全规范

## 敏感数据处理

- OAuth Token、Cookie、代理 URL 必须加密后存储，使用 `core/security.py` 提供的加解密工具
- 禁止在日志、响应体、错误信息中输出任何 token、密钥、cookie 原文
- 数据库字段命名以 `_enc` 结尾表示加密存储（如 `oauth_token_enc`、`cookie_enc`）

```python
# Good
from app.core.security import encrypt, decrypt

account.oauth_token_enc = encrypt(raw_token)

# Bad
account.oauth_token = raw_token
```

## 环境变量

- 所有密钥、连接串、第三方 API Key 必须通过环境变量注入，禁止硬编码
- 本地开发使用 `.env`（已加入 `.gitignore`），参考 `infra/.env.example`
- 禁止将 `.env` 文件提交至代码仓库

```python
# Good
from app.config import settings
llm_api_key = settings.OPENAI_API_KEY

# Bad
llm_api_key = "sk-xxxxxxxxxxxxxxxx"
```

## CI 敏感信息检测

PR 触发时 CI 会自动扫描以下模式，命中则阻断合并：

- `github_pat_` / `ghp_` — GitHub Token
- `sk-` — OpenAI API Key
- `password = "..."` — 硬编码密码

## 认证与授权

- 所有 `/api/v1/` 接口必须经过 JWT 认证，在 `dependencies.py` 的 `get_current_merchant` 中统一校验
- 商家数据严格按 `merchant_id` 隔离，Service 层查询必须带 `merchant_id` 过滤条件
- Webhook 入口（`/api/v1/interaction/webhook/message`）使用 HMAC 签名验证来源合法性

## 依赖安全

- 定期运行 `pip audit` / `npm audit` 检查已知漏洞
- 生产依赖版本锁定（`requirements.txt` 固定版本号，`package-lock.json` 提交至仓库）
