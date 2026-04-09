# 需求 A1：账号接入管理技术方案分析

## 1. 文档目标

本文档基于当前项目源码现状，针对模块 A 的 **需求 A1：账号接入管理** 提供可落地的技术方案分析，用于指导后续数据库设计、后端实现、异步任务接入、前端管理页设计以及后续 A2/A3/A4 需求的平滑扩展。

本文重点回答以下问题：

- 当前仓库现状下，A1 应该落在哪些模块和边界上
- 三种账号接入方式如何在同一套账号域模型内统一管理
- 如何满足 OAuth 加密存储、Cookie 预警、授权失效停机、人设注入等验收标准
- 存在哪些可选方案，各自适用场景、优缺点与风险是什么
- 结合当前项目成熟度，推荐优先采用哪种方案

---

## 2. 需求范围与验收点拆解

需求 A1 的验收标准可以拆分为 6 个子能力：

1. 支持三种账号接入方式：
   - 小红书官方开放平台 API
   - 第三方 RPA 工具
   - 浏览器自动化脚本
2. 支持商家在同一后台管理多个账号，且账号数量受套餐限制
3. 官方 API 接入时使用 OAuth 2.0，并对访问令牌加密存储
4. Cookie 距离过期不足 24 小时时发送刷新提醒
5. Cookie 已过期且未刷新时，暂停该账号全部自动化操作，并标记为 `auth_expired`
6. 每个账号可配置独立语气人设，并作为 LLM System Prompt 的一部分注入内容生成流程

从实现角度看，A1 不只是“新增账号表”或“做几个接口”，而是一个横跨以下层次的账号域能力：

- 数据层：账号、授权凭证、人设、代理配置、套餐上限
- 服务层：账号创建、授权回调、凭证更新、状态迁移、账号可操作性检查
- Worker 层：Cookie 过期检查、账号状态探测、画像同步触发
- Agent / Prompt 层：账号人设注入内容生成链路
- 前端层：多账号统一管理后台

---

## 3. 基于当前源码的项目现状分析

### 3.1 已经具备的基础能力

当前仓库已经为 A1 预留了较明确的骨架，说明账号域是系统核心模块之一：

- `backend/app/core/security.py`
  - 已提供 `encrypt()` / `decrypt()`，适合用于 OAuth Token、Cookie、代理地址等敏感字段加密存储
- `backend/app/dependencies.py`
  - 已提供 `CurrentMerchantId`，说明系统已经按 `merchant_id` 做商家数据隔离
- `worker/beat_schedule.py`
  - 已存在账号状态探测任务和账号画像同步任务的调度入口
- `worker/tasks/account_probe_task.py`
  - 已明确预留 Cookie 预警、过期状态切换、封禁检测的任务入口
- `worker/tasks/profile_sync_task.py`
  - 已明确预留账号画像同步逻辑
- `agent/prompts/content_generation.py`
  - 已存在 `{persona}` 注入位点，适合直接接入账号人设能力
- `.kiro/specs/architecture.md`
  - 已定义 `accounts`、`account_personas`、`proxy_configs` 等表结构草案
- `.kiro/steering/architecture-layers.md`
  - 已明确规定业务逻辑集中在 Service 层，Task 只作为异步入口，路由层只做参数校验和响应封装

### 3.2 当前缺失的关键实现

虽然架构预留较完整，但 A1 的实际代码实现仍处于空壳阶段：

- `backend/app/models/account.py`
  - 尚未实现 `Account`、`AccountPersona`、`ProxyConfig` ORM
- `backend/app/services/account_service.py`
  - 尚未实现 OAuth、Cookie 管理、账号状态监控、人设管理等业务逻辑
- `backend/app/api/v1/accounts.py`
  - 尚未实现账号管理 API
- `frontend/app/accounts/page.tsx`
  - 账号管理页仍是占位页面
- 数据库迁移目录中尚无具体 migration 文件
- 项目中尚未看到套餐/订阅模块，账号数量上限缺少可直接复用的数据来源

### 3.3 对方案选择的影响

这意味着 A1 的实现必须满足两个现实条件：

- 不能设计成过度依赖现有复杂基础设施，因为当前账号域核心代码还没有真正落地
- 又不能只做最简陋的单表 CRUD，因为 A1 后面会直接影响 A2 代理隔离、A3 账号画像同步、A4 状态监控

因此，A1 最适合采用：

- 以统一账号域模型为核心
- 用轻量策略模式抽象三种接入方式
- 用中央“账号可操作性闸门”控制所有自动化行为

---

## 4. 设计目标

结合当前仓库现状，A1 的技术方案需要满足以下目标：

- 与当前 FastAPI + Service + Celery + Agent 分层架构一致
- 对三种接入方式统一建模，但允许后续差异化扩展
- 对敏感信息实现统一加密存储与脱敏访问
- 将“账号状态”作为自动化行为的统一控制点
- 能够直接支撑后续 A2 代理与环境隔离、A3 账号画像同步、A4 账号状态监控
- 能先实现 MVP，再平滑演进，而不是一次性做过重架构

---

## 5. 可选技术方案

## 方案一：统一账号表 + Service 内部分支判断

### 方案描述

使用一个 `accounts` 表统一存储账号基础信息和授权信息，通过 `access_type` 字段区分三种接入方式。`account_service.py` 中通过 `if/elif` 判断不同接入类型，分别走 OAuth、RPA、Browser 的处理逻辑。

### 核心实现方式

- `accounts` 表中统一存储：
  - `merchant_id`
  - `nickname`
  - `xhs_user_id`
  - `access_type`
  - `oauth_token_enc`
  - `cookie_enc`
  - `cookie_expires_at`
  - `status`
- `account_personas` 表单独维护每个账号的人设配置
- `proxy_configs` 表单独维护代理与浏览器指纹
- 在 `AccountService` 中直接写：
  - `create_account()`
  - `handle_oauth_callback()`
  - `update_cookie()`
  - `probe_account_status()`
  - `update_persona()`

### 优点

- 实现成本最低
- 最接近当前架构文档草案
- 对当前代码骨架最友好，能快速做出第一版
- 适合项目早期快速验证业务闭环

### 不足

- 三种接入方式的逻辑都会堆到 `account_service.py`
- 随着 A2/A3/A4 增长，Service 会迅速膨胀
- 第三方 RPA 和浏览器自动化的差异处理会越来越难维护
- 后续接入更多平台或更多账号能力时扩展性较差

### 适用场景

- 需要极快交付 MVP
- 账号能力近期不会继续扩展
- 可接受后续较快重构

### 风险与应对

- 风险：业务逻辑越来越多，形成巨型 Service
- 应对：即使采用本方案，也要把不同接入方式逻辑拆分为私有方法或子模块，避免所有逻辑都堆在一个文件中

---

## 方案二：统一账号域模型 + Connector 策略模式

### 方案描述

保留统一账号表，但在 Service 层引入轻量 Connector 抽象，为三种接入方式分别实现独立适配器：

- `OAuthConnector`
- `RpaConnector`
- `BrowserConnector`

由 `AccountService` 负责统一编排，按 `access_type` 将授权、状态探测、画像同步等动作分发给对应 Connector。与此同时，引入统一的账号执行闸门 `ensure_account_operable()`，所有自动化任务在执行前都先通过该检查。

### 核心实现方式

#### 1. 统一领域模型

- `accounts`
  - 账号基础信息
  - 接入方式
  - 当前授权状态
  - 核心敏感凭证引用
- `account_personas`
  - tone、system_prompt、bio、tags 等
- `proxy_configs`
  - proxy、user_agent、screen_resolution、timezone 等

#### 2. Connector 抽象接口

建议定义最小接口集合：

- `build_authorize_url()`
- `handle_callback()`
- `probe_status()`
- `sync_profile()`
- `get_runtime_credentials()`

不同接入方式只实现自己需要的方法：

- `OAuthConnector`
  - 负责 OAuth 授权链接生成、code 换 token、授权撤销检测
- `RpaConnector`
  - 负责对接第三方 RPA 平台凭证、任务可用性检查
- `BrowserConnector`
  - 负责 Playwright Cookie 驱动登录、浏览器侧状态探测、画像抓取

#### 3. 中央执行闸门

为所有自动化操作增加统一前置检查：

- 账号是否存在
- 是否属于当前商家
- 是否超过套餐账号上限
- 是否为 `active`
- Cookie 是否过期
- OAuth 是否已撤销
- 是否缺少必要代理配置

只有通过该闸门的账号，才能继续执行：

- 发布任务
- 评论回复
- 私信发送
- 画像同步
- 数据回抓

### 优点

- 保持统一账号管理视图，符合产品体验
- 三种接入方式的差异被隔离在 Connector 内，扩展性明显优于方案一
- 不需要拆服务，仍与当前单体项目结构兼容
- 对 A2/A3/A4 的延展性最好
- 能显著减少后续维护成本

### 不足

- 首版设计和编码成本高于方案一
- 如果抽象过度，容易在项目早期增加额外复杂度
- 需要团队在 Service 层和 Connector 边界上保持纪律

### 适用场景

- 当前项目即将继续实现 A2/A3/A4
- 需要兼顾首版可落地与中期可维护性
- 希望后续接入更多自动化能力而不重构主干

### 风险与应对

- 风险：为了“通用”而设计过多接口，导致首版过重
- 应对：只定义最小必需接口，不做复杂插件系统，不引入额外框架，使用简单注册表即可

---

## 方案三：账号接入网关 / 事件驱动拆分方案

### 方案描述

将账号接入从当前后端中进一步拆分，形成独立的接入网关或异步接入服务。主业务服务只管理账号元数据、状态和任务下发，OAuth、RPA、浏览器自动化分别作为独立执行单元或子服务运行。

### 核心实现方式

- 主业务服务存账号元数据和账号状态
- 每种接入方式单独作为一个执行模块
- 通过 Celery / MQ / 事件总线下发动作
- 回调结果异步更新账号状态

### 优点

- 隔离性最好
- 更适合高规模、多平台、多厂商接入
- 监控、审计、限流、熔断更容易做

### 不足

- 对当前项目成熟度来说过重
- 会显著增加开发和运维成本
- 一致性与排障复杂度明显上升
- 当前代码基础还不足以支撑这一层级的拆分

### 适用场景

- 平台已经进入多团队协作阶段
- 账号量、任务量、平台接入数量快速增长
- 已有完善的订阅、事件、监控系统

### 风险与应对

- 风险：过早拆分导致交付周期拉长、系统复杂度先于业务增长
- 应对：当前阶段不直接采用，仅保留未来升级空间

---

## 6. 方案对比

| 对比维度 | 方案一：Service 分支 | 方案二：Connector 策略 | 方案三：接入网关拆分 |
|------|------|------|------|
| 首版开发速度 | 高 | 中 | 低 |
| 与当前代码适配度 | 高 | 高 | 低 |
| 中期可维护性 | 低 | 高 | 高 |
| 扩展三种接入差异 | 一般 | 好 | 很好 |
| 对 A2/A3/A4 支撑 | 一般 | 很好 | 很好 |
| 架构复杂度 | 低 | 中 | 高 |
| 运维复杂度 | 低 | 低 | 高 |
| 推荐程度 | 一般 | 最高 | 当前不推荐 |

---

## 7. 推荐方案

推荐采用 **方案二：统一账号域模型 + Connector 策略模式**。

### 推荐原因

1. 最符合当前项目现状

当前仓库已经有明确的账号域边界、Worker 调度入口、加密工具和 Prompt 注入位点，但还没有成型的账号业务代码。方案二可以在不破坏现有结构的前提下，把账号服务主干一次性搭对。

2. 能兼顾首版可交付与后续扩展

相比方案一，方案二不会把三种接入方式全部塞进 `account_service.py`，能为 A2、A3、A4 提前留出扩展空间；相比方案三，又不会给当前项目引入过重的架构成本。

3. 最利于“统一管理多个账号”

产品层面需要的是一个统一后台，而不是三套分裂的账号管理逻辑。方案二在后台界面、数据模型和状态管理上天然统一，但又能在执行层面保留差异。

4. 能自然形成“账号状态控制中心”

Cookie 过期预警、授权失效停机、账号异常探测，其本质都依赖统一账号状态流转。方案二有利于构建中央状态机和统一执行闸门。

---

## 8. 推荐方案的详细设计

## 8.1 数据模型设计

### accounts

建议在架构文档基础上扩展为以下最小可用字段：

- `id`
- `merchant_id`
- `xhs_user_id`
- `nickname`
- `access_type`
- `status`
- `status_reason`
- `oauth_token_enc`
- `oauth_refresh_token_enc`
- `oauth_expires_at`
- `cookie_enc`
- `cookie_expires_at`
- `last_cookie_reminded_at`
- `rpa_provider`
- `rpa_config_enc`
- `last_probed_at`
- `created_at`
- `updated_at`

说明：

- `status` 建议取值：
  - `active`
  - `suspended`
  - `auth_expired`
  - `banned`
- `status_reason` 用于记录当前冻结原因，便于前端展示
- `last_cookie_reminded_at` 用于防止重复提醒
- `rpa_config_enc` 用于存储第三方 RPA 平台敏感凭证或任务配置

### account_personas

建议字段：

- `id`
- `account_id`
- `tone`
- `style_keywords`
- `forbidden_phrases`
- `system_prompt`
- `bio`
- `tags`
- `follower_count`
- `profile_synced_at`

说明：

- `tone` 用于前端配置和快速筛选
- `system_prompt` 存最终编译后的 Prompt 文本，供内容生成链路直接使用
- `bio/tags/follower_count` 用于结合账号画像增强人设

### proxy_configs

沿用架构草案即可：

- `account_id`
- `proxy_url_enc`
- `user_agent`
- `screen_resolution`
- `timezone`
- `is_active`

### 套餐限制表

当前仓库尚未看到完整套餐模型，因此建议新增轻量配置来源：

- `merchant_settings`
  - `merchant_id`
  - `max_accounts`

或：

- `merchant_plan_snapshots`
  - `merchant_id`
  - `plan_code`
  - `max_accounts`

优先建议使用最简 `merchant_settings`，避免在 A1 阶段等待完整订阅系统落地。

---

## 8.2 后端服务层设计

建议将 `backend/app/services/account_service.py` 作为账号域编排中心，负责：

- 创建账号
- 校验套餐账号上限
- 处理 OAuth 授权回调
- 更新 Cookie
- 更新账号人设
- 获取账号状态
- 触发账号画像同步
- 执行账号状态探测
- 提供统一的账号可操作性检查

建议核心函数：

- `create_account(merchant_id, payload)`
- `list_accounts(merchant_id)`
- `get_account_detail(merchant_id, account_id)`
- `delete_account(merchant_id, account_id)`
- `handle_oauth_callback(merchant_id, account_id, code, state)`
- `update_cookie(merchant_id, account_id, cookie, expires_at)`
- `update_persona(merchant_id, account_id, payload)`
- `update_proxy(merchant_id, account_id, payload)`
- `sync_profile(merchant_id, account_id)`
- `probe_account(account_id)`
- `ensure_account_operable(account_id, operation)`

其中 `ensure_account_operable()` 是推荐方案中的关键函数，所有自动化动作都应该复用它，而不是在不同任务里各写一套状态判断。

---

## 8.3 Connector 设计

建议在账号服务内部新增轻量适配层，例如：

- `backend/app/services/account_connectors/base.py`
- `backend/app/services/account_connectors/oauth_connector.py`
- `backend/app/services/account_connectors/rpa_connector.py`
- `backend/app/services/account_connectors/browser_connector.py`

基础接口建议如下：

```python
class BaseAccountConnector(ABC):
    async def build_authorize_url(self, account): ...
    async def handle_callback(self, account, payload): ...
    async def probe_status(self, account): ...
    async def sync_profile(self, account): ...
    async def get_runtime_credentials(self, account): ...
```

说明：

- OAuth 型账号可重点实现 `build_authorize_url()`、`handle_callback()`、`probe_status()`
- Browser 型账号可重点实现 `probe_status()`、`sync_profile()`、`get_runtime_credentials()`
- RPA 型账号可重点实现平台侧授权、任务可用性检查、状态同步

为了控制复杂度，首版不建议做动态插件发现机制，直接在 `AccountService` 内维护一个简单映射：

```python
CONNECTOR_REGISTRY = {
    "oauth": OAuthConnector(),
    "rpa": RpaConnector(),
    "browser": BrowserConnector(),
}
```

---

## 8.4 OAuth 2.0 实现建议

### 建议流程

1. 商家创建 `access_type=oauth` 的账号接入记录
2. 后端生成授权链接与 `state`
3. 前端跳转到小红书开放平台授权页
4. 小红书回调 `code + state`
5. 后端验证 `state`
6. Connector 使用 `code` 换取 `access_token`
7. 使用 `security.encrypt()` 加密后写入 `oauth_token_enc`
8. 状态更新为 `active`

### 安全要求

- 不记录 token 明文日志
- 不将 token 返回给前端
- `state` 必须防重放、防伪造
- token、refresh token 统一使用 `_enc` 字段落库
- 若未来支持刷新 token，也同样采用加密字段

### 当前仓库风险点

`backend/app/config.py` 中 `encryption_key` 目前是开发占位值，A1 真正联调前必须切换为合法 Fernet Key，并在应用启动时做校验，否则加密能力无法可靠投入生产。

---

## 8.5 Cookie 过期提醒与授权失效停机

### 推荐实现方式

复用现有 Celery Beat 中的 `account-probe` 定时任务，每 10 分钟扫描一次全部账号。

状态探测逻辑建议顺序如下：

1. 查询所有启用账号
2. 判断是否存在 `cookie_expires_at`
3. 若剩余时间 `< 24h` 且未提醒过，则发送刷新提醒
4. 若 Cookie 已过期，则将账号状态更新为 `auth_expired`
5. 对 `auth_expired` 账号触发告警并阻断自动化操作
6. 对外部平台返回的封禁/撤销码更新为 `banned` 或相应状态

### 为什么不能只做定时任务改状态

如果只是把状态改成 `auth_expired`，但发布任务、评论回复、私信发送等执行链路没有前置校验，那么已入队的旧任务仍可能继续执行。因此必须配合中央闸门：

- `publish_task`
- `comment_reply`
- `dm_sender`
- 后续所有账号自动化操作

都必须在真正执行前调用 `ensure_account_operable()`

### 重复提醒问题

如果不做去重，10 分钟任务会在 24 小时窗口内持续发送提醒，造成消息轰炸。推荐做法：

- 在 `accounts.last_cookie_reminded_at` 记录上次提醒时间
- 或在 `alerts` 表中用 `(account_id, alert_type, date_bucket)` 做唯一约束

首版更推荐前者，简单直接。

---

## 8.6 多账号统一管理与套餐上限

### 推荐实现方式

所有账号列表、详情、更新、删除都以 `merchant_id` 为主过滤条件，确保商家隔离。

创建账号前：

1. 查询当前商家已有账号数
2. 查询套餐上限 `max_accounts`
3. 若已达到上限，拒绝创建并返回业务错误码

### 关键点

- 套餐校验必须在 Service 层完成
- 不能仅依赖前端按钮置灰
- 若未来支持升级套餐，只需更新 `merchant_settings.max_accounts` 即可

---

## 8.7 人设注入内容生成流程

当前 `agent/prompts/content_generation.py` 已包含：

- `账号人设：{persona}`

这说明 A1 与 C1 已经天然衔接。

### 推荐做法

在账号人设层同时维护两类信息：

- 结构化配置
  - `tone`
  - `style_keywords`
  - `forbidden_phrases`
- 编译后的 `system_prompt`

内容生成时：

1. 根据 `account_id` 查询 `account_personas`
2. 优先读取 `system_prompt`
3. 若 `system_prompt` 为空，则由结构化字段拼装默认 Prompt
4. 将结果注入内容生成 Prompt 的 `{persona}`

### 这样设计的好处

- 前端可做结构化配置表单
- 后端可审计最终注入给 LLM 的内容
- 后续支持“预览 Prompt”“版本回滚”“人设模板复用”会更容易

---

## 8.8 API 设计建议

建议沿用架构文档中的账号管理 API，并按当前实现阶段分两批落地。

### 第一批：A1 核心闭环

- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `GET /api/v1/accounts/{id}`
- `DELETE /api/v1/accounts/{id}`
- `POST /api/v1/accounts/{id}/oauth/callback`
- `PUT /api/v1/accounts/{id}/cookie`
- `GET /api/v1/accounts/{id}/status`
- `PUT /api/v1/accounts/{id}/persona`

### 第二批：为 A2/A3 铺路

- `PUT /api/v1/accounts/{id}/proxy`
- `POST /api/v1/accounts/{id}/sync-profile`

### 路由层职责要求

必须遵守当前分层规范：

- 路由层只做参数校验和响应封装
- 业务逻辑全部放在 `AccountService`
- Task 只负责异步入口，不直接写核心业务逻辑

---

## 9. 推荐实施顺序

为降低返工，建议按以下顺序推进：

### 第一阶段：数据层打底

- 实现 `Account`、`AccountPersona`、`ProxyConfig` ORM
- 增加最小套餐配置表
- 编写 Alembic migration

### 第二阶段：账号服务主干

- 实现 `AccountService`
- 落地账号创建、列表、详情、删除
- 落地套餐上限校验
- 落地账号状态与中央执行闸门

### 第三阶段：授权与 Cookie 管理

- 实现 OAuth callback 处理
- 加密存储 token / cookie
- 实现更新 Cookie 接口

### 第四阶段：异步任务接入

- 实现 `account_probe_task`
- 落地 Cookie 预警、过期停机、异常告警
- 实现 `profile_sync_task` 的基础入口

### 第五阶段：人设与内容链路打通

- 实现账号人设配置 API
- 将 `account_personas.system_prompt` 注入内容生成链路

### 第六阶段：前端账号管理页

- 账号列表
- 账号状态展示
- OAuth 接入入口
- Cookie 更新入口
- 人设配置入口

---

## 10. 主要不足与应对策略

### 不足一：当前项目缺少完整套餐模块

影响：

- A1 中“账号数量受套餐限制”缺少现成数据源

应对：

- 先实现轻量 `merchant_settings.max_accounts`
- 后续订阅系统落地后再迁移到正式套餐表

### 不足二：敏感配置尚未达到生产就绪

影响：

- `encryption_key` 当前还是占位值
- 若直接上线，无法满足真正的密钥安全要求

应对：

- 启动时校验 `encryption_key`
- 生产环境从安全配置中心或环境变量注入
- 增加密钥轮换预案

### 不足三：Worker 已预留但业务尚未复用 Service

影响：

- 如果在 Task 内直接写业务，容易违反当前架构规范

应对：

- 所有 Task 只调用 `AccountService` 公共函数
- 状态探测、画像同步都复用统一账号域逻辑

### 不足四：浏览器自动化和 RPA 差异较大

影响：

- 不同接入方式的状态探测能力、可支持操作、返回错误码可能不一致

应对：

- 在 Connector 层统一返回标准化结果
- 例如统一返回：
  - `status`
  - `reason`
  - `recoverable`
  - `raw_error_code`

### 不足五：仅改账号状态不足以阻止已入队任务

影响：

- 可能出现账号已经失效，但旧任务还在继续执行

应对：

- 所有执行类任务在最终动作前都调用 `ensure_account_operable()`
- 将“状态更新”和“执行阻断”设计为两层保障，而不是只依赖一种

---

## 11. 测试建议

A1 至少需要覆盖以下测试：

- 单元测试：OAuth Token 加密存储，数据库中的值不得等于明文
- 单元测试：Cookie 剩余时间 `< 24h` 时触发提醒，`>= 24h` 不提醒
- 单元测试：Cookie 过期后账号状态变为 `auth_expired`
- 单元测试：`auth_expired` 账号被 `ensure_account_operable()` 拦截
- 单元测试：套餐上限达到后不能再创建账号
- 单元测试：账号人设能正确编译并注入 Prompt
- 集成测试：账号创建 -> OAuth 回调 -> 状态激活
- 集成测试：账号过期 -> Worker 扫描 -> 告警发送 -> 自动化任务被阻断

---

## 12. 最终结论

基于当前源码实际情况，A1 最不适合做成“简单 CRUD + 零散状态判断”，也不适合直接上“独立接入网关拆分”。最合适的落地路线是：

- 采用统一账号域模型
- 在 Service 层引入轻量 Connector 策略模式
- 用中央账号可操作性闸门统一拦截所有自动化动作
- 以加密存储、状态流转、任务阻断、人设注入作为 A1 的真正核心闭环

该方案能够在当前项目成熟度下实现最好的平衡：

- 首版可落地
- 与现有架构一致
- 能自然支撑后续 A2/A3/A4
- 后续维护成本可控

因此，建议将 **方案二** 作为 A1 的正式技术方案基线。
