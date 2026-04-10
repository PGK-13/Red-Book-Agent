# Implementation Plan: 模块 A — 账号集成与基础配置

## Overview

基于现有项目骨架（已有 stub 文件），按分层架构逐步实现账号管理全功能：ORM 模型 → Pydantic Schema → Service 层 → API 路由 → Celery 异步任务 → 属性测试。每一步都在前一步基础上构建，确保无孤立代码。

## Tasks

- [x] 1. 实现 SQLAlchemy ORM 模型（Account、AccountPersona、ProxyConfig）
  - [x] 1.1 在 `backend/app/models/account.py` 中实现 Account、AccountPersona、ProxyConfig 三个 ORM 模型
    - 替换现有 TODO stub
    - Account 表：id(UUID PK)、merchant_id(UUID, indexed)、xhs_user_id(VARCHAR 64)、nickname(VARCHAR 128)、access_type(Enum: oauth/rpa/browser)、oauth_token_enc(Text)、cookie_enc(Text)、cookie_expires_at(TIMESTAMPTZ)、status(Enum: active/suspended/auth_expired/banned, default=active)、last_probed_at(TIMESTAMPTZ)、created_at(TIMESTAMPTZ, server_default=now)
    - AccountPersona 表：id(UUID PK)、account_id(UUID FK → accounts.id, CASCADE, unique)、tone(VARCHAR 64)、system_prompt(Text)、bio(Text)、tags(ARRAY Text)、follower_count(Integer)、profile_synced_at(TIMESTAMPTZ)
    - ProxyConfig 表：id(UUID PK)、account_id(UUID FK → accounts.id, CASCADE, unique)、proxy_url(Text, 加密存储)、user_agent(Text)、screen_resolution(VARCHAR 16)、timezone(VARCHAR 64, default=Asia/Shanghai)、is_active(Boolean, default=True)
    - 定义 relationship：Account ↔ AccountPersona (one-to-one)、Account ↔ ProxyConfig (one-to-one)
    - 添加 UniqueConstraint("merchant_id", "xhs_user_id")
    - _Requirements: A1.1, A1.2, A1.6, A2.1, A2.3_
  - [x] 1.2 创建 Alembic 迁移脚本生成 accounts、account_personas、proxy_configs 三张表
    - 在 `backend/app/db/migrations/` 下生成迁移文件
    - 包含所有索引和约束（merchant_id 索引、status 索引、unique 约束）
    - _Requirements: A1.1, A1.2_

- [x] 2. 实现 Pydantic 请求/响应 Schema
  - [x] 2.1 创建 `backend/app/schemas/account.py`，定义所有账号相关 Schema
    - AccountCreateRequest：xhs_user_id(str, max_length=64)、nickname(str, max_length=128)、access_type(Literal["oauth","rpa","browser"])
    - OAuthCallbackRequest：code(str)
    - CookieUpdateRequest：raw_cookie(str)、expires_at(datetime)
    - PersonaUpdateRequest：tone(str|None)、system_prompt(str|None)、bio(str|None)、tags(list[str]|None)
    - ProxyUpdateRequest：proxy_url(str)、user_agent(str)、screen_resolution(str, pattern=^\d+x\d+$)、timezone(str, default=Asia/Shanghai)、is_active(bool, default=True)
    - AccountResponse：id、merchant_id、xhs_user_id、nickname、access_type、status、cookie_expires_at、last_probed_at、created_at、persona(PersonaResponse|None)、proxy(ProxyResponse|None)
    - PersonaResponse：tone、bio、tags、follower_count、profile_synced_at
    - ProxyResponse：user_agent、screen_resolution、timezone、is_active（不返回 proxy_url）
    - AccountStatusResponse：status、last_probed_at、cookie_expires_at、cookie_remaining_hours(float|None)
    - QrLoginStartResponse：session_id(str)、qr_image_base64(str)
    - QrLoginStatusResponse：status(Literal["waiting","success","expired"])
    - _Requirements: A1.1, A1.3, A1.6, A1.7, A1.8, A2.1, A2.3, A4.4_

- [x] 3. 实现 AccountService 核心业务逻辑
  - [x] 3.1 在 `backend/app/services/account_service.py` 中实现账号 CRUD 方法
    - 替换现有 TODO stub
    - `list_accounts(merchant_id, limit, cursor, db)` → 按 merchant_id 过滤，cursor 分页
    - `create_account(merchant_id, data, db)` → 创建账号，检查商家套餐账号数量上限
    - `get_account(merchant_id, account_id, db)` → 按 merchant_id + account_id 查询
    - `delete_account(merchant_id, account_id, db)` → 级联删除（persona、proxy_config）
    - 所有查询必须携带 merchant_id 过滤
    - _Requirements: A1.1, A1.2_
  - [x] 3.2 实现 OAuth 授权回调和 Cookie 管理方法
    - `handle_oauth_callback(merchant_id, account_id, code, db)` → 用 code 换取 access_token，调用 `core/security.encrypt()` 加密后存入 oauth_token_enc
    - `update_cookie(merchant_id, account_id, raw_cookie, expires_at, db)` → 调用 `encrypt()` 加密 raw_cookie 存入 cookie_enc，更新 cookie_expires_at，若账号状态为 auth_expired 则恢复为 active
    - 原始凭证仅在内存中短暂存在，不得写入日志
    - _Requirements: A1.3, A1.4, A1.5_
  - [x] 3.3 实现人设配置和代理配置方法
    - `update_persona(merchant_id, account_id, data, db)` → 创建或更新 AccountPersona 记录
    - `update_proxy(merchant_id, account_id, data, db)` → 调用 `encrypt()` 加密 proxy_url，创建或更新 ProxyConfig 记录
    - 代理配置更新时需校验设备指纹唯一性（user_agent + screen_resolution + timezone 组合不得与同商家其他账号重复）
    - _Requirements: A1.6, A2.1, A2.3_
  - [x] 3.4 实现账号状态探测方法
    - `probe_account_status(account_id, db)` → 检测 Cookie 过期时间和平台返回状态码
      - Cookie 距过期 < 24h → 调用 `notifications.send_alert()` 发送预警
      - Cookie 已过期 → 状态设为 auth_expired，暂停所有操作
      - 平台返回 403/封禁码 → 状态设为 banned，触发告警
      - 平台返回 429/限流码 → 状态设为 suspended，触发告警
    - `probe_all_accounts(db)` → 查询所有 active 账号，逐个调用 probe_account_status，更新 last_probed_at
    - 记录包含时间戳和错误码的异常日志
    - _Requirements: A4.1, A4.2, A4.3, A1.4, A1.5_
  - [x] 3.5 实现账号画像同步方法
    - `sync_profile(merchant_id, account_id, db)` → 通过 Playwright 浏览器上下文抓取小红书个人主页
    - 提取：昵称、简介、标签、粉丝数
    - 更新 account_personas 表对应字段和 profile_synced_at
    - _Requirements: A3.1, A3.2_
  - [x] 3.6 实现 Playwright 浏览器上下文管理方法
    - `get_browser_context(account_id, db)` → 根据 ProxyConfig 创建隔离的 Playwright BrowserContext
    - 配置 proxy（解密 proxy_url）、user_agent、viewport（解析 screen_resolution）、timezone_id
    - 注入解密后的 Cookie（解析 cookie_enc）
    - 未配置代理时记录警告日志（IP 混用风险）
    - 上下文按需创建，使用完毕后关闭
    - _Requirements: A2.1, A2.2, A2.3_
  - [x] 3.7 实现扫码登录方法
    - `start_qr_login(merchant_id, account_id, db)` → 通过 Playwright 打开小红书登录页，截取二维码图片
      - 使用账号已配置的代理 IP 创建浏览器上下文
      - 截取二维码区域为 base64 图片
      - 在 Redis 中创建扫码会话（session_id → {context_ref, status: waiting, created_at}，TTL=5min）
      - 返回 session_id 和 qr_image_base64
    - `poll_qr_login_status(merchant_id, account_id, session_id, db)` → 轮询扫码登录状态
      - 从 Redis 读取 session 状态
      - 检测 Playwright 页面是否已跳转（登录成功标志：URL 变化或特定元素出现）
      - 登录成功 → 提取所有 Cookie，调用 encrypt() 加密存入 cookie_enc，计算 cookie_expires_at，关闭浏览器上下文
      - 超时（> 5min）→ 关闭浏览器上下文，返回 expired 状态
    - _Requirements: A1.7, A1.8_

- [x] 4. Checkpoint — 确保 Service 层逻辑完整
  - 确保所有 Service 方法类型注解完整，async/await 正确使用
  - 确保所有查询携带 merchant_id 过滤
  - 确保所有敏感字段通过 core/security.encrypt() 加密
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. 实现 API 路由层
  - [x] 5.1 在 `backend/app/api/v1/accounts.py` 中实现所有账号管理路由
    - 替换现有 TODO stub
    - GET `/accounts` → 调用 AccountService.list_accounts，返回 PaginatedResponse[AccountResponse]
    - POST `/accounts` → 调用 AccountService.create_account，返回 BaseResponse[AccountResponse]
    - GET `/accounts/{id}` → 调用 AccountService.get_account，返回 BaseResponse[AccountResponse]
    - DELETE `/accounts/{id}` → 调用 AccountService.delete_account，返回 BaseResponse
    - POST `/accounts/{id}/oauth/callback` → 调用 AccountService.handle_oauth_callback
    - PUT `/accounts/{id}/cookie` → 调用 AccountService.update_cookie
    - GET `/accounts/{id}/status` → 调用 AccountService.get_account_status，返回 BaseResponse[AccountStatusResponse]
    - POST `/accounts/{id}/sync-profile` → 调用 AccountService.sync_profile
    - PUT `/accounts/{id}/persona` → 调用 AccountService.update_persona
    - PUT `/accounts/{id}/proxy` → 调用 AccountService.update_proxy
    - POST `/accounts/{id}/qr-login/start` → 调用 AccountService.start_qr_login，返回 BaseResponse[QrLoginStartResponse]
    - GET `/accounts/{id}/qr-login/status` → 调用 AccountService.poll_qr_login_status，返回 BaseResponse[QrLoginStatusResponse]
    - 所有路由注入 CurrentMerchantId 和 DbSession 依赖
    - 路由层只做参数校验和响应封装，不写业务逻辑
    - _Requirements: A1.1, A1.2, A1.3, A1.4, A1.5, A1.6, A1.7, A1.8, A2.1, A2.3, A3.1, A4.4_

- [ ] 6. 实现 Celery 异步任务
  - [ ] 6.1 实现 `worker/tasks/account_probe_task.py` 账号状态探测任务
    - 替换现有 NotImplementedError stub
    - 创建数据库会话，调用 AccountService.probe_all_accounts()
    - 配置 max_retries=3、retry_backoff=True
    - 每 10 分钟由 Celery Beat 触发（beat_schedule.py 已配置）
    - _Requirements: A4.1, A4.2, A4.3_
  - [ ] 6.2 实现 `worker/tasks/profile_sync_task.py` 账号画像同步任务
    - 替换现有 NotImplementedError stub
    - 查询所有 active 账号，逐个调用 AccountService.sync_profile()
    - 配置 max_retries=3、retry_backoff=True
    - 每 24 小时凌晨 3 点由 Celery Beat 触发（beat_schedule.py 已配置）
    - _Requirements: A3.1, A3.2_

- [ ] 7. Checkpoint — 确保端到端流程可用
  - 确保 API 路由 → Service 层 → ORM 模型完整串联
  - 确保 Celery 任务 → Service 层调用正确
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. 编写属性测试和单元测试
  - [ ]* 8.1 编写属性测试：OAuth 令牌加密存储
    - **Property 1: OAuth token encrypted storage**
    - **Validates: Requirements A1.3**
    - 使用 Hypothesis 生成随机 token 字符串，验证 encrypt(token) != token 且 decrypt(encrypt(token)) == token
    - 在 `backend/tests/test_account_properties.py` 中实现
  - [ ]* 8.2 编写属性测试：Cookie 过期预警触发
    - **Property 2: Cookie expiry warning trigger**
    - **Validates: Requirements A1.4**
    - 使用 Hypothesis `st.datetimes()` 生成随机过期时间，验证：距过期 < 24h 时触发通知，≥ 24h 时不触发
    - 在 `backend/tests/test_account_properties.py` 中实现
  - [ ]* 8.3 编写属性测试：Cookie 过期后状态转换
    - **Property 3: Cookie expired → auth_expired status transition**
    - **Validates: Requirements A1.5**
    - 使用 Hypothesis 生成已过期的 Cookie 时间戳，验证账号状态变为 auth_expired 且自动化操作被阻止
    - 在 `backend/tests/test_account_properties.py` 中实现
  - [ ]* 8.4 编写属性测试：代理 IP 绑定一致性
    - **Property 4: Proxy IP binding consistency**
    - **Validates: Requirements A2.1**
    - 使用 Hypothesis 生成随机代理配置，验证 get_browser_context 创建的上下文使用了正确的代理 IP
    - 在 `backend/tests/test_account_properties.py` 中实现
  - [ ]* 8.5 编写属性测试：设备指纹唯一性
    - **Property 5: Device fingerprint uniqueness across accounts**
    - **Validates: Requirements A2.3**
    - 使用 Hypothesis 生成多组设备指纹参数（user_agent + screen_resolution + timezone），验证同商家下不同账号的指纹组合不重复
    - 在 `backend/tests/test_account_properties.py` 中实现
  - [ ]* 8.6 编写 AccountService 单元测试
    - 测试 CRUD 操作的正常路径和错误路径
    - 测试 merchant_id 隔离（跨商家不可访问）
    - 测试状态机转换（active → auth_expired → active、active → banned）
    - 测试代理未配置时的警告逻辑
    - 在 `backend/tests/test_account_service.py` 中实现
    - _Requirements: A1.1, A1.2, A1.5, A2.2, A4.2_
  - [ ]* 8.7 编写 API 路由层单元测试
    - 测试各端点的请求参数校验（无效 access_type、缺失字段等）
    - 测试响应格式符合 BaseResponse / PaginatedResponse 规范
    - 在 `backend/tests/test_account_api.py` 中实现
    - _Requirements: A1.1, A4.4_

- [ ] 9. Final checkpoint — 确保所有测试通过
  - 确保所有属性测试（Hypothesis）通过，每个属性至少 100 次迭代
  - 确保所有单元测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- 所有代码使用 Python 3.11+，async/await，类型注解完整
- 敏感字段加密使用已有的 `backend/app/core/security.py`（encrypt/decrypt）
- 通知推送使用已有的 `backend/app/core/notifications.py`（send_alert）
- Celery Beat 调度已在 `worker/beat_schedule.py` 中配置完成
