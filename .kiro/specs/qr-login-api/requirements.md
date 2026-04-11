# 需求文档 — 公开扫码登录 API

## 简介

当前后端的扫码登录接口挂在 `/{account_id}/qr-login/` 路径下，依赖 JWT 认证（`CurrentMerchantId`），用于已登录商家为账号绑定小红书。前端登录页（`QrLoginCard` 组件）需要一组无需认证的公开 API，用于商家首次扫码登录平台。登录成功后由后端签发 JWT，前端存入 `localStorage` 完成认证闭环。

本需求新增两个公开路由，与现有的已认证扫码登录接口并存，互不影响。

## 术语表

- **Public_QrLogin_Router**：新增的公开扫码登录路由模块，挂载在 `/api/v1/accounts/qr-login` 路径下，不依赖任何认证中间件
- **QrLogin_Service**：扫码登录业务逻辑层，负责二维码生成、会话管理、状态轮询、JWT 签发
- **JWT**：JSON Web Token，用于前端认证，payload 包含 `sub`（xhs_user_id）、`nickname`、`avatar`、`exp` 字段
- **Session**：扫码会话，存储在 Redis 中，包含 session_id、状态（waiting/success/expired）、创建时间，TTL 为 5 分钟
- **BaseResponse**：统一响应格式 `{ code: 0, message: "success", data: T | null }`，定义在 `backend/app/schemas/base.py`
- **api-client**：前端统一 HTTP 请求封装模块（`frontend/lib/api-client.ts`），自动注入 JWT、处理 401 拦截

## 需求

### 需求 1：启动扫码登录（公开接口）

**用户故事：** 作为一个未登录的商家，我希望在登录页发起扫码登录请求，以获取小红书二维码图片进行扫码。

#### 验收标准

1. WHEN 前端发送 `POST /api/v1/accounts/qr-login/start` 请求（请求体为空 JSON `{}`），THE Public_QrLogin_Router SHALL 返回 `BaseResponse[QrLoginStartResponse]`，其中 `data` 包含非空的 `session_id`（UUID 格式字符串）和非空的 `qr_image_base64`（base64 编码的 PNG 图片）
2. THE Public_QrLogin_Router SHALL 在不依赖任何认证头（无 `Authorization` header）的情况下正常处理请求
3. WHEN 启动扫码登录成功，THE QrLogin_Service SHALL 在 Redis 中创建一条扫码会话记录，key 格式为 `pub_qr_session:{session_id}`，TTL 为 300 秒（5 分钟），初始状态为 `waiting`
4. IF Playwright 未安装或小红书登录页无法访问，THEN THE QrLogin_Service SHALL 返回 HTTP 503 错误，message 包含可读的错误描述

### 需求 2：轮询扫码登录状态（公开接口）

**用户故事：** 作为一个正在扫码的商家，我希望前端能每 3 秒轮询扫码状态，以便在扫码成功后自动获取 JWT 并跳转到主页。

#### 验收标准

1. WHEN 前端发送 `GET /api/v1/accounts/qr-login/status?session_id=xxx` 请求，THE Public_QrLogin_Router SHALL 返回 `BaseResponse[PublicQrLoginStatusResponse]`，其中 `data.status` 为 `"waiting"` | `"success"` | `"expired"` 之一
2. THE Public_QrLogin_Router SHALL 在不依赖任何认证头的情况下正常处理请求
3. WHEN `data.status` 为 `"success"`，THE PublicQrLoginStatusResponse SHALL 额外包含 `token` 字段（JWT 字符串）和 `user` 字段（包含 `nickname`、`avatar`、`xhs_user_id`）
4. WHEN `data.status` 为 `"waiting"` 或 `"expired"`，THE PublicQrLoginStatusResponse SHALL 将 `token` 和 `user` 字段设为 `null`
5. IF `session_id` 参数缺失或对应的 Redis 会话已过期（key 不存在），THEN THE Public_QrLogin_Router SHALL 返回 `data.status` 为 `"expired"`

### 需求 3：JWT 签发

**用户故事：** 作为一个扫码成功的商家，我希望后端签发一个包含用户信息的 JWT，以便前端存储后用于后续 API 认证。

#### 验收标准

1. WHEN 扫码登录成功（小红书登录页检测到用户已登录），THE QrLogin_Service SHALL 签发一个 JWT，payload 包含以下字段：`sub`（值为 xhs_user_id）、`nickname`、`avatar`（从小红书页面提取，提取失败时为 `null`）、`exp`（过期时间）
2. THE QrLogin_Service SHALL 使用环境变量 `JWT_SECRET_KEY` 作为签名密钥，`JWT_ALGORITHM`（默认 `HS256`）作为签名算法
3. THE QrLogin_Service SHALL 将 JWT 过期时间设为当前时间加上 `JWT_EXPIRE_MINUTES`（默认 1440 分钟，即 24 小时）
4. THE QrLogin_Service SHALL 通过 `app.config.settings` 读取 JWT 配置，禁止硬编码密钥或算法

### 需求 4：响应格式兼容

**用户故事：** 作为前端开发者，我希望公开扫码登录 API 的响应格式与现有 `api-client` 和 `QrLoginCard` 组件的期望完全一致，以实现零改动对接。

#### 验收标准

1. THE Public_QrLogin_Router SHALL 使用 `BaseResponse` 包装所有响应，确保顶层结构为 `{ code: 0, message: "success", data: {...} }`
2. THE `POST /api/v1/accounts/qr-login/start` 响应的 `data` 字段 SHALL 包含 `session_id`（string）和 `qr_image_base64`（string），与前端 `QrStartResponse` 类型匹配
3. THE `GET /api/v1/accounts/qr-login/status` 响应的 `data` 字段 SHALL 包含 `status`（string）、`token`（string | null）、`user`（`{ nickname: string, avatar: string | null, xhs_user_id: string }` | null），与前端 `QrPollResponse` 类型匹配

### 需求 5：路由隔离与安全

**用户故事：** 作为平台运维人员，我希望公开扫码登录接口与现有已认证接口互不干扰，且公开接口具备基本的安全防护。

#### 验收标准

1. THE Public_QrLogin_Router SHALL 注册为独立的 `APIRouter`，路径前缀为 `/accounts/qr-login`，不使用 `CurrentMerchantId` 依赖
2. THE 现有的 `accounts.router` 下的 `/{account_id}/qr-login/start` 和 `/{account_id}/qr-login/status` 路由 SHALL 保持不变，继续要求 JWT 认证
3. WHEN 在 `app/main.py` 中注册路由时，THE Public_QrLogin_Router SHALL 挂载在 `/api/v1` 前缀下，最终路径为 `/api/v1/accounts/qr-login/start` 和 `/api/v1/accounts/qr-login/status`
4. THE Public_QrLogin_Router SHALL 在 `main.py` 中的注册顺序位于 `accounts.router` 之前，确保 FastAPI 路由匹配优先级正确（公开路由优先于带 `{account_id}` 路径参数的路由）

### 需求 6：Schema 扩展

**用户故事：** 作为后端开发者，我希望新增的响应 Schema 与现有 Schema 体系一致，便于维护。

#### 验收标准

1. THE 新增的 `PublicQrLoginStatusResponse` Schema SHALL 定义在 `backend/app/schemas/account.py` 中，包含 `status`（Literal["waiting", "success", "expired"]）、`token`（str | None）、`user`（UserInfo | None）字段
2. THE 新增的 `UserInfo` Schema SHALL 定义在 `backend/app/schemas/account.py` 中，包含 `nickname`（str）、`avatar`（str | None）、`xhs_user_id`（str）字段
3. THE 现有的 `QrLoginStartResponse` 和 `QrLoginStatusResponse` SHALL 保持不变，不影响已认证接口的行为
