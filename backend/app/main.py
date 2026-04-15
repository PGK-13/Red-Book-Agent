from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    accounts,
    analytics,
    content,
    interaction,
    knowledge,
    qr_login,
    risk,
)
from app.config import settings

app = FastAPI(
    title="小红书营销自动化 Agent",
    version="0.1.0",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（公开路由必须在 accounts.router 之前，避免路径被 /{account_id} 拦截）
app.include_router(qr_login.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(interaction.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
