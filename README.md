# 小红书营销自动化 Agent

面向小红书商家的营销自动化智能体平台。

## 快速开始

### 前置依赖

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+

### 1. 启动本地基础设施

```bash
cp infra/.env.example .env
docker-compose -f infra/docker-compose.yml up -d
```

服务启动后：
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- RabbitMQ: `localhost:5672`（管理界面：http://localhost:15672）
- Qdrant: `localhost:6333`（API 文档：http://localhost:6333/dashboard）

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API 文档：http://localhost:8000/docs

### 3. 启动 Celery Worker

```bash
cd worker
celery -A celery_app worker --loglevel=info
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端：http://localhost:3000

## 项目结构

```
├── backend/      # FastAPI 后端
├── frontend/     # Next.js 前端
├── agent/        # LangGraph Agent 核心
├── worker/       # Celery 异步任务
└── infra/        # 基础设施配置
```

详细架构设计见 `.kiro/specs/architecture.md`。

## 开发规范

见 `.kiro/steering/` 目录下各规范文件。
