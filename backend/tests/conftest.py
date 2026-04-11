"""共享 test fixtures — PostgreSQL 异步会话。

使用 NullPool 避免连接跨 event loop 问题。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import Base
from app.models.account import Account, AccountPersona, ProxyConfig  # noqa: F401


def _make_engine():
    """每次调用创建新 engine（NullPool 不缓存连接）。"""
    return create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    """每个测试前确保表存在并清空数据。"""
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        await conn.execute(text("DELETE FROM proxy_configs"))
        await conn.execute(text("DELETE FROM account_personas"))
        await conn.execute(text("DELETE FROM accounts"))
        await conn.commit()
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """提供一个干净的数据库会话。"""
    engine = _make_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI 异步测试客户端，注入测试 db session。"""
    from app.db.session import get_db
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()
