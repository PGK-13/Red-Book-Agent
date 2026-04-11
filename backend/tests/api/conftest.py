"""API 路由测试 conftest — 不依赖数据库。

覆盖根 conftest 的 autouse _setup_db fixture，
使公开路由测试无需 PostgreSQL 连接。

由于 task 5 尚未将 qr_login.router 注册到 main.py，
此处构建一个独立的 FastAPI app 实例，确保路由注册顺序正确
（公开路由在 accounts.router 之前，避免 {account_id} 路径参数抢先匹配）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    """覆盖根 conftest 的 _setup_db，跳过数据库初始化。"""
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """无需数据库的异步测试客户端，路由注册顺序正确。"""
    from app.api.v1 import qr_login

    app = FastAPI()
    # 公开路由必须在 accounts.router 之前注册（需求 5.4）
    app.include_router(qr_login.router, prefix="/api/v1")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
