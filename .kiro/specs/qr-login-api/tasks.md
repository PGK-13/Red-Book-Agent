# 实施计划：公开扫码登录 API

## 概述

为前端登录页（`QrLoginCard` 组件）新增两个无需认证的公开扫码登录 API 端点，与现有已认证扫码登录接口并存。实现包括：Schema 扩展、Service 层新增公开扫码函数和 JWT 签发、新建公开路由文件、路由注册顺序调整。

## 任务

- [x] 1. 扩展 Schema — 新增 UserInfo 和 PublicQrLoginStatusResponse
  - [x] 1.1 在 `backend/app/schemas/account.py` 中新增 `UserInfo` 模型
    - 包含 `nickname: str`、`avatar: str | None = None`、`xhs_user_id: str` 字段
    - _需求: 6.2, 2.3_
  - [x] 1.2 在 `backend/app/schemas/account.py` 中新增 `PublicQrLoginStatusResponse` 模型
    - 包含 `status: Literal["waiting", "success", "expired"]`、`token: str | None = None`、`user: UserInfo | None = None` 字段
    - _需求: 6.1, 2.1, 2.3, 2.4_
  - [x] 1.3 编写 Schema 属性测试
    - **属性 1: PublicQrLoginStatusResponse 状态字段约束**
    - **验证: 需求 6.1 — status 只能为 "waiting"、"success"、"expired" 之一**
    - **属性 2: success 状态必须携带 token 和 user**
    - **验证: 需求 2.3 — 当 status 为 success 时，token 和 user 不为 None**
    - **属性 3: waiting/expired 状态 token 和 user 为 null**
    - **验证: 需求 2.4 — 当 status 为 waiting 或 expired 时，token 和 user 为 None**

- [x] 2. Service 层 — 新增公开扫码登录函数和 JWT 签发
  - [x] 2.1 在 `backend/app/services/account_service.py` 中新增 `_create_jwt_token()` 私有函数
    - 参数：`xhs_user_id: str, nickname: str, avatar: str | None`
    - 使用 `app.config.settings` 读取 `jwt_secret_key`、`jwt_algorithm`、`jwt_expire_minutes`
    - JWT payload 包含 `sub`（xhs_user_id）、`nickname`、`avatar`、`exp` 字段
    - 使用 `python-jose` 的 `jwt.encode()` 签发
    - _需求: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.2 在 `backend/app/services/account_service.py` 中新增 `public_start_qr_login()` 异步函数
    - 无需 `merchant_id` 和 `account_id` 参数
    - 使用 Playwright 打开小红书登录页，截取二维码为 base64
    - 在 Redis 中创建会话，key 格式 `pub_qr_session:{session_id}`，TTL 300 秒，初始状态 `waiting`
    - Playwright 不可用时返回 HTTP 503
    - 返回 `{"session_id": str, "qr_image_base64": str}`
    - _需求: 1.1, 1.3, 1.4_
  - [x] 2.3 在 `backend/app/services/account_service.py` 中新增 `public_poll_qr_login_status()` 异步函数
    - 参数：`session_id: str`
    - 从 Redis 读取 `pub_qr_session:{session_id}`，key 不存在返回 `expired`
    - 状态为 `waiting` 时通过 Playwright 检测登录状态
    - 登录成功时提取用户信息，调用 `_create_jwt_token()` 签发 JWT
    - 返回 `{"status": str, "token": str | None, "user": dict | None}`
    - _需求: 2.1, 2.3, 2.4, 2.5, 3.1_
  - [ ]* 2.4 编写 `_create_jwt_token()` 属性测试
    - **属性 4: JWT 签发往返一致性**
    - **验证: 需求 3.1 — 签发的 JWT 解码后 sub、nickname、avatar 与输入一致**
    - **属性 5: JWT 过期时间正确性**
    - **验证: 需求 3.3 — JWT exp 字段等于签发时间 + JWT_EXPIRE_MINUTES**

- [ ] 3. 检查点 — 确保 Schema 和 Service 层代码无语法错误
  - 确保所有测试通过，如有疑问请向用户确认。

- [ ] 4. 路由层 — 新建公开扫码登录路由
  - [ ] 4.1 创建 `backend/app/api/v1/qr_login.py`，定义 `router = APIRouter(prefix="/accounts/qr-login", tags=["扫码登录（公开）"])`
    - 不引入任何认证依赖（不使用 `CurrentMerchantId`、`HTTPBearer`）
    - _需求: 5.1_
  - [ ] 4.2 实现 `POST /start` 端点
    - 调用 `account_service.public_start_qr_login()`
    - 返回 `BaseResponse[QrLoginStartResponse]`
    - _需求: 1.1, 1.2, 4.1, 4.2_
  - [ ] 4.3 实现 `GET /status` 端点
    - 接收 `session_id: str = Query(...)` 参数
    - 调用 `account_service.public_poll_qr_login_status(session_id)`
    - 返回 `BaseResponse[PublicQrLoginStatusResponse]`
    - _需求: 2.1, 2.2, 4.1, 4.3_
  - [ ]* 4.4 编写路由层单元测试
    - 使用 `httpx.AsyncClient` 测试两个端点
    - Mock `account_service` 的公开扫码函数
    - 验证无 `Authorization` header 时请求正常处理
    - 验证响应格式符合 `BaseResponse` 包装
    - _需求: 1.2, 2.2, 4.1, 4.2, 4.3_

- [ ] 5. 路由注册 — 修改 main.py 挂载公开路由
  - [ ] 5.1 在 `backend/app/main.py` 中导入 `qr_login` 模块
    - `from app.api.v1 import qr_login`
    - _需求: 5.3_
  - [ ] 5.2 在 `accounts.router` 之前注册 `qr_login.router`
    - `app.include_router(qr_login.router, prefix="/api/v1")` 必须在 `app.include_router(accounts.router, prefix="/api/v1")` 之前
    - 确保 `/api/v1/accounts/qr-login/start` 优先于 `/{account_id}/qr-login/start` 匹配
    - _需求: 5.3, 5.4_
  - [ ]* 5.3 编写路由注册顺序验证测试
    - **属性 6: 路由隔离 — 公开路由不要求认证**
    - **验证: 需求 5.1, 5.2 — 公开路由无需 JWT 即可访问，已认证路由仍需 JWT**

- [ ] 6. 最终检查点 — 确保所有测试通过
  - 确保所有测试通过，确保现有已认证扫码登录接口不受影响，如有疑问请向用户确认。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 现有的 `QrLoginStartResponse` 和 `QrLoginStatusResponse` 保持不变，不影响已认证接口（需求 6.3、5.2）
- 属性测试验证核心正确性属性，单元测试验证具体场景和边界条件
