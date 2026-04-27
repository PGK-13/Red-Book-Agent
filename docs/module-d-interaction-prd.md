# 模块 D：互动与意图路由 — 产品需求文档

## 1. 文档目标

本文档定义模块 D（互动与意图路由）的功能范围、数据模型、API 接口设计、交互流程及验收标准，用于指导后端实现、前端联调与质量验收。

---

## 2. 模块概述

### 2.1 核心价值

解决"怎么回"的问题 — 作为 Agent 的核心大脑，负责监听用户互动（评论/私信）、精细化理解用户意图，并触发相应的自动化回复流程，同时在高风险场景下主动通知商家并支持人工接管。

### 2.2 技术选型说明

> 由于小红书开放平台 API 需要企业资质，本模块所有与小红书平台的交互均采用 **Playwright RPA（浏览器自动化）** 实现，不依赖官方 API 接口。浏览器以 `headless=True`（无头模式）运行，24/7 无人值守。

### 2.3 用户故事

- **评论实时监测**：商家希望系统持续监控笔记评论区的新增评论，第一时间触发自动回复
- **图片评论 OCR**：评论含图片时，系统自动识别图片文字再进行意图分类
- **意图精细分类**：系统能区分问价、投诉、求链接、购买意向等不同意图，执行差异化策略
- **防重复打扰**：对同一用户 24 小时内相同意图的评论仅触发一次自动私信
- **自动化私信导流**：根据评论意图自动向用户发送包含价格/链接/购买引导的私信
- **实时客服**：通过商家端消息页面实时接收并回复用户私信，维持多轮上下文
- **人工接管**：在高风险（强愤怒）或高价值（商务合作）场景下自动通知商家并暂停自动回复
- **HITL 审核**：低置信度或特定意图的条目进入人工审核队列，商家确认后执行

---

## 3. 功能模块详细说明

### 3.1 D1 — 评论实时监测

#### 功能描述

系统通过 Playwright RPA 轮询商家指定笔记的评论区，检测新增评论（增量检测），并触发意图分类和自动回复流程。

#### 技术实现

- **轮询机制**：Celery Beat 每 10 秒触发 `comment-probe` 任务，通过令牌桶 + 随机抖动控制实际执行频率
- **增量检测**：点击"按时间排序" → 解析评论时间戳 → 过滤 `parsed_at > last_checked_at` → 遇到旧评论立即 break → Redis ID 集合幂等兜底
- **防检测策略**：每批次笔记处理前随机等待 5~25 秒；每篇笔记处理间隔 3~15 秒；Browser Context 按账号复用确保设备指纹一致

#### 业务流程

```
Celery Beat (每 10s)
  → NotePollingScheduler.acquire_token()
      → [随机等待 5~25s]
      → Playwright RPA.poll_note_comments()
          → 打开笔记评论页
          → 点击"按时间排序"
          → 解析时间戳，增量过滤
          → Redis ID 集合幂等
          → 返回新评论列表
      → [每篇间隔 3~15s]
  → 新评论写入 comments 表
      → 含图片 → OCR 识别文字
      → 调用 IntentRouterGraph 分类
      → 按意图分支执行（私信/评论回复/HITL）
```

#### 状态说明

| reply_status | 说明 |
|------|------|
| `pending` | 待处理 |
| `replied` | 已回复 |
| `manual_review` | 进入 HITL 人工审核 |
| `skipped` | 跳过（去重/非目标意图）|

#### 验收标准

1. 新评论检测延迟不超过 60 秒
2. 含图片评论通过 OCR 提取文字，置信度 < 0.5 时标记为无法识别并进入 HITL
3. 同一用户 24 小时内相同意图评论仅触发一次自动私信
4. 令牌桶调度确保操作频率符合防检测要求

---

### 3.2 D2 — 多层级意图识别

#### 功能描述

通过 LangGraph + GPT-4o Function Calling 对评论和私信进行意图分类和情绪分析，输出结构化结果供下游分支判断使用。

#### 意图分类

**评论场景（6 类）：**

| 意图 | 说明 |
|------|------|
| `ask_price` | 问价 |
| `complaint` | 吐槽/投诉 |
| `ask_link` | 求链接 |
| `general_inquiry` | 一般咨询 |
| `competitor_mention` | 竞品提及 |
| `other` | 其他 |

**私信场景（7 类）：**

| 意图 | 说明 |
|------|------|
| `ask_price` | 问价 |
| `ask_link` | 求链接 |
| `purchase_intent` | 购买意向 |
| `complaint` | 吐槽/投诉 |
| `high_value_bd` | 高价值商务合作 |
| `general_inquiry` | 一般咨询 |
| `other` | 其他 |

#### 情绪分析

输出情绪分数：`-1.0`（极度负面）到 `+1.0`（极度正面）

#### 置信度阈值

- `confidence >= 0.7` → 正常分支
- `confidence < 0.7` → `needs_human_review = True`，进入 HITL 队列

#### 特定意图强制 HITL

| 条件 | trigger_reason |
|------|---------------|
| `intent = complaint` | `complaint` |
| `intent = competitor_mention`（评论）| `competitor_mention` |
| `intent = high_value_bd`（私信）| `high_value_bd` |
| `sentiment_score < -0.8` | `strong_negative` |
| `confidence < 0.7` | `low_confidence` |

#### 验收标准

1. 评论意图分类在 10 秒内返回
2. 私信意图分类在 15 秒内返回
3. 同时输出情绪分数（-1.0 ~ +1.0）
4. 置信度低于 0.7 时自动进入 HITL 审核队列

---

### 3.3 D3 — 自动化私信触发

#### 功能描述

根据评论意图自动触发私信发送，通过 Playwright RPA 模拟人工操作在商家端发送私信，实现问价导流、链接推送、购买转化等业务目标。

#### 私信内容生成

| 意图 | 私信内容策略 |
|------|------------|
| `ask_price` | 从 RAG 检索产品价格区间，生成含价格引导的话术 |
| `ask_link` | 从 RAG 检索商品链接/店铺入口 |
| `purchase_intent` | 发送支付链接或客服联系方式 |

#### 业务流程

```
评论意图分类完成
  → check_dm_deduplication(xhs_user_id, intent)
      → 24h 内存在相同意图记录 → 跳过
      → 不存在 → 继续
  → 获取/创建 Conversation
  → RAG.hybrid_search(intent, content)
  → 组装 Prompt + 生成私信内容
  → RiskService.scan_output(content)
      → 扫描通过 → 继续
      → rewrite_required → 重试 ≤ 3 次
  → Playwright RPA.send_dm(xhs_user_id, content)
  → 记录 messages 表
```

#### 频率限制

- 私信发送：≤ 50 次/小时/账号
- 由模块 E（风控）`check_and_reserve_quota()` 强制执行

#### 验收标准

1. `ask_price` 意图 → 发送含价格区间的私信
2. `ask_link` 意图 → 发送含商品链接/店铺入口的私信
3. `complaint` 意图 → 不触发私信，进入 HITL 待处理队列
4. `competitor_mention` → 阻止自动回复，进入 HITL 并标记原因为竞品相关
5. `purchase_intent` → 发送含支付链接/客服联系方式的转化话术
6. 发送前必须通过风控扫描（模块 E）
7. 每次私信交互记录意图分类、回复内容和用户响应状态

---

### 3.4 D4 — 人工接管触发

#### 功能描述

在高风险（强愤怒情绪）或高价值（商务合作）场景下，系统自动暂停自动回复，通知商家并切换为人工接管模式。

#### 触发条件

| 条件 | 触发操作 |
|------|---------|
| `sentiment_score < -0.8` | 立即通知 + 切换人工接管 |
| `intent = high_value_bd`（私信）| 立即通知 + 切换人工接管 |
| `intent = complaint` | 进入 HITL 待处理队列（不强通知） |

#### 通知机制

- **App 推送**：通过 App 渠道发送实时通知
- **短信**：发送短信双渠道强提醒

#### 业务流程

```
IntentRouter 分类完成
  → 判断触发条件
  → Conversation.mode = 'human_takeover'
  → 发送 App + 短信双渠道通知
  → HITLQueue.enqueue(trigger_reason=xxx)
  → 商家处理后调用 /release 解除接管
  → Conversation.mode = 'auto'
```

#### 验收标准

1. 情绪分数 < -0.8 时立即发送 App + 短信双渠道强提醒
2. `high_value_bd` 私信意图立即触发人工接管通知
3. 人工接管期间暂停该会话所有自动回复
4. 商家可通过 `/release` 手动解除接管状态

---

### 3.5 D5 — 实时客服回复

#### 功能描述

通过 Playwright RPA 轮询商家端消息页面，实时接收用户私信并生成回复，维持多轮对话上下文，在线时段外自动回复"稍后为您解答"。

#### 业务流程

```
Celery Beat (每 5s)
  → poll_dm_messages()
      → Playwright RPA 打开商家端消息页面
      → 获取消息列表，新增写入 messages 表
      → 防重检查（xhs_msg_id UNIQUE）

  新消息
  → 查询 conversations.mode
      → human_takeover → enqueue_hitl() → 跳过
      → auto → 继续

  → 检查在线时段
      → 时段外 → 发送"稍后为您解答，稍后人工处理" → enqueue_hitl()
      → 时段内 → 继续

  → IntentRouter.classify_dm_intent()
      → needs_human_review → switch_to_human_takeover() + 通知
      → 正常分支

  → get_recent_messages(limit=10) 加载上下文
  → RAG.hybrid_search(intent, content)
  → CustomerServiceGraph.generate_reply()
  → RiskService.scan_output()
  → Playwright RPA.send_dm(reply_content)
  → append_message() 更新上下文
  → 更新 conversations.last_message_at
```

#### 上下文窗口

- 保留最近 **10 轮**消息记录
- 超出 10 轮时自动删除最早的记录
- 新消息到达后立即更新上下文

#### 连接中断处理

- Redis `session:pending:{conversation_id}` 队列暂存待发送消息
- `dm-pending` 任务（每 10s）检测连接恢复
- 连接恢复后 30 秒内补发，不在回复中体现延迟感知

#### 验收标准

1. 消息到达后响应延迟不超过 5 秒（目标值）
2. 意图分类在 3 秒内返回
3. 融合 RAG 知识库检索和最近 10 轮上下文生成回复
4. 连接中断时消息暂存待队列，恢复后 30 秒内补发
5. 在线时段外自动回复"稍后为您解答"并进入待处理队列
6. 置信度 < 0.7 或特定意图触发人工接管流程

---

## 4. 数据模型

### 4.1 ER 图

```
MonitoredNote (监测笔记配置)
     │
     └─── Comment ──→ IntentLog
              │
              └─── HITLQueue
                       │
                       └─── Conversation ──→ Message
                                                   │
                                              DMTriggerLog
```

### 4.2 表结构

#### `monitored_notes` — 监测笔记配置

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| account_id | UUID | 所属账号 FK |
| xhs_note_id | VARCHAR(64) | 笔记 ID |
| note_title | VARCHAR(256) | 笔记标题（缓存） |
| is_active | BOOLEAN | 是否启用监测（默认 true）|
| check_interval_seconds | INTEGER | 检查间隔（秒，默认 60）|
| batch_size | INTEGER | 每批最多处理笔记数（默认 3）|
| last_checked_at | TIMESTAMPTZ | 最近检查时间 |
| last_known_comment_count | INTEGER | 最近已知评论数（增量检测）|
| last_seen_comment_id | VARCHAR(64) | 最近已处理评论 ID（游标）|
| created_at | TIMESTAMPTZ | 创建时间 |

**索引：** `INDEX(account_id, is_active, last_checked_at ASC)`

---

#### `comments` — 评论记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| account_id | UUID | 被评论的账号 FK |
| xhs_note_id | VARCHAR(64) | 所属笔记 ID |
| xhs_comment_id | VARCHAR(64) UNIQUE | 小红书平台评论 ID（防重）|
| xhs_user_id | VARCHAR(64) | 评论用户 ID |
| content | TEXT | 评论文本内容 |
| image_urls | TEXT[] | 评论图片 URL 数组 |
| ocr_result | TEXT | OCR 提取文字（图片评论时）|
| intent | VARCHAR(32) | 意图分类结果 |
| intent_confidence | FLOAT | 意图置信度 |
| sentiment_score | FLOAT | 情绪分数（-1.0 ~ 1.0）|
| reply_status | ENUM | pending/replied/manual_review/skipped |
| deduplicated | BOOLEAN | 是否已去重 |
| detected_at | TIMESTAMPTZ | 检测到评论的时间 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引：**
- `INDEX(merchant_id, reply_status, created_at DESC)`
- `INDEX(account_id, xhs_note_id, created_at DESC)`

---

#### `conversations` — 私信会话

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| account_id | UUID | 商家账号 FK |
| xhs_user_id | VARCHAR(64) | 对话用户 ID |
| mode | ENUM | auto/human_takeover/pending |
| user_long_term_memory | JSONB | 用户长期记忆（偏好标签）|
| online_hours_start | TIME | 在线时段开始（nullable）|
| online_hours_end | TIME | 在线时段结束（nullable）|
| last_message_at | TIMESTAMPTZ | 最近消息时间 |
| created_at | TIMESTAMPTZ | 创建时间 |

**约束：** `UNIQUE(account_id, xhs_user_id)`
**索引：** `INDEX(merchant_id, mode, last_message_at DESC)`

---

#### `messages` — 消息记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| xhs_msg_id | VARCHAR(64) UNIQUE | 小红书平台消息 ID（防重）|
| conversation_id | UUID FK | 所属会话（indexed）|
| role | ENUM | user/assistant |
| content | TEXT | 消息内容 |
| intent | VARCHAR(32) | 意图分类（仅 user 消息）|
| intent_confidence | FLOAT | 意图置信度 |
| sentiment_score | FLOAT | 情绪分数 |
| sent_at | TIMESTAMPTZ | 发送时间 |

**索引：** `INDEX(conversation_id, sent_at DESC)`

---

#### `intent_logs` — 意图识别日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| source_type | ENUM | comment/message |
| source_id | UUID | 来源记录 ID |
| raw_input | TEXT | 原始输入文本 |
| intent | VARCHAR(32) | 识别结果 |
| confidence | FLOAT | 置信度 |
| sentiment_score | FLOAT | 情绪分数 |
| llm_latency_ms | INTEGER | LLM 调用耗时（毫秒）|
| created_at | TIMESTAMPTZ | 记录时间 |

**索引：** `INDEX(merchant_id, created_at DESC)`

---

#### `hitl_queue` — HITL 待审核队列

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| conversation_id | UUID FK (nullable) | 关联会话（私信时）|
| comment_id | UUID FK (nullable) | 关联评论（评论时）|
| trigger_reason | VARCHAR(64) | 触发原因 |
| original_content | TEXT | 原始用户输入 |
| suggested_reply | TEXT | AI 建议回复（nullable）|
| final_reply | TEXT | 最终回复（审核通过后填入）|
| status | ENUM | pending/approved/rejected/edited |
| reviewed_by | UUID (nullable) | 审核人 |
| reviewed_at | TIMESTAMPTZ (nullable) | 审核时间 |
| created_at | TIMESTAMPTZ | 入队时间 |

**索引：** `INDEX(merchant_id, status, created_at DESC)`

---

#### `dm_trigger_logs` — 私信触发去重日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 所属商家 |
| account_id | UUID | 商家账号 FK |
| xhs_user_id | VARCHAR(64) | 用户 ID |
| xhs_comment_id | VARCHAR(64) | 对应评论 ID |
| intent | VARCHAR(32) | 触发意图 |
| triggered_at | TIMESTAMPTZ | 触发时间 |
| expires_at | TIMESTAMPTZ | 过期时间（+24h）|

**索引：** `INDEX(merchant_id, xhs_user_id, intent, expires_at)`

---

## 5. API 接口设计

### 5.1 监测笔记配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/interaction/monitored-notes` | 获取监测笔记列表（支持账号/状态筛选）|
| POST | `/api/v1/interaction/monitored-notes` | 添加监测笔记 |
| PUT | `/api/v1/interaction/monitored-notes/{id}` | 更新监测配置（间隔/批次大小）|
| DELETE | `/api/v1/interaction/monitored-notes/{id}` | 移除监测笔记 |

### 5.2 评论管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/interaction/comments` | 评论列表（cursor 分页、状态/意图筛选）|
| GET | `/api/v1/interaction/comments/{id}` | 评论详情（含 OCR 结果）|
| POST | `/api/v1/interaction/comments/{id}/classify` | 手动触发意图分类 |
| POST | `/api/v1/interaction/comments/{id}/reply` | 发送评论回复（Playwright RPA）|

### 5.3 私信会话

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/interaction/conversations` | 会话列表（cursor 分页、模式筛选）|
| GET | `/api/v1/interaction/conversations/{id}` | 会话详情（含模式状态）|
| GET | `/api/v1/interaction/conversations/{id}/messages` | 消息历史（cursor 分页）|
| POST | `/api/v1/interaction/conversations/{id}/reply` | 发送私信回复（Playwright RPA）|
| POST | `/api/v1/interaction/conversations/{id}/takeover` | 切换人工接管 |
| POST | `/api/v1/interaction/conversations/{id}/release` | 解除人工接管 |
| PUT | `/api/v1/interaction/conversations/{id}/online-hours` | 配置在线时段 |

### 5.4 HITL 审核

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/interaction/hitl/queue` | HITL 待审核队列（cursor 分页）|
| POST | `/api/v1/interaction/hitl/{id}/approve` | 审核通过 |
| POST | `/api/v1/interaction/hitl/{id}/edit-approve` | 修改后通过 |
| POST | `/api/v1/interaction/hitl/{id}/reject` | 拒绝回复 |
| POST | `/api/v1/interaction/hitl/batch-approve` | 批量审核通过（≤20 条）|

---

## 6. 响应格式

### 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code: 0` = 成功，非零 = 业务错误
- 错误码范围：40301–40399（互动模块）

### 分页响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "next_cursor": "xxx",
    "has_more": false
  }
}
```

### 统一错误响应

```json
{
  "code": 40301,
  "message": "评论不存在",
  "data": null
}
```

---

## 7. 前端页面结构

### 7.1 互动与客服页面 `/interaction`

```
互动与客服页面
├── 概览统计卡（4 个 StatCard）
│   ├── 待处理评论数
│   ├── 活跃会话数
│   ├── HITL 待审核数
│   └── 今日自动回复数
├── 评论监测区块
│   ├── 监测笔记配置列表
│   │   ├── 笔记标题 / 账号 / 状态 / 检查间隔
│   │   └── 编辑 / 删除 按钮
│   └── 添加监测笔记表单
├── 评论列表区块
│   ├── 筛选栏（账号/笔记/状态/意图）
│   ├── 评论表格
│   │   ├── 用户 / 内容 / 意图 / 情绪 / 状态 / 时间
│   │   └── 操作（查看详情 / 手动分类 / 回复）
│   └── 分页导航
├── 私信会话区块
│   ├── 会话列表（按模式筛选）
│   │   └── 用户 / 最后消息时间 / 模式标签（自动/人工/待处理）
│   └── 会话详情面板
│       ├── 消息历史（10 轮上下文）
│       ├── 回复输入框
│       ├── 人工接管 / 解除接管 按钮
│       └── 在线时段配置
├── HITL 审核工作台 `/interaction/hitl`
│   ├── 待审核队列列表
│   │   ├── 来源（评论/私信）/ 触发原因 / 原始内容
│   │   ├── AI 建议回复
│   │   └── 操作（通过 / 编辑通过 / 拒绝）
│   └── 批量审核（≤20 条）
```

---

## 8. 验收检查清单

### D1 — 评论实时监测
- [ ] Celery Beat 每 10 秒触发评论探测任务
- [ ] 令牌桶 + 随机抖动控制执行频率
- [ ] 按时间排序 + 时间戳过滤 + Redis ID 幂等三重增量检测
- [ ] 含图片评论自动 OCR 识别（置信度 < 0.5 时进入 HITL）
- [ ] 24h 内相同意图评论仅触发一次私信

### D2 — 多层级意图识别
- [ ] 评论 6 类 + 私信 7 类意图分类
- [ ] 评论分类 10 秒内返回，私信 15 秒内返回
- [ ] 情绪分数输出（-1.0 ~ +1.0）
- [ ] 置信度 < 0.7 自动进入 HITL
- [ ] 特定意图（complaint/high_value_bd/competitor_mention/strong_negative）触发 HITL

### D3 — 自动化私信触发
- [ ] `ask_price` → 含价格区间私信
- [ ] `ask_link` → 含商品链接/店铺入口私信
- [ ] `complaint` → 不触发私信，进入 HITL
- [ ] `competitor_mention` → 阻止自动回复，标记竞品原因进入 HITL
- [ ] `purchase_intent` → 含支付链接/客服联系方式转化话术
- [ ] 发送前必须通过风控扫描（模块 E）
- [ ] 频率限制 ≤ 50 次/小时/账号（模块 E）

### D4 — 人工接管触发
- [ ] `sentiment_score < -0.8` 立即 App + 短信双渠道强提醒
- [ ] `high_value_bd` 私信意图立即触发人工接管
- [ ] 人工接管期间暂停所有自动回复
- [ ] 商家可通过 `/release` 解除接管

### D5 — 实时客服回复
- [ ] 消息到达后响应延迟 ≤ 5 秒（目标值）
- [ ] 意图分类 3 秒内返回
- [ ] 融合 RAG 检索 + 最近 10 轮上下文生成回复
- [ ] 连接中断时消息暂存 Redis，恢复后 30 秒内补发
- [ ] 在线时段外自动回复"稍后为您解答"并进入待处理队列
- [ ] 上下文窗口严格保留最近 10 轮

### D6 — RPA 防检测
- [ ] 人类行为模拟：随机延迟（3~15s）、分步滚动、随机偏移点击、逐字输入
- [ ] 设备指纹一致性：Browser Context 按账号复用
- [ ] Captcha 检测 7 种选择器，检测到立即停止并通知商家
- [ ] 操作前检查账号状态（auth_expired/banned/suspended 账号拒绝操作）
