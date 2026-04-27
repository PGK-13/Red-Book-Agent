# 模块 D — 互动与意图路由 实现总结

> 分支: `feature/module-d-interaction`
> 技术选型: 纯 Playwright RPA，不依赖官方 API（headless=True）

---

## 1. 修改文件清单

### 1.1 新建文件（19 个）

| 文件 | 说明 |
|------|------|
| `agent/graphs/intent_router.py` | 意图路由 LangGraph 图（评论 6 类 + 私信 7 类） |
| `agent/graphs/customer_service.py` | 实时客服 LangGraph 图（11 节点编排） |
| `agent/tools/playwright_rpa_base.py` | RPA 基础：Browser Context 复用、人类行为模拟、Captcha 检测 |
| `agent/tools/playwright_comment_monitor.py` | 评论监测：时间排序 + 时间戳解析 + ID 幂等去重 |
| `agent/tools/playwright_dm_monitor.py` | 私信轮询：消息列表解析 + msg_id 去重 |
| `agent/tools/playwright_dm_sender.py` | 私信发送：模拟人工输入 + 发送 |
| `agent/tools/playwright_comment_replier.py` | 评论回复：定位评论 + 模拟回复（15~80 字校验） |
| `backend/app/services/note_polling_scheduler.py` | 令牌桶 + 随机抖动调度器 |
| `backend/app/services/interaction_service.py` | 核心服务编排（追加 RPA 方法） |
| `worker/tasks/comment_probe_task.py` | 评论探测 Celery 任务（每 10s） |
| `worker/tasks/dm_probe_task.py` | 私信探测 Celery 任务（每 5s） |
| `worker/tasks/dm_pending_task.py` | 待发送消息补发任务（每 10s） |
| `worker/tasks/captcha_recovery_task.py` | Captcha 恢复检查任务（每 5min） |

### 1.2 修改文件（10 个）

| 文件 | 变更 |
|------|------|
| `agent/prompts/intent_classification.py` | 评论 6 类 + 私信 7 类分类 prompt |
| `agent/tools/ocr_tool.py` | PaddleOCR 实现（置信度 < 0.5 返回空） |
| `agent/tools/risk_scan.py` | `RiskScanResult` dataclass + `scan_content()` |
| `agent/tools/rag_retrieval.py` | `hybrid_search()` stub（待模块 B 实现） |
| `backend/app/models/interaction.py` | 7 个 ORM 模型 + `last_seen_comment_id` 字段 |
| `backend/app/schemas/interaction.py` | Pydantic Schema（请求/响应全部覆盖） |
| `backend/app/api/v1/interaction.py` | 16 个 API 路由（含 RPA 真实调用） |
| `backend/app/db/migrations/versions/003_create_interaction_tables.py` | Alembic 迁移（7 张表 + 索引） |
| `worker/beat_schedule.py` | 注册 4 个 Module D 定时任务 |
| `worker/celery_app.py` | 注册 4 个新 task 模块 |

---

## 2. 架构设计

### 2.1 分层架构

```
API Router (interaction.py)
    ↓ 参数校验 + 响应封装
InteractionService (interaction_service.py)
    ↓ 业务编排（去重、HITL、上下文截断）
Agent Graph (intent_router / customer_service)
    ↓ LLM 意图分类 + 回复生成
Playwright RPA Tools (playwright_*.py)
    ↓ headless 浏览器自动化
小红书平台
```

**非协商分层规则：** API 层只做校验和封装，Service 层做编排，ORM 层零业务逻辑，Agent 不直接访问数据库。

### 2.2  Agent 图

**IntentRouterGraph** — 意图分类：

```
START → classify_intent (GPT-4o) → END
```

- 评论场景 6 类：`ask_price` / `complaint` / `ask_link` / `general_inquiry` / `competitor_mention` / `other`
- 私信场景 7 类：上述 `competitor_mention` 替换为 `purchase_intent` + `high_value_bd`
- 置信度 < 0.7 或特定意图 → `needs_human_review = True`

**CustomerServiceGraph** — 实时客服：

```
START → check_mode → check_captcha → classify_intent → check_human_review
     → check_online_hours → load_memory → rag_retrieve → generate_reply
     → risk_scan → humanized_send → pending_queue → END
```

- 4 个条件分支断路：人工接管 / Captcha 阻断 / 需人工审核 / 非在线时段
- 端到端延迟目标 ≤ 5s

### 2.3 数据模型

```
MonitoredNote ──→ (监测笔记配置，含 last_seen_comment_id + last_checked_at)
Comment ──→ (xhs_comment_id 唯一，含 OCR 结果、意图分类)
Conversation ──→ (UNIQUE(account_id, xhs_user_id)，含在线时段)
Message ──→ (xhs_msg_id 唯一，含 10 轮截断)
IntentLog ──→ (分类日志，含 llm_latency_ms)
HITLQueue ──→ (人工审核队列，trigger_reason 含 captcha_detected)
DMTriggerLog ──→ (24h 去重，含 expires_at)
```

---

## 3. 核心策略设计

### 3.1 评论增量检测：时间排序 + 时间戳过滤 + ID 幂等

**问题：** 小红书评论默认"最热"排序，列表每次重排。用 `last_known_comment_count` 索引切片会在重排时重复处理或漏检。

**方案演进：**

| 阶段 | 方案 | 问题 |
|------|------|------|
| V1 | `all_comments[last_known_count:]` 索引切片 | 平台重排序 → 索引错位 |
| V2 | `last_seen_comment_id` 游标 ID 定位 | 游标 ID 可能不在当前列表中 |
| **V3** | **时间排序 + 时间戳过滤 + Redis ID 集合** | **三重保障** |

**V3 最终方案流程：**

```
打开笔记页
  → 检查 Captcha
  → 点击"按时间排序"按钮（确保列表时间序稳定）
  → 解析每条评论的时间戳
  → 过滤：parsed_at > last_checked_at（时间增量）
  → 遇到旧评论立即 break（不滚全量历史）
  → Redis xhs_comment_id 集合去重（幂等兜底）
  → 更新 note.last_checked_at = 本次轮询时间
```

**为什么采用三层防护：**

1. **时间排序** — 列表稳定，新评论始终在前，旧评论在后。可提前 `break` 停止滚动
2. **时间戳过滤** — 即使排序按钮点击失败，时间戳差距仍然可靠
3. **Redis ID 集合** — 时间戳解析失败时兜底，绝对不重复处理同一条评论

### 3.2 令牌桶 + 随机抖动（防检测核心）

```
NotePollingScheduler
├── 令牌桶 (capacity=10, refill_rate=1/s) → 控制处理速率
├── 抖动延迟 (base_delay ±50%) → 避免固定间隔
├── 批次开始前随机等待 (5~25s) → 避免批量操作特征
└── 批次间间隔 (3~15s) → 模拟人类浏览节奏
```

**Redis 存储：**
- `rpa:token_bucket:{account_id}` — 令牌桶状态
- `rpa:last_probe:{account_id}` — 上次探测时间

### 3.3 Captcha 检测与应对

```
RPA 操作中检测到 Captcha
  → 立即停止该账号所有自动化
  → 设置 Redis rpa:captcha_flag:{account_id}
  → 写入 HITL 队列 (trigger_reason=captcha_detected)
  → 发送 App + 短信告警
  → 商家人工处理后点击"已处理" → 清除 Redis flag
  → CaptchaRecoveryTask 每 5 分钟检查恢复情况
```

**不设计自动破解**：成功率低且有封号风险，完全依赖人工处理。

### 3.4 私信 24h 去重

```
check_dm_deduplication(merchant_id, account_id, xhs_user_id, xhs_comment_id, intent)
  → 先查 Redis 缓存 (dm:dedup:{...})
  → 再查 db dm_trigger_logs (expires_at > now)
  → 存在 → 跳过触发
  → 不存在 → record_dm_trigger() 写入 Redis + DB (TTL=24h)
```

### 3.5 上下文截断（10 轮窗口）

```
append_message(conversation_id, role, content)
  → 写入 messages 表
  → SELECT * FROM messages WHERE conversation_id = ? ORDER BY sent_at DESC
  → 若 > 10 条：DELETE 第 11 条及更早的消息
  → 更新 conversations.last_message_at
```

### 3.6 人类行为模拟（7 项措施）

| 措施 | 实现 | 目的 |
|------|------|------|
| 随机延迟 | `humanized_delay(3~15s)` | 避免固定操作间隔 |
| 分步滚动 | `human_scroll()` 2~4 步，每步 0.5~1.5s | 模拟人类浏览 |
| 随机偏移点击 | `human_click()` ±3px 偏移 | 避免固定坐标 |
| 逐字输入 | `human_type()` 每字 50~150ms | 模拟打字速度 |
| 设备指纹一致性 | Browser Context 按 account_id 复用 | Cookie/UA/Viewport 一致 |
| Captcha 检测 | `check_captcha()` 7 种选择器 | 及时停止避免更严重封号 |
| 令牌桶限速 | `NotePollingScheduler` | 频率不超阈值 |

---

## 4. Redis Key 设计

| Key Pattern | 用途 | TTL |
|-------------|------|-----|
| `dm:dedup:{merchant_id}:{account_id}:{xhs_user_id}:{xhs_comment_id}` | 私信去重 | 24h |
| `session:context:{conversation_id}` | 短期上下文（最近 10 轮） | 无 |
| `session:memory:{xhs_user_id}` | 用户长期记忆 | 无 |
| `session:pending:{conversation_id}` | 待补发消息队列 | 无 |
| `rpa:captcha_flag:{account_id}` | Captcha 阻断标记 | 永久（手动清除） |
| `rpa:token_bucket:{account_id}` | 令牌桶状态 | 无 |
| `rpa:last_probe:{account_id}` | 上次探测时间 | 无 |
| `comment:known_ids:{account_id}:{xhs_note_id}` | 已处理评论 ID 集合 | 无（可定期清理） |
| `dm:known_msg_ids:{account_id}` | 已知私信消息 ID | 无 |

---

## 5. Celery Beat 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| `comment-probe` | 每 10s | 通过令牌桶控制实际执行 |
| `dm-probe` | 每 5s | 私信轮询 |
| `dm-pending` | 每 10s | 补发 pending 队列消息 |
| `captcha-recovery` | 每 5min | 检查 Captcha 恢复 |

---

## 6. API 路由总览（16 个端点）

### 监测笔记配置
- `GET    /api/v1/interaction/monitored-notes` — 列表
- `POST   /api/v1/interaction/monitored-notes` — 添加
- `PUT    /api/v1/interaction/monitored-notes/{id}` — 更新
- `DELETE /api/v1/interaction/monitored-notes/{id}` — 删除

### 评论管理
- `GET    /api/v1/interaction/comments` — 列表（cursor 分页）
- `GET    /api/v1/interaction/comments/{id}` — 详情
- `POST   /api/v1/interaction/comments/{id}/classify` — 手动意图分类
- `POST   /api/v1/interaction/comments/{id}/reply` — 发送回复（RPA）

### 私信会话
- `GET    /api/v1/interaction/conversations` — 列表（cursor 分页）
- `GET    /api/v1/interaction/conversations/{id}` — 详情
- `GET    /api/v1/interaction/conversations/{id}/messages` — 消息历史
- `POST   /api/v1/interaction/conversations/{id}/reply` — 发送私信（RPA）
- `POST   /api/v1/interaction/conversations/{id}/takeover` — 人工接管
- `POST   /api/v1/interaction/conversations/{id}/release` — 解除接管
- `PUT    /api/v1/interaction/conversations/{id}/online-hours` — 在线时段

### HITL 审核
- `GET    /api/v1/interaction/hitl/queue` — 待审核队列
- `POST   /api/v1/interaction/hitl/{id}/approve` — 审核通过
- `POST   /api/v1/interaction/hitl/{id}/edit-approve` — 修改后通过
- `POST   /api/v1/interaction/hitl/{id}/reject` — 拒绝
- `POST   /api/v1/interaction/hitl/batch-approve` — 批量通过（≤20 条）

---

## 7. 已知待完成项

| 项目 | 状态 | 阻塞原因 |
|------|------|----------|
| `trigger_dm_for_comment` 私信内容生成 | TODO | 需要 RAG 检索 + 回复模板 |
| `rag_retrieval.hybrid_search` Qdrant 实现 | TODO | 模块 B 未完成 |
| `risk_service.scan_output` 真实风控 | TODO | 模块 E 未完成 |
| `risk_service.check_and_reserve_quota` 配额 | TODO | 模块 E 未完成 |
| 属性测试（Task 11） | 未开始 | 前置依赖完成后编写 |
| 集成测试（Task 11） | 未开始 | 前置依赖完成后编写 |
| CSS 选择器精确化 | 占位符 | 需实际抓取小红书页面确定 |

---

## 8. 关键设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 技术路线 | Playwright RPA（非官方 API） | 小红书 API 需企业资质，个人/小商户无法获取 |
| 浏览器模式 | headless=True | 纯后端操作，商户不需要看浏览器 |
| Captcha | 人工处理（不自动破解） | 自动破解成功率低且有封号风险 |
| 评论排序 | 强制"按时间排序" | 默认"最热"排序不稳定，时间序才能做增量检测 |
| 去重方案 | 时间戳 + ID 集合双重保障 | 单一方案在平台重排时可能失效 |
| 防检测策略 | 7 项人类化措施 | 反检测优先级高于实时性 |
| DB 会话传递 | 通过 State.db 字段注入 | LangGraph 节点无法自动获取 FastAPI DI 会话 |
| 代理策略 | 可配置（独享/共享） | 不同商户预算不同 |
| 轮询策略 | 令牌桶 + 随机抖动 | 避免固定频率被平台识别为机器人 |
