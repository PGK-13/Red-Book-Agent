# Implementation Plan: 模块 E — 风控与合规保障

## Overview

基于现有项目骨架（`risk.py` / `risk_service.py` / `api/v1/risk.py` 已有 stub），按分层架构逐步实现模块 E：规则模型与配置 → 风控 Schema → Service 编排 → API 路由 → 与模块 C/D 的调用集成 → 属性测试与单元测试。重点先打通统一风控入口，再补齐频率、去重、告警等横切能力。

## Tasks

- [ ] 1. 实现 SQLAlchemy ORM 模型（RiskKeyword、AccountRiskConfig、ReplyHistory）
  - [ ] 1.1 在 `backend/app/models/risk.py` 中实现 `RiskKeyword` ORM 模型
    - 替换现有 TODO stub
    - 字段：`id(UUID PK)`、`merchant_id(UUID, nullable, indexed)`、`keyword(VARCHAR 128)`、`category(Enum: platform_banned/contraband/exaggeration/competitor/custom)`、`replacement(VARCHAR 128, nullable)`、`match_mode(Enum: exact/fuzzy)`、`severity(Enum: warn/block)`、`is_active(Boolean, default=True)`、`created_at(TIMESTAMPTZ, server_default=now)`
    - 添加 `UniqueConstraint("merchant_id", "keyword", "category")`
    - _Requirements: E1.1, E3.3, E3.4_
  - [ ] 1.2 在 `backend/app/models/risk.py` 中新增 `AccountRiskConfig` ORM 模型
    - 字段：`account_id(UUID FK → accounts.id, unique)`、`rest_windows(TEXT[])`、`comment_reply_limit_per_hour(Integer, default=20)`、`dm_send_limit_per_hour(Integer, default=50)`、`note_publish_limit_per_day(Integer, default=3)`、`dedup_similarity_threshold(Float, default=0.85)`、`competitor_alert_threshold_per_hour(Integer, default=10)`、`updated_at(TIMESTAMPTZ)`
    - _Requirements: E2.1, E2.4, E3.2, E3.5_
  - [ ] 1.3 在 `backend/app/models/risk.py` 中新增 `ReplyHistory` ORM 模型
    - 字段：`id(UUID PK)`、`account_id(UUID FK → accounts.id, indexed)`、`content(Text)`、`normalized_content(Text)`、`similarity_hash(VARCHAR 64, nullable)`、`source_type(Enum: comment_reply/dm_send)`、`source_record_id(UUID, nullable)`、`created_at(TIMESTAMPTZ, indexed)`
    - 用于保存最近回复历史并支持最近 100 条相似度比对
    - _Requirements: E3.1, E3.2_
  - [ ] 1.4 创建 Alembic 迁移脚本生成 `risk_keywords`、`account_risk_configs`、`reply_histories`
- [ ] 1.4 在 `backend/app/models/risk.py` 中新增 `OperationLog` 和 `Alert` ORM 模型
    - OperationLog：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK → accounts.id)`、`operation_type(Enum: note_publish/comment_reply/dm_send/comment_inbound/dm_inbound)`、`status(Enum: success/blocked/rewrite_required/manual_review)`、`risk_decision(VARCHAR 32)`、`violations(TEXT[])`、`content_preview(Text, nullable)`、`created_at(TIMESTAMPTZ)`
    - Alert：`id(UUID PK)`、`merchant_id(UUID, indexed)`、`account_id(UUID FK → accounts.id, nullable)`、`module(VARCHAR 32, default=risk)`、`alert_type(VARCHAR 64)`、`message(Text)`、`severity(Enum: info/warning/critical)`、`is_resolved(Boolean, default=False)`、`created_at(TIMESTAMPTZ)`
    - 添加复合索引：`operation_logs(account_id, operation_type, created_at DESC)`、`alerts(merchant_id, module, created_at DESC)`
    - _Requirements: E1.3, E2.2, E3.5_
  - [ ] 1.5 创建 Alembic 迁移脚本生成 `risk_keywords`、`account_risk_configs`、`reply_histories`、`operation_logs`、`alerts`
    - 包含所需索引和唯一约束
    - _Requirements: E1.1, E2.4, E3.3_

- [ ] 2. 实现风控 Pydantic Schema
  - [ ] 2.1 创建 `backend/app/schemas/risk.py`
    - 定义 `RiskKeywordCreateRequest`、`RiskKeywordUpdateRequest`
    - 定义 `RiskScanRequest`、`RiskHitResponse`、`RiskScanResponse`
    - 定义 `AccountRiskScheduleRequest`、`AccountRiskQuotaResponse`、`RiskEventResponse`
    - `scene` 枚举覆盖：`note_publish`、`comment_reply`、`dm_send`、`comment_inbound`、`dm_inbound`
    - _Requirements: E1.2, E2.4, E3.3_

- [ ] 3. 实现 RiskService 核心业务逻辑
  - [ ] 3.1 在 `backend/app/services/risk_service.py` 中实现关键词配置管理方法
    - `list_keywords(merchant_id, category, is_active, db)`
    - `create_keyword(merchant_id, data, db)`
    - `update_keyword(merchant_id, keyword_id, data, db)`
    - `delete_keyword(merchant_id, keyword_id, db)`
    - 查询同时加载系统级关键词（`merchant_id IS NULL`）和商家级关键词
    - _Requirements: E1.1, E3.3_
  - [ ] 3.2 实现敏感词扫描方法
    - `scan_sensitive_keywords(content, merchant_id, db)` 返回命中词、位置、类别、替换建议、严重级别
    - 同时支持系统词库与商家自定义词库
    - 输出扫描报告，目标耗时 ≤ 1 秒
    - _Requirements: E1.1, E1.2_
  - [ ] 3.3 实现入站内容扫描方法
    - `scan_input(merchant_id, account_id, scene, content, db)`
    - 对评论、私信入站内容执行敏感词/竞品检测
    - 命中时写入日志，但不阻塞正常回复流程
    - _Requirements: E1.3_
  - [ ] 3.4 实现出站内容统一扫描方法
    - `scan_output(merchant_id, account_id, scene, content, db)`
    - 顺序串联：休息时段检查 → 频率检查 → 敏感词检测 → 竞品检测 → 相似度检测
    - 返回统一决策：`passed` / `rewrite_required` / `blocked` / `manual_review`
    - _Requirements: E1.2, E2.1, E2.2, E2.4, E3.2, E3.4_
  - [ ] 3.5 实现频率控制与配额占用
    - 复用或扩展 `backend/app/core/rate_limiter.py`
    - `check_and_reserve_quota(account_id, action, db)`：评论回复每小时 ≤ 20，私信每小时 ≤ 50，笔记每天 ≤ 3
    - 命中阈值后暂停账号自动化操作并触发告警
    - _Requirements: E2.1, E2.2_
  - [ ] 3.6 实现休息时段配置与检查
    - `update_account_schedule(merchant_id, account_id, data, db)`
    - `is_in_rest_window(account_id, now, db)`
    - 支持类似 `00:00-08:00` 的时间段配置
    - _Requirements: E2.4_
  - [ ] 3.7 实现人工操作间隔生成
    - `apply_humanized_delay(account_id, action)` 返回 3 到 15 秒随机等待值
    - 将等待值传递给上游执行器，而不是在风控服务中长时间阻塞
    - _Requirements: E2.3_
  - [ ] 3.8 实现内容变体注入与相似度检测
    - `inject_variants(content)`：同义词替换、语序微调、语气词增减
    - `detect_similarity(account_id, candidate, db)`：与最近 100 条历史回复比对，阈值 `0.85`
- 注意：变体注入（同义词替换、语序微调）属于模块 C 内容生成引擎的职责，E 模块只负责检测
    - _Requirements: E3.1, E3.2_
  - [ ] 3.9 实现竞品避嫌检测
    - 对 `category=competitor` 的关键词执行全词匹配和编辑距离 ≤ 1 的模糊匹配
    - 统计同账号 1 小时内竞品命中次数，超过 10 次触发告警
    - _Requirements: E3.3, E3.4, E3.5_
  - [ ] 3.10 实现回复历史落库与缓存
    - `persist_reply_history(account_id, content, source_type, source_record_id, db)`
    - 仅保留最近 100 条高频读取数据在 Redis 中的摘要缓存，完整内容落 PostgreSQL
    - _Requirements: E3.2_
  - [ ] 3.11 实现风控事件日志与告警触发
    - 复用 `operation_logs` 和 `alerts`
    - 记录敏感词命中、频率超限、休息时段阻断、竞品高频命中、自动改写失败等事件
    - 告警统一通过 `backend/app/core/notifications.py` / `worker/tasks/alert_task.py`
    - _Requirements: E1.3, E2.2, E3.5_

- [ ] 4. Checkpoint — 确保 RiskService 编排完整
  - 确保所有 Service 方法按 `merchant_id` 做数据隔离
  - 确保 `scan_output()` 只返回统一决策对象，不泄露底层实现细节给调用方
  - 确保 Redis 计数与数据库日志职责清晰，不重复存储
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. 实现 API 路由层
  - [ ] 5.1 在 `backend/app/api/v1/risk.py` 中实现风控配置与调试路由
    - 替换现有 TODO stub
    - GET `/risk/keywords` → 调用 `RiskService.list_keywords`
    - POST `/risk/keywords` → 调用 `RiskService.create_keyword`
    - PUT `/risk/keywords/{id}` → 调用 `RiskService.update_keyword`
    - DELETE `/risk/keywords/{id}` → 调用 `RiskService.delete_keyword`
    - POST `/risk/scan` → 调用 `RiskService.scan_output` 或 `scan_input`
    - GET `/risk/accounts/{id}/quota` → 调用 `RiskService.get_account_quota`
    - PUT `/risk/accounts/{id}/schedule` → 调用 `RiskService.update_account_schedule`
    - GET `/risk/accounts/{id}/events` → 查询近期风控事件
    - 所有路由注入 `CurrentMerchantId` 与 `DbSession`
    - _Requirements: E1.1, E1.2, E2.4, E3.3_

- [ ] 6. 集成模块 C / D 的风控调用链
  - [ ] 6.1 在 `backend/app/services/content_service.py` 中接入出站风控
- [ ]* 6. 集成模块 C / D 的风控调用链（建议在 C/D 模块各自实现时接入，此处仅作参考）
  - [ ]* 6.1 在 `backend/app/services/content_service.py` 中接入出站风控
    - 命中可改写问题时驱动内容引擎局部重写，最多 3 次
    - 连续失败后将 `content_drafts.risk_status` 置为 `manual_review`
    - _Requirements: E1.4, E2.1, E2.4_
  - [ ] 6.2 在 `backend/app/services/interaction_service.py` 中接入评论/私信风控
    - 对入站评论、私信先调用 `scan_input`
    - 对自动回复、自动私信发送前调用 `scan_output`
    - 回复发送成功后写入 `ReplyHistory`
    - _Requirements: E1.3, E2.1, E3.1, E3.2_
  - [ ]* 6.3 在相关 Agent / Tool 层接入变体注入与等待节奏
    - `agent/tools/comment_reply.py`
    - `agent/tools/dm_sender.py`
    - `agent/tools/risk_scan.py`
    - 在执行器层消费 `apply_humanized_delay()` 的返回值
    - _Requirements: E2.3, E3.1_

- [ ] 7. 实现异步与告警联动
  - [ ] 7.1 扩展 `worker/tasks/alert_task.py`
    - 支持风控限流、竞品高频、改写失败、账号休息期违规调度等告警类型
    - _Requirements: E2.2, E3.5_
  - [ ] 7.2 如有必要，在 `worker/beat_schedule.py` 中补充风控相关定时任务
    - 如配额快照清理、风险缓存清理等轻量维护任务
    - _Requirements: E2.1, E3.2_

- [ ] 8. 编写属性测试和单元测试
  - [ ]* 8.1 编写属性测试：敏感词扫描覆盖与耗时约束
    - **Property 13: Outbound content must be scanned before send**
    - **Validates: Requirements E1.2**
    - 使用 Hypothesis 生成随机文本与关键词集合，验证扫描结果覆盖所有命中词，且实现中保留耗时断言接口
    - 在 `backend/tests/test_risk_properties.py` 中实现
  - [ ]* 8.2 编写属性测试：频率上限阻断
    - **Property 14: Operation rate caps are never exceeded**
    - **Validates: Requirements E2.1, E2.2**
    - 使用 Hypothesis 生成随机操作序列，验证超过阈值后返回 `blocked`
    - 在 `backend/tests/test_risk_properties.py` 中实现
  - [ ]* 8.3 编写属性测试：回复内容去重
    - **Property 15: Reply similarity against latest 100 messages stays below 0.85**
    - **Validates: Requirements E3.1, E3.2**
    - 使用 Hypothesis 生成高相似候选文本与历史回复集，验证系统触发改写而非直接发送
    - 在 `backend/tests/test_risk_properties.py` 中实现
  - [ ]* 8.4 编写 RiskService 单元测试
    - 测试系统词库 + 商家词库合并加载
    - 测试休息时段阻断
    - 测试评论/私信/笔记三类配额限制
    - 测试竞品模糊匹配（编辑距离 1）
    - 测试竞品高频命中触发告警
    - 在 `backend/tests/test_risk_service.py` 中实现
    - _Requirements: E1.1, E2.1, E2.4, E3.4, E3.5_
  - [ ]* 8.5 编写 API 路由层单元测试
    - 测试关键词 CRUD 参数校验
    - 测试 `/risk/scan` 对不同 `scene` 的请求校验
    - 测试响应格式符合 `BaseResponse` 规范
    - 在 `backend/tests/test_risk_api.py` 中实现
    - _Requirements: E1.1, E1.2_
  - [ ]* 8.6 编写集成测试
    - 测试内容生成 → 风控扫描 → 改写重试 → 人工审核降级链路
    - 测试评论入站 → 出站回复 → 回复历史写入链路
    - _Requirements: E1.4, E3.2_

- [ ] 9. Final checkpoint — 确保模块 E 可端到端接入
  - 确保模块 C、D 都通过统一 `RiskService.scan_output()` 接入，而不是各自分散实现风控
  - 确保所有属性测试（Hypothesis）通过，每个属性至少 100 次迭代
  - 确保所有单元测试与集成测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 模块 E 是横切模块，优先保证统一入口和一致决策，再逐步增强算法细节
- 高频计数优先走 Redis；规则配置、审核留痕、历史回复优先走 PostgreSQL
- 相似度算法可先用简单可解释方案落地，后续再替换为更强实现
- 若仓库已有 `backend/app/core/rate_limiter.py`，优先复用而不是重复造轮子
