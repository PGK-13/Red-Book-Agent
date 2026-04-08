---
inclusion: always
---

# Architecture and Layering Rules

## Architectural Style

分层架构（Layered Architecture）+ 六边形思想，以 Service 层为核心编排器。

```
API 路由层（FastAPI Routers）
        ↓  参数校验 + 响应封装
Service 层（Business Logic Orchestrator）
        ↓  领域操作
Repository / ORM 层（SQLAlchemy Models）
        ↓
PostgreSQL + Qdrant + Redis
```

异步边界（独立生命周期）：
```
Celery Worker（RabbitMQ 驱动）
        ↓  任务消费
Service 层（复用同一套业务逻辑）
```

## Component Responsibilities

### API 路由层（`backend/app/api/v1/`）
- 只做：请求参数校验（Pydantic Schema）、调用 Service 层、格式化响应
- 禁止：直接操作数据库、直接调用 LangGraph/LLM、包含任何业务判断逻辑
- 禁止：在路由层做权限以外的条件分支

### Service 层（`backend/app/services/`）
- 这是唯一的业务逻辑编排层
- 负责：跨模块协调（如 D 调用 B 检索、D 调用 E 风控）、事务边界、错误处理、任务分发
- 所有查询必须携带 `merchant_id` 过滤，确保商家数据隔离
- 调用 LangGraph Agent、Celery 任务、外部 API 均在此层发起

### Agent 层（`agent/`）
- LangGraph 图和 LangChain Tools 是纯粹的 AI 编排层
- 不直接操作数据库，通过 Service 层提供的工具函数访问数据
- 工具函数（`agent/tools/`）是 Service 层能力的薄封装，不包含独立业务逻辑

### Worker 层（`worker/tasks/`）
- Celery Task 是异步执行入口，等同于路由层的地位
- 禁止在 Task 中写业务逻辑，复用 Service 层函数
- 所有 Task 必须配置幂等性保障（`task_id` 去重 或 数据库唯一约束）

### 模型层（`backend/app/models/`）
- 纯 SQLAlchemy ORM 定义，不包含业务逻辑
- 复杂查询封装为 Repository 函数，不散落在 Service 层

## Module Communication Rules

- **同步调用**：Service 层直接 import 其他 Service 函数（如 `RiskService.scan()`）
- **异步任务**：通过 Celery `delay()` / `apply_async()` 发布，不直接调用 Worker 函数
- **实时推送**：通过 Redis Pub/Sub，不在请求链路中阻塞等待
- **禁止循环依赖**：模块依赖方向为 A→B→E（单向），禁止 B 反向依赖 D

## Non-Negotiable Layering Rules

1. 路由层不写业务逻辑，Service 层不写 SQL，模型层不写业务逻辑。
2. LangGraph Agent 不直接访问数据库，必须通过 Tool 函数间接访问。
3. Celery Task 不写业务逻辑，复用 Service 层。
4. 风控扫描（E 模块）必须在任何出站操作（发布笔记、发送回复、发送私信）前同步完成，不得异步化。
5. 跨模块调用通过 Service 层函数，禁止跨层直接调用（如路由层直接调用 ORM）。
