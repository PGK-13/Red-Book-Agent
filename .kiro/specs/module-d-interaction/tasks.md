# Implementation Plan: 模块 D — 互动与意图路由

## Overview

基于现有项目骨架，按分层架构逐步实现模块 D：ORM 模型 → Schema → Service 编排 → API 路由 → Agent 图 → Playwright RPA 工具 → 集成测试 → 属性测试。

**技术选型**：所有与小红书平台的交互均采用 Playwright RPA 实现，不依赖官方 API。

重点执行顺序：
1. ORM + Schema（基础设施）
2. 笔记监测配置 + 评论基础流程
3. 私信 + 实时客服流程
4. Playwright RPA 工具封装
5. 防检测 + 令牌桶调度
6. Agent 图 + HITL
7. 测试

## Tasks

- [x] 1. 实现 SQLAlchemy ORM 模型
  - [x] 1.1 在 `backend/app/models/interaction.py` 中实现 `Comment` ORM 模型
    - 替换现有 TODO stub
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK)`、`xhs_note_id(VARCHAR 64)`、`xhs_comment_id(VARCHAR 64, UNIQUE)`、`xhs_user_id(VARCHAR 64)`、`content(TEXT)`、`image_urls(TEXT[])`、`ocr_result(TEXT, nullable)`、`intent(VARCHAR 32)`、`intent_confidence(FLOAT)`、`sentiment_score(FLOAT)`、`reply_status(Enum: pending/replied/manual_review/skipped)`、`deduplicated(BOOLEAN)`、`detected_at(TIMESTAMPTZ)`、`created_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(merchant_id, reply_status, created_at DESC)`、`INDEX(account_id, xhs_note_id, created_at DESC)`
    - _Requirements: D1.1, D1.2, D1.4_
  - [x] 1.2 在 `backend/app/models/interaction.py` 中新增 `Conversation` ORM 模型
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK)`、`xhs_user_id(VARCHAR 64)`、`mode(Enum: auto/human_takeover/pending)`、`user_long_term_memory(JSONB)`、`online_hours_start(TIME, nullable)`、`online_hours_end(TIME, nullable)`、`last_message_at(TIMESTAMPTZ)`、`created_at(TIMESTAMPTZ)`
    - 添加唯一约束：`UNIQUE(account_id, xhs_user_id)`
    - 添加索引：`INDEX(merchant_id, mode, last_message_at DESC)`
    - _Requirements: D3.1, D4.1, D4.2, D4.3, D5.3, D5.6_
  - [x] 1.3 在 `backend/app/models/interaction.py` 中新增 `Message` ORM 模型
    - 字段：`id(UUID PK)`、`conversation_id(UUID FK, indexed)`、`role(Enum: user/assistant)`、`content(TEXT)`、`intent(VARCHAR 32, nullable)`、`intent_confidence(FLOAT, nullable)`、`sentiment_score(FLOAT, nullable)`、`sent_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(conversation_id, sent_at DESC)`
    - _Requirements: D3.8, D5.4_
  - [x] 1.4 在 `backend/app/models/interaction.py` 中新增 `IntentLog` ORM 模型
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`source_type(Enum: comment/message)`、`source_id(UUID)`、`raw_input(TEXT)`、`intent(VARCHAR 32)`、`confidence(FLOAT)`、`sentiment_score(FLOAT)`、`llm_latency_ms(INT)`、`created_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(merchant_id, created_at DESC)`
    - _Requirements: D2.1, D2.2, D2.3_
  - [x] 1.5 在 `backend/app/models/interaction.py` 中新增 `HITLQueue` ORM 模型
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`conversation_id(UUID FK, nullable)`、`comment_id(UUID FK, nullable)`、`trigger_reason(VARCHAR 64)`、`original_content(TEXT)`、`suggested_reply(TEXT, nullable)`、`final_reply(TEXT, nullable)`、`status(Enum: pending/approved/rejected/edited)`、`reviewed_by(UUID, nullable)`、`reviewed_at(TIMESTAMPTZ, nullable)`、`created_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(merchant_id, status, created_at DESC)`
    - `trigger_reason` 新增 `captcha_detected` 值
    - _Requirements: D1.3, D2.4, D4.1, D4.2, D5.7_
  - [x] 1.6 在 `backend/app/models/interaction.py` 中新增 `DMTriggerLog` ORM 模型
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK)`、`xhs_user_id(VARCHAR 64)`、`xhs_comment_id(VARCHAR 64)`、`intent(VARCHAR 32)`、`triggered_at(TIMESTAMPTZ)`、`expires_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(merchant_id, xhs_user_id, intent, expires_at)`
    - _Requirements: D1.4, D3.6_
  - [x] 1.7 在 `backend/app/models/interaction.py` 中新增 `MonitoredNote` ORM 模型
    - 字段：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK)`、`xhs_note_id(VARCHAR 64)`、`note_title(VARCHAR 256)`、`is_active(BOOLEAN, default=True)`、`check_interval_seconds(INT, default=60)`、`batch_size(INT, default=3)`、`last_checked_at(TIMESTAMPTZ, nullable)`、`last_known_comment_count(INT, default=0)`、`last_seen_comment_id(VARCHAR 64, nullable)`、`created_at(TIMESTAMPTZ)`
    - 添加索引：`INDEX(account_id, is_active, last_checked_at ASC)`
    - _Requirements: D1.1_
  - [x] 1.8 创建 Alembic 迁移脚本生成 `comments`、`conversations`、`messages`、`intent_logs`、`hitl_queue`、`dm_trigger_logs`、`monitored_notes` 表及其索引和约束
    - _Requirements: D1.1, D2.1, D3.1, D4.1, D5.3_

- [x] 2. 实现 Pydantic Schema
  - [x] 2.1 创建 `backend/app/schemas/interaction.py`
    - 笔记监测：`MonitoredNoteCreateRequest`、`MonitoredNoteUpdateRequest`、`MonitoredNoteListRequest`
    - 评论相关：`CommentIntentRequest`、`CommentIntentResponse`、`CommentReplyRequest`、`CommentListRequest`
    - 私信相关：`DMIntentRequest`、`DMReplyRequest`、`ConversationModeRequest`、`ConversationListRequest`、`MessageListRequest`
    - HITL 相关：`HITLApproveRequest`、`HITLEditApproveRequest`、`HITLRejectRequest`、`HITLBatchApproveRequest`、`HITLQueueItemResponse`
    - _Requirements: D1.1, D2.1, D3.1, D4.1, D5.1_

- [x] 3. 实现 InteractionService 核心业务逻辑
  - [x] 3.1 实现笔记监测配置方法
    - `add_monitored_note(merchant_id, data, db)`：商家添加监测笔记，写入 `monitored_notes` 表
    - `remove_monitored_note(merchant_id, note_id, db)`：移除监测笔记配置
    - `list_monitored_notes(merchant_id, account_id, is_active, db)`：查询监测笔记列表
    - _Requirements: D1.1_
  - [x] 3.2 实现评论监测核心方法
    - `check_monitored_notes(account_id, db)`：按令牌桶调度，批量检查账号下所有激活笔记的新评论。每批最多处理 `batch_size` 篇，每篇之间注入随机延迟
    - `process_single_note_comments(merchant_id, note_id, db)`：通过 Playwright RPA 获取笔记评论列表，使用时间戳增量检测（last_checked_at），Redis ID 集合幂等兜底
    - OCR + 意图分类集成在评论处理流程中
    - _Requirements: D1.1, D1.2_
  - [x] 3.3 实现去重检查方法
    - `check_dm_deduplication(merchant_id, account_id, xhs_user_id, xhs_comment_id, intent, db)`：查询 `dm_trigger_logs` 表是否存在未过期记录；检查 Redis 缓存键
    - 返回 `True` 表示已去重，`False` 表示需要触发
    - 触发后写入 `dm_trigger_logs`，`expires_at` 为 24 小时后
    - _Requirements: D1.4, D3.6_
  - [x] 3.4 实现意图分类编排方法
    - `classify_comment_intent(merchant_id, content, account_id, db)`：调用 `IntentRouterGraph`，返回 `IntentClassificationResult`
    - `classify_dm_intent(merchant_id, conversation_id, content, db)`：调用 `IntentRouterGraph`，返回 `IntentClassificationResult`
    - _Requirements: D2.1, D2.2, D2.3_
  - [x] 3.5 实现私信触发方法
    - `trigger_dm_for_comment(merchant_id, comment_id, intent, db)`：获取评论信息 → 获取/创建会话 → 调用 CustomerServiceGraph 生成并发送私信 → 记录去重
    - `trigger_dm_for_conversation` 由 `poll_dm_messages` 中的 CustomerServiceGraph.reply() 实现
    - _Requirements: D3.1, D3.2, D3.3, D3.4, D3.5, D3.7_
  - [x] 3.6 实现 RPA 发送方法（不依赖官方 API）
    - `send_dm_via_rpa(merchant_id, account_id, xhs_user_id, content, db)`：通过 Playwright RPA 发送私信。调用 `humanized_delay()` 注入随机等待，执行风控扫描，频率配额检查，调用 `PlaywrightDM工具` 模拟操作
    - `reply_comment_via_rpa(merchant_id, account_id, xhs_note_id, xhs_comment_id, reply_content, db)`：通过 Playwright RPA 发送评论回复。回复字数 15~80 汉字
    - _Requirements: D3.1, D3.2, D3.3, D3.4, D3.7_
  - [x] 3.7 实现会话管理方法
    - `get_or_create_conversation(merchant_id, account_id, xhs_user_id, db)`：根据 `account_id + xhs_user_id` 查找会话，不存在则创建
    - `get_conversation_by_id(conversation_id, db)`：根据 ID 获取会话
    - `switch_to_human_takeover(merchant_id, conversation_id, reason, db)`：更新 `conversations.mode`，调用通知服务发送提醒
    - `release_human_takeover(merchant_id, conversation_id, db)`：恢复 `mode = auto`
    - _Requirements: D4.1, D4.2, D4.3_
  - [x] 3.8 实现上下文与记忆方法
    - `list_messages(conversation_id, limit, db)`：查询最近 N 条消息
    - `append_message(...)`：追加消息到 `messages` 表，自动截断超过 10 轮
    - _Requirements: D5.4, Property 12_
  - [x] 3.9 实现在线时段检查
    - `is_within_online_hours(account_id, db)`：读取 `conversations.online_hours_start/end`，与当前时间比对
    - 若会话无配置或当前在时段外，返回 `False`，触发"稍后为您解答"回复
    - _Requirements: D5.6_
  - [x] 3.10 实现 HITL 审核方法
    - `enqueue_hitl(...)`：将审核项写入 `hitl_queue` 表
    - `approve_hitl(merchant_id, queue_id, final_reply, reviewer_id, db)`：审核通过后调用 `reply_comment_via_rpa()` 或 `send_dm_via_rpa()`
    - `edit_approve_hitl(...)`：修改后通过
    - `reject_hitl(merchant_id, queue_id, reviewer_id, reason, db)`：记录拒绝原因
    - _Requirements: D1.3, D2.4, D4.1, D5.7_
  - [x] 3.11 实现 Captcha 检测处理
    - `handle_captcha_detected(account_id, trigger_reason, db)`：设置 Redis 标记，入 HITL 队列，发送告警
    - `is_captcha_blocked(account_id)`：检查 Redis `rpa:captcha_flag:{account_id}`
    - `clear_captcha_flag(account_id)`：清除阻断标记
    - _Requirements: D1.3, D4.1_
  - [x] 3.12 实现 Playwright RPA 轮询方法
    - `poll_dm_messages(account_id, db)`：通过 Playwright RPA 轮询商家端消息页面，检测新私信，写入 `messages` 表，触发自动回复
    - `check_monitored_notes` 承担笔记评论轮询角色，检查账号 `status`
    - _Requirements: D1.1, D5.1, D5.2_

- [ ] 4. Checkpoint — 确保 InteractionService 编排完整
  - [x] 确保所有 Service 方法按 `merchant_id` 做数据隔离
  - [x] 确保 `IntentClassificationResult` 统一传递给上游
  - [x] 确保 RPA 操作前检查账号状态和 Captcha 阻断标记
  - [ ] 测试未编写（Task 11 待完成）

- [x] 5. 实现 API 路由层
  - [x] 5.1 在 `backend/app/api/v1/interaction.py` 中实现笔记监测配置路由
    - 替换现有 TODO stub
    - GET `/interaction/monitored-notes` → 调用 `InteractionService.list_monitored_notes`
    - POST `/interaction/monitored-notes` → 调用 `InteractionService.add_monitored_note`
    - PUT `/interaction/monitored-notes/{id}` → 调用 `InteractionService.update_monitored_note`
    - DELETE `/interaction/monitored-notes/{id}` → 调用 `InteractionService.remove_monitored_note`
    - 所有路由注入 `CurrentMerchantId` 与 `DbSession`
    - _Requirements: D1.1_
  - [x] 5.2 实现评论管理路由
    - GET `/interaction/comments` → 评论列表
    - GET `/interaction/comments/{id}` → 评论详情
    - POST `/interaction/comments/{id}/classify` → 手动触发意图分类
    - POST `/interaction/comments/{id}/reply` → 发送评论回复（Playwright RPA）
    - _Requirements: D1.1, D1.4, D2.1_
  - [x] 5.3 实现私信会话路由
    - GET `/interaction/conversations` → 会话列表
    - GET `/interaction/conversations/{id}` → 会话详情
    - GET `/interaction/conversations/{id}/messages` → 消息历史
    - POST `/interaction/conversations/{id}/reply` → 发送私信回复（Playwright RPA）
    - POST `/interaction/conversations/{id}/takeover` → 切换人工接管
    - POST `/interaction/conversations/{id}/release` → 解除人工接管
    - POST `/interaction/conversations/{id}/poll` → 手动触发私信轮询（调试用）
    - PUT `/interaction/conversations/{id}/online-hours` → 配置在线时段
    - _Requirements: D3.1, D4.1, D4.3, D5.3, D5.6_
  - [x] 5.4 实现 HITL 审核路由
    - GET `/interaction/hitl/queue` → HITL 待审核队列
    - POST `/interaction/hitl/{id}/approve` → 审核通过
    - POST `/interaction/hitl/{id}/edit-approve` → 修改后通过
    - POST `/interaction/hitl/{id}/reject` → 拒绝回复
    - POST `/interaction/hitl/batch-approve` → 批量审核通过（最多 20 条）
    - _Requirements: D1.3, D2.4, D4.1, D5.7_

- [x] 6. 实现 Agent 意图路由图
  - [x] 6.1 在 `agent/graphs/intent_router.py` 中实现 `IntentRouterGraph`
    - 替换现有 TODO stub
    - 使用 LangGraph StateGraph + GPT-4o 进行意图分类
    - 评论场景（6 类）和私信场景（7 类）共用同一 Agent，通过 `source_type` 参数区分
    - 输出：`intent`、`confidence`、`sentiment_score`、`needs_human_review`、`review_reason`
    - _Requirements: D2.1, D2.2, D2.3, D2.4_
  - [x] 6.2 更新 `agent/prompts/intent_classification.py`
    - 统一意图分类 prompt，支持评论（6 类）和私信（7 类）两套分类
    - 输出 JSON 格式：`{"intent": "...", "confidence": 0.0-1.0, "sentiment_score": -1.0-1.0}`
    - _Requirements: D2.1, D2.2_

- [x] 7. 实现 Agent 实时客服图
  - [x] 7.1 在 `agent/graphs/customer_service.py` 中实现 `CustomerServiceGraph`
    - 替换现有 TODO stub
    - 节点编排：`check_mode` → `check_captcha` → `classify_intent` → `check_human_review` → `check_online_hours` → `load_memory` → `rag_retrieve` → `generate_reply` → `risk_scan` → `humanized_send` → `pending_queue`
    - 4 个条件分支：人工接管 / Captcha 阻断 / 需审核 / 非在线时段 → 直接 END
    - 所有节点已连接真实实现（非 mock）
    - 连接中断时通过 Redis `session:pending:{conversation_id}` 队列补发
    - _Requirements: D5.1, D5.2, D5.3, D5.4, D5.5, D5.6, D5.7, Property 11_
  - [x] 7.2 客服回复 prompt 在 `generate_reply_node` 内联实现
    - 支持多轮对话上下文注入（最近 10 轮）
    - 支持在线时段外回复"稍后为您解答"的场景
    - 支持 RAG 检索结果注入
    - _Requirements: D5.4, D5.6_

- [x] 8. 实现 Playwright RPA 工具层
  - [x] 8.1 在 `agent/tools/` 下新增 `playwright_rpa_base.py`
    - 实现 `HumanizedBrowserContext` 上下文管理器
    - 每个账号的 Browser Context 复用 `ProxyConfig` 构建设备指纹一致的上下文
    - 实现 `humanized_delay()`、`human_scroll()`、`human_click()`、`human_type()` 等基础随机化方法
    - 实现 `check_captcha()` Captcha 检测方法（7 种选择器）
    - _Requirements: 防检测设计_
  - [x] 8.2 在 `agent/tools/` 下新增 `playwright_comment_monitor.py`
    - 实现 `poll_note_comments(page, note_url, last_checked_at, known_comment_ids)` 方法
    - 点击"按时间排序"确保列表稳定 → 解析时间戳 → 时间过滤 + Redis ID 幂等去重
    - 遇到旧评论提前 break，不滚全量历史
    - 检测并报告 Captcha 状态
    - _Requirements: D1.1_
  - [x] 8.3 在 `agent/tools/` 下新增 `playwright_dm_monitor.py`
    - 实现 `poll_dm_messages(page, known_msg_ids)` 方法
    - 获取商家端消息列表，返回新增消息
    - 处理消息去重（msg_id）
    - _Requirements: D5.1_
  - [x] 8.4 在 `agent/tools/` 下新增 `playwright_dm_sender.py`
    - 实现 `send_dm(page, xhs_user_id, content)` 方法
    - 导航到私信发送页面，模拟人工输入和点击发送
    - 随机化操作轨迹和延迟
    - 检测并报告 Captcha 状态
    - _Requirements: D3.1, D3.2, D3.3, D3.7_
  - [x] 8.5 在 `agent/tools/` 下新增 `playwright_comment_replier.py`
    - 实现 `send_comment_reply(page, xhs_note_id, xhs_comment_id, reply_content)` 方法
    - 导航到笔记评论页面，找到指定评论，模拟输入并提交回复
    - 回复字数验证：15~80 汉字
    - _Requirements: D1.4, D3.4_
  - [x] 8.6 更新 `agent/tools/ocr_tool.py`
    - 实现 PaddleOCR 本地调用（`ocr_image`）
    - 输入：图片 URL（远程下载）或本地路径
    - 输出：`(text: str, confidence: float)`
    - 置信度 < 0.5 时返回空字符串，触发人工审核
    - _Requirements: D1.2_
  - [x] 8.7 更新 `agent/tools/risk_scan.py`
    - 封装对 `RiskService.scan_output()` 的调用
    - 返回统一 `RiskScanResult`（passed, hit_keywords, risk_level, suggestion）
    - _Requirements: D3.5, E1.2_

- [x] 9. 实现令牌桶 + 随机抖动调度器
  - [x] 9.1 在 `backend/app/services/` 下新增 `note_polling_scheduler.py`
    - 实现 `NotePollingScheduler` 类
    - 令牌桶算法控制每账号每批次笔记处理量（capacity=10, refill_rate=1/s）
    - `get_jitter_delay()`：基础间隔 ±50% 随机抖动
    - `get_batch_start_delay()`：批次开始前 5~25 秒随机等待
    - 每批笔记处理之间注入 3~15 秒随机延迟
    - Redis 存储令牌桶状态（`rpa:token_bucket:{account_id}`）
    - _Requirements: D1.1, 防检测设计_
  - [x] 9.2 在 `worker/tasks/` 下新增 `comment_probe_task.py`
    - Celery Beat 定时触发（每 10 秒）
    - 调用 `InteractionService.check_monitored_notes()`
    - _Requirements: D1.1_
  - [x] 9.3 在 `worker/tasks/` 下新增 `dm_probe_task.py`
    - Celery Beat 定时触发（每 5 秒）
    - 调用 `InteractionService.poll_dm_messages()`
    - _Requirements: D5.1_
  - [x] 9.4 在 `worker/tasks/` 下新增 `dm_pending_task.py`
    - 处理 Redis `session:pending:{conversation_id}` 队列中的待发送消息
    - 连接恢复后 30 秒内补发回复
    - _Requirements: D5.5_
  - [x] 9.5 在 `worker/tasks/` 下新增 `captcha_recovery_task.py`
    - 检测账号的 Captcha 阻断标记是否已清除（商家人工处理后）
    - 清除后恢复账号自动化操作
    - _Requirements: D1.3_
  - [x] 9.6 在 `worker/beat_schedule.py` 中注册定时任务
    - `comment_probe_task`：每 10 秒执行
    - `dm_probe_task`：每 5 秒执行
    - `dm_pending_task`：每 10 秒执行
    - `captcha_recovery_task`：每 5 分钟执行

- [x] 10. 集成模块 B（知识库）和模块 E（风控）（框架已就绪，真值待模块 B/E 提供）
  - [x] 10.1 在 `InteractionService` 和 `CustomerServiceGraph` 中接入 RAG 检索
    - 调用 `hybrid_search()`，模块 B 未实现时降级返回空列表
    - 传入 `account_id` 和 `intent` 作为检索参数
    - _Requirements: D3.1, D3.2, D3.4, D3.5_
  - [x] 10.2 在 `InteractionService` 中接入风控扫描
    - `send_dm_via_rpa` 和 `reply_comment_via_rpa` 中调用 `scan_content()`
    - 扫描通过后才执行发送
    - _Requirements: D3.5, E1.2_
  - [x] 10.3 在 `InteractionService` 中接入频率控制
    - `send_dm_via_rpa` 中调用 `risk_service.check_and_reserve_quota()`
    - 频率超限时阻止发送并触发告警
    - _Requirements: D3.7, E2.1, E2.2_
  - [x] 10.4 在 `InteractionService` 中接入账号状态感知
    - RPA 操作前检查 `accounts.status`
    - 拒绝向 `auth_expired` / `banned` / `suspended` 账号执行操作
    - _Requirements: D1.1_

- [x] 11. 编写属性测试和单元测试（已实现）
  - [x] 11.1 属性测试：评论去重私信触发（Property 10, Hypothesis 50 examples）
  - [x] 11.2 属性测试：实时客服端到端延迟（Property 11, Mock 图节点 + LLM 延迟）
  - [x] 11.3 属性测试：会话上下文窗口大小（Property 12, 10轮截断/TTL过期）
  - [x] 11.4 InteractionService 单元测试（CRUD/模式切换/Captcha/在线时段/去重）
  - [x] 11.5 API 路由层单元测试（参数校验/响应格式/字数/HITL上限）
  - [x] 11.6 集成测试（4条完整链路，Mock Playwright + LLM）
  - 测试文件：`backend/tests/test_interaction_properties.py`, `test_interaction_service.py`, `test_interaction_api.py`, `test_interaction_integration.py`

- [ ] 12. Final checkpoint — 确保模块 D 可端到端接入
  - 确保 Agent 图正确调用 RAG 检索和风控扫描
  - 确保令牌桶调度和 humanized delay 正确注入
  - 确保 Captcha 检测和账号状态检查生效
  - Task 11.2（Property 11 E2E 延迟属性测试）：需要 Mock LLM 调用延迟，待实现
  - 确保所有属性测试（Hypothesis）通过，每个属性至少 100 次迭代
  - 确保所有单元测试与集成测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 模块 D 是核心大脑，优先保证意图分类准确性和实时客服延迟约束
- Playwright 页面元素选择器（CSS Selector）为占位符，需在实现阶段替换为真实抓取的选择器
- App/短信双渠道告警复用 `backend/app/core/notifications.py`
- RAG 检索复用 `agent/tools/rag_retrieval.py`，风控扫描复用 `agent/tools/risk_scan.py`
- 令牌桶调度优先 Redis 实现，避免数据库压力
- Captcha 恢复依赖商家人工处理，无自动破解方案
