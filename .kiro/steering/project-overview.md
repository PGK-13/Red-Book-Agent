---
inclusion: always
---

# Project Overview — 小红书营销自动化 Agent（Red Book Agent）

## What This Is

一个面向小红书商家的营销自动化智能体平台，覆盖账号管理、内容生产、互动回复、风控合规和数据分析五大业务域。

核心组成：
- LangGraph 驱动的 Agent 作为核心大脑（意图路由、工具调用、状态机）
- FastAPI 提供 RESTful 服务，Celery + RabbitMQ 承载异步任务
- Next.js 提供商家后台和 HITL（Human-in-the-Loop）工作台
- 全量 RAG 知识库（Qdrant 向量索引 + PostgreSQL），支持动态权重调整
- Playwright 浏览器自动化驱动小红书平台操作

## Tech Stack

- 后端框架：FastAPI（Python 3.11+，async/await）
- Agent 框架：LangGraph + LangChain
- LLM：GPT-4o（默认），接口层抽象为 `BaseLLM`，可替换 DeepSeek / Qwen
- 关系型数据库：PostgreSQL（JSONB、TEXT[]、pg_trgm）
- 向量数据库：Qdrant（混合检索：向量 + BM25 稀疏向量）
- 缓存 / Pub/Sub：Redis（频率计数、会话上下文、实时推送）
- 消息队列：Celery + RabbitMQ（任务持久化、死信队列、优先级队列）
- 浏览器自动化：Playwright（多账号上下文隔离）
- OCR：PaddleOCR（中文识别，本地部署）
- 图像生成：DALL-E API + Pillow
- 前端：Next.js App Router（SSR + React Server Components）

## Reference Documents

- `.kiro/specs/architecture.md` — 完整架构设计文档（数据模型、API 设计、关键流程、正确性属性）

## Module Boundaries

| 模块 | 职责 |
|------|------|
| A 账号服务 | OAuth 授权、Cookie 管理、代理配置、账号画像同步、状态监控 |
| B 知识库服务 | 文档解析分块、向量索引、混合检索、爆款文案权重管理、行业趋势分析 |
| C 内容生成服务 | 文案生成、封面模板渲染、发布调度、草稿管理 |
| D 互动路由服务 | 评论监听、OCR 识别、意图分类、私信触发、实时客服、人工接管 |
| E 风控服务 | 敏感词扫描、频率限制、内容去重、竞品过滤 |
| F 数据看板服务 | 转化漏斗统计、HITL 审核工作台、告警中心、数据导出 |

## Non-Negotiable Principles

1. 敏感字段必须加密存储。OAuth Token、Cookie、代理 URL 使用 `core/security.py` 加密，字段名以 `_enc` 结尾，禁止明文落库。
2. 所有密钥和 API Key 通过环境变量注入，禁止硬编码，禁止提交 `.env` 文件。
3. Provider 回调必须幂等。小红书 Webhook、第三方回调以 `xhs_comment_id` / `xhs_note_id` 等平台 ID 做去重，重复请求返回首次成功响应。
4. 风控扫描必须在任何出站内容发布前完成。笔记、评论回复、私信发送前均须通过 E 模块扫描。
5. 账号操作频率受硬性上限约束。评论回复 ≤ 20 次/小时，私信 ≤ 50 次/小时，超限自动暂停，不得绕过。
6. 私钥 / 加密材料不得落库、不得打印日志、不得通过网络传输。
7. 业务逻辑集中在 Service 层，API 路由层只做参数校验和响应封装，禁止在路由层写业务逻辑。
8. 商家数据严格按 `merchant_id` 隔离，所有 Service 层查询必须携带 `merchant_id` 过滤条件。
