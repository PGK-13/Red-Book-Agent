"""共享 test fixtures — PostgreSQL 异步会话。

使用 NullPool 避免连接跨 event loop 问题。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import inspect

import pytest
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
from app.core import rate_limiter
from app.db.migrations_runner import upgrade_database
from app.db.session import Base
from app.models.analytics import Alert, OperationLog  # noqa: F401
from app.models.account import Account, AccountPersona, ProxyConfig  # noqa: F401
from app.models.content import ContentDraft  # noqa: F401
from app.models.risk import AccountRiskConfig, ReplyHistory, RiskKeyword  # noqa: F401


def _get_test_database_url() -> str:
    return (
        settings.test_database_url
        or "postgresql+asyncpg://xhs:xhs_dev_password@127.0.0.1:55432/xhs_marketing_test"
    )


def _requires_test_db(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("requires_db") is not None or bool(
        {"db", "client"} & set(request.fixturenames)
    )


def _uses_alembic_db(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("alembic_only") is not None or "alembic_db" in set(
        request.fixturenames
    )


def _make_engine():
    """每次调用创建新 engine（NullPool 不缓存连接）。"""
    return create_async_engine(
        _get_test_database_url(),
        echo=False,
        poolclass=NullPool,
        connect_args={
            "timeout": 5,
            "command_timeout": 5,
            "server_settings": {"application_name": "pytest"},
        },
    )


async def _reset_public_schema(engine) -> None:
    enum_types = (
        "operation_log_status_enum",
        "alert_severity_enum",
        "operation_status_enum",
        "operation_type_enum",
        "reply_history_source_type_enum",
        "risk_severity_enum",
        "risk_match_mode_enum",
        "risk_keyword_category_enum",
        "account_status_enum",
        "access_type_enum",
    )

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        for enum_name in enum_types:
            await conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))


@pytest_asyncio.fixture(autouse=True)
async def _setup_db(request: pytest.FixtureRequest):
    """每个测试前确保表存在并清空数据。"""
    if not _requires_test_db(request) or _uses_alembic_db(request):
        yield
        return

    engine = _make_engine()
    try:
        await _reset_public_schema(engine)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with engine.connect() as conn:
            await conn.execute(text("DELETE FROM alerts"))
            await conn.execute(text("DELETE FROM operation_logs"))
            await conn.execute(text("DELETE FROM reply_histories"))
            await conn.execute(text("DELETE FROM account_risk_configs"))
            await conn.execute(text("DELETE FROM risk_keywords"))
            await conn.execute(text("DELETE FROM content_drafts"))
            await conn.execute(text("DELETE FROM proxy_configs"))
            await conn.execute(text("DELETE FROM account_personas"))
            await conn.execute(text("DELETE FROM accounts"))
            await conn.commit()
    except Exception as exc:
        pytest.skip(
            "Test database is unavailable; skipping DB-dependent test. Set "
            "TEST_DATABASE_URL or start the dedicated pytest PostgreSQL on "
            f"127.0.0.1:55432. Resolved URL: {_get_test_database_url()}. "
            f"Original error: {exc}"
        )
    finally:
        await engine.dispose()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_redis_client() -> AsyncGenerator[None, None]:
    async def _close_cached_client() -> None:
        client = rate_limiter._redis
        rate_limiter._redis = None
        if client is None:
            return

        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if close is None:
            return

        result = close()
        if inspect.isawaitable(result):
            await result

    await _close_cached_client()
    yield
    await _close_cached_client()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """提供一个干净的数据库会话。"""
    engine = _make_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def alembic_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a session backed by a schema created only through Alembic."""

    engine = _make_engine()
    try:
        await _reset_public_schema(engine)
        await asyncio.to_thread(upgrade_database, _get_test_database_url())
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            "Alembic-backed test database is unavailable; skipping DB-dependent test. Set "
            "TEST_DATABASE_URL or start the dedicated pytest PostgreSQL on "
            f"127.0.0.1:55432. Resolved URL: {_get_test_database_url()}. "
            f"Original error: {exc}"
        )

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


@pytest_asyncio.fixture
async def alembic_client(alembic_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async test client backed by an Alembic-initialized schema."""

    from app.db.session import get_db
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield alembic_db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()
