# 需求 A1：账号接入管理技术方案分析与落地设计

## 1. 文档目标

本文档基于当前项目源码现状，针对模块 A 的 **需求 A1：账号接入管理** 提供可落地的技术方案与详细设计，用于指导后续数据库设计、后端实现、异步任务接入、前端管理页设计以及后续核心业务流程的平滑扩展。

本文重点说明：
- 当前仓库现状下，A1 的模块与边界划分。
- 三种账号接入方式（平台 API、RPA、浏览器自动化）如何在同一套账号域模型内统一管理。
- **贴合当前项目成熟度的落地机制**：OAuth 加密存储、Cookie 更新协同、以数据库为真源的中央拦截闸门、状态机流转、以及分阶段通知策略。
- 结合当前项目成熟度，本系统采用的 **统一账号域模型 + Connector 策略模式** 架构。

---

## 2. 需求范围与验收点拆解

需求 A1 的验收标准拆分为以下核心能力：

1. **多端接入能力**：支持小红书官方开放平台 API（专业号）、第三方 RPA 工具和浏览器自动化脚本。
2. **多账号与配额管理**：支持商家在同一后台管理多个账号，且账号数量受商家套餐限制。
3. **安全与合规**：官方 API 接入使用 OAuth 2.0，所有访问令牌及敏感凭证需执行加密存储。
4. **生命周期监控机制**：Cookie 距离过期不足 24 小时发送刷新提醒通知。
5. **失效保护机制**：Cookie 已过期且未刷新时，暂停该账号全部自动化操作（防脏任务执行），并标记为 `auth_expired`。
6. **AI 人设赋能**：每个账号可配置独立语气人设，并编译作为 LLM System Prompt 注入内容生成流程。

---

## 3. 架构方案选择：统一账号域模型 + Connector 策略模式

基于项目现状（已有 FastAPI + Service 分层，但账号域业务处于空壳状态），系统采用 **统一账号域模型 + Connector 策略模式** 方案：

*   **数据层统一**：以统一的 `accounts` 表作为核心，掩盖底层接入的差异性。
*   **服务层编排**：由 `AccountService` 负责统筹账户增删改查、状态探测与同步流转。
*   **执行层解耦**：引入轻量 `Connector` 抽象（如 `OAuthConnector`, `BrowserConnector`, `RpaConnector`），由它们负责处理各自协议的登录、凭证探测差异。
*   **防腐层设计**：通过统一的执行闸门 `ensure_account_operable()` 拦截所有违规状态的自动化调用。

---

## 4. 详细落地设计方案

### 4.1 数据模型设计 (Database Schema)

**1. `accounts` (核心账号表)**
- `id`, `merchant_id`, `xhs_user_id`, `nickname`
- `access_type`: 接入类型 (`oauth`, `rpa`, `browser`)
- `status`: 当前账号状态（严格受状态机控制）
- `status_reason`: 当前状态具体原因 / 风控提示信息
- `oauth_token_enc`, `oauth_refresh_token_enc`, `oauth_expires_at`: API 授权凭证
- `cookie_enc`, `cookie_expires_at`
- `last_cookie_reminded_at`: 防重复通知锁
- `rpa_provider`, `rpa_config_enc`: 第三方 RPA 平台敏感配置
- `last_probed_at`, `created_at`, `updated_at`

**2. `account_personas` (账号人设表 - 对齐 A1-Req-6)**
- 结构化字段：`tone` (语气), `style_keywords`, `forbidden_phrases`, `bio`
- 编译字段：`system_prompt` (最终编译后的 Prompt 文本，供内容生成链路直接消费，剥离动态拼接开销)

**3. `merchant_settings` (轻量套餐配额设置)**
- 为了在独立订阅系统上线前支持多账号上限功能，引入此表管理 `max_accounts`。

### 4.2 严格的状态机控制 (State Machine)

账号的状态流转不能是随意的 CRUD，必须收敛于 `AccountService` 中的状态机白名单，避免发生“封号账号被一个更新 Cookie 接口重新拉起”的严重业务 Bug。

**状态枚举与允许的迁移路径：**
- **`active`**：活跃正常。-> 允许转移至：`auth_expired`, `suspended`, `banned`
- **`auth_expired`**：授权自然过期。-> ONLY 允许转移至：`active` (需提供有效 Cookie/Token)
- **`suspended`**：被平台挂起（如欠费、配额超限）。-> ONLY 允许转移至：`active` (需系统后台人工或支付回调触发)
- **`banned`**：彻底被官方封禁（终态）。-> ONLY 允许转移至：无（只能由高权限系统管理员手动撤销）。

补充说明：

- 当前项目的既有架构文档只定义了 `active/suspended/auth_expired/banned` 四种状态，因此首版严格以这四种状态为准，避免与全局模型脱节。
- 若后续需要表达“验证码拦截”“人工介入”等更细粒度的中间态，首版建议通过 `status_reason` 承载，而不是直接扩充状态枚举。

### 4.3 “中央执行闸门”的实现与性能加速

为了确保**旧任务、重试任务**在账号过期或封禁时被有效阻断（满足 A1-Req-5），所有业务级自动化任务执行前均需调用闸门。

首版实现中，**数据库应为账号状态的唯一真源**。Redis 可以作为后续优化手段，但不能成为状态判定的唯一依据，否则会引入缓存一致性风险。

推荐首版实现：

- `ensure_account_operable()` 直接读取 DB 中的账号状态与必要凭证字段
- 所有执行类任务在最终动作前调用该函数
- Redis 仅用于后续性能优化或短期缓存，不参与首版正确性兜底

后续若账号量和任务量增长明显，可在保持 DB 真源前提下增加 Redis 只读缓存：

```python
# 伪代码：DB 为真源，Redis 为可选加速层
async def ensure_account_operable(account_id: str) -> bool:
    # 1. 首版直接查 DB
    account = await repo.get_account(account_id)
    if account.status != "active":
        raise AccountNotOperableException(account.status_reason)

    # 2. 按 access_type 检查必需凭证是否有效
    # 例如 oauth 看 token/browser 看 cookie/rpa 看 provider 配置

    # 3. 可选：将只读结果回写 Redis 做短期缓存
    return True
```

补充说明：

- 如果未来接入 Redis 缓存，必须坚持“DB 真源、Redis 可失效”的原则。
- 任何涉及到 Cookie 更新、Token 更新、状态变更的业务接口，都必须同步清理或重写缓存。

### 4.4 非 API 模式的凭证采集及上下游协同 (对抗风控)

鉴于小红书风控机制，非 API 模式下需要明确 Cookie 与运行态凭证的协同来源。但这部分在首版不应被强行收敛为“必须有浏览器插件”，而应设计成分层支持。

建议拆为两层：

- **首版必做能力**
  - 系统提供 `PUT /api/v1/accounts/{id}/cookie` 接口，允许商家或受控工具安全上报最新 Cookie 与过期时间
  - Browser / RPA Connector 均复用这套凭证更新入口
- **后续增强能力**
  - 浏览器插件（Chrome Extension / Tampermonkey 脚本）作为可选增强方案，用于提升 Cookie 更新体验
  - RPA 本地沙盒程序作为独立执行体，遇到风控滑块或人工介入事件时回调后端网关

这样处理的原因：

- A1 原始需求只要求支持浏览器自动化脚本接入，并未要求必须交付插件产品
- 若把插件写成默认前提，会额外引入插件开发、发版、安装指引、权限审计等新增范围
- 首版先保证“后端能安全接收和管理 Cookie”，比“必须先做插件”更贴合当前项目成熟度

### 4.5 触达与通知机制 (Notification Channel)

对于 A1 中要求的 “不足 24 小时发送提醒” 问题，需要明确落地通知管道，不能只有定时计算而无实体触达：

1. **Celery 定时巡检 (`account_probe_task`)**: 每 10 分钟扫描一次 DB。
2. **防重防打扰**: 取出 `last_cookie_reminded_at`，如果距当前时间少于特定间隔（如 12 小时），则略过不发送。
3. **首版触达管道**:
   - 复用现有告警思路，先落 `alerts` 或等价通知流水表
   - 前端通过轮询展示账号告警与到期提醒
4. **后续增强触达**:
   - 如果后续项目补齐 WebSocket 基建，再增加在线实时 Push

这样设计的原因：

- 当前仓库只有 `send_alert()` 的占位实现，尚无成熟通知中心或 WebSocket 能力
- 若将站内信 + WebSocket 都作为 A1 首版前提，会让账号模块反向依赖通知子系统
- 首版先做到“可记录、可查询、可展示”即可满足业务闭环

### 4.6 安全与凭证加密细节

- **`encryption_key`**: 不能硬编码，生产环境必须通过容器环境变量或等价安全注入方式提供。系统 `startup` 钩子中需实现对其合法性的检查。
- 所有凭证字段入库强制调用框架内置的 `security.encrypt()` 闭包，读出给底层的 Connector 使用前调用 `security.decrypt()`。**绝对禁止返回给前端侧（哪怕被混淆过）**。

补充说明：

- 当前项目尚未引入云厂商 KMS 基础设施，因此文档首版不将 `AWS KMS` 作为强依赖前提
- 首版更贴合当前仓库的做法是：环境变量注入 + 启动时合法性校验 + 日志严格脱敏

### 4.7 接入方式、凭证与阻断规则矩阵

为了避免 `accounts` 表同时承载 OAuth、Cookie、RPA 配置后造成执行歧义，必须明确不同接入类型的最小依赖凭证与阻断规则。

| access_type | 最小必需凭证 | 常见执行能力 | 失效判定 | 是否触发全停 |
|------|------|------|------|------|
| `oauth` | `oauth_token_enc` | 官方 API 能覆盖的账号管理/数据同步类能力 | token 失效、授权撤销、refresh 失败 | 是 |
| `browser` | `cookie_enc` | 基于浏览器自动化的发布、互动、页面抓取 | Cookie 过期、人工登录失效、浏览器环境异常 | 是 |
| `rpa` | `rpa_provider` + `rpa_config_enc`，必要时附加 `cookie_enc` | 第三方 RPA 支持的自动化动作 | RPA 连接失效、凭证失效、平台返回异常 | 是 |

设计原则：

- `oauth` 账号不应因为缺少 Cookie 而被误判为不可操作，除非某个具体动作明确依赖 Cookie
- `browser` 账号不应强制要求 OAuth token
- `rpa` 账号是否依赖 Cookie 由对应 Connector 决定，但必须在 Connector 中明确返回标准化错误
- `ensure_account_operable()` 必须按 `access_type` 做差异化判定，而不是对所有账号一刀切检查全部凭证

---

## 5. API 编排与职责规范

遵循项目架构层级，API 层面不做任何业务校验（只做 Body 参数和鉴权），交由 `AccountService` 处理。

**提供给前端的 API (第一阶段)：**
- `POST /api/v1/accounts` (创建空位 / 配置)
- `GET /api/v1/accounts` (列表 / 强制按照 merchant_id 隔离)
- `GET /api/v1/accounts/{id}/status` 
- `PUT /api/v1/accounts/{id}/cookie` (插件端上报凭证入口)
- `PUT /api/v1/accounts/{id}/persona` 
- `POST /api/v1/accounts/{id}/oauth/callback` (OAuth 回调处理)

说明：

- 若采用“预创建账号 + state 绑定 account_id”的流程，则上述 callback 设计可保留
- 若后续发现 OAuth 提供方更适合“回调后再绑定账号”，则可将 callback 改为独立入口，由 `state` 反查账号记录

**提供给自动化执行层 (Worker/Agent) 的内部接口：**
- `AccountService.ensure_account_operable()` 

---

## 6. 实施顺序建议

为最大程度降低后续返工率，整体实施步调排期建议如下：

1. **Phase 1: DB 核心基建**
   实施 `accounts`、`account_personas` 与 `merchant_settings` 的 ORM 模型建立；配置 Fernet 密钥合法性校验；先以 DB 作为状态真源。
2. **Phase 2: 状态机与闸门系统开发**
   在 `AccountService` 下完成账号状态机转移逻辑，完善拦截函数 `ensure_account_operable`。
3. **Phase 3: Client 上报 API & Connector 开发**
   搭建 Cookie 更新专用接口；配置 OAuth 协议回调链路；实现三种 Connector 的最小可用版本。
4. **Phase 4: Worker 保护与通知**
   配置 10 分钟周期的 Celery Beat Scan 任务；对接并完善告警/通知表结构记录。
5. **Phase 5: Agent 人设注水**
   联动当前既有的 Prompt 生成器，实现 `system_prompt` 读取与注入。
6. **Phase 6: 管理端前端界面联调**
   最后通过 API 提供给运营控制面板展现。
7. **Phase 7: Redis / 插件 / WebSocket 增强**
   当 DB 真源方案稳定后，再按实际压力决定是否引入 Redis 状态缓存、浏览器插件协同和 WebSocket 实时推送。

--- 

## 7. 测试验收关键要点

开发就绪后，必须重点保障以下 Test Cases：

- **(安全项)** DB 内容查看测试：`oauth_token_enc` 及 `cookie_enc` 的落库存储值不得等于原始明文，且系统可正常解密恢复。
- **(边界项)** Cookie 时长边界：修改模拟时钟至 `Now + 23h 59m`，断言提醒触发；`Now + 24h 01m`，断言不提醒。
- **(状态机项)** 非法跨越：模拟发出将 `banned` 或 `auth_expired` 在不上传新凭证的情况下请求变为 `active`，断言请求被拦截抛出 400 Bad Request。
- **(风控项)** 旧任务拦截测试：将一个处于模拟队列里的任务下发前更改账户状态为 `suspended`，断言下发时触发 `ensure_account_operable` 失败。
- **(矩阵项)** 不同 `access_type` 的凭证判定测试：`oauth` 不应被缺失 Cookie 误伤，`browser` 不应被缺失 token 误伤。
