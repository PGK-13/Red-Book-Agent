# 小红书营销自动化 Agent

面向小红书商家的营销自动化智能体平台。

## 快速开始

### 前置依赖

- Docker / Docker Compose
- Python 3.12+
- Node.js 20+

### Phase 1 容器化启动

Phase 1 已将数据库迁移纳入 Docker 启动流程。首次启动或删除数据库卷后，推荐直接使用：

```bash
cp infra/.env.example .env
docker compose -f infra/docker-compose.yml up --build
```

启动顺序如下：

1. PostgreSQL / Redis / RabbitMQ / Qdrant 启动并通过健康检查
2. `migrate` 服务自动执行 `python -m app.db.migrations_runner upgrade head`
3. `backend` 与 `worker` 在迁移成功后启动

启动后可访问：

- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- RabbitMQ: `localhost:5672`
- RabbitMQ 管理界面: `http://localhost:15672`
- Qdrant: `http://localhost:6333`

### 空库验收

Phase 1 的空库验收脚本已经补齐。删除数据库卷后，可按下面流程验证模块 E 的关键落库链路：

```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up --build -d
docker compose -f infra/docker-compose.yml --profile verify run --rm risk-bootstrap-check
```

验收脚本会在空库环境中：

- 通过 Alembic 初始化数据库
- 写入测试账号与风险词
- 执行一次模块 E 入站扫描
- 校验 `operation_logs` 与 `alerts` 已成功落库

更详细的操作说明见 [docs/phase1-empty-db-acceptance.md](docs/phase1-empty-db-acceptance.md)。

### 本地后端开发

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.db.migrations_runner upgrade head
uvicorn app.main:app --reload
```

### 本地 Worker

```bash
cd backend
python -m app.db.migrations_runner upgrade head
celery -A worker.celery_app:app worker --loglevel=info
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 测试

模块 E 的 Phase 1 新增了一条只依赖 Alembic 的测试链路，用于阻止 ORM / 迁移 / 服务写入再次漂移：

```bash
docker compose -f infra/docker-compose.test.yml up -d
cd backend
pytest tests/test_risk_alembic_path.py
```

## 项目结构

```text
backend/   FastAPI 后端
frontend/  Next.js 前端
agent/     LangGraph Agent 核心
worker/    Celery 异步任务
infra/     基础设施与容器编排
docs/      任务与验收文档
```
