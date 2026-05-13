"""test_llm 目录的 fixtures — 纯单元测试，不需要数据库连接。"""

from __future__ import annotations

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _setup_db() -> None:
    """覆盖全局 conftest 的 autouse _setup_db — LLM 测试不连数据库。"""
    yield
