"""Service 层单元测试专用 conftest — 不需要数据库连接。

覆盖父级 conftest 中的 autouse _setup_db fixture，
避免纯 mock 测试尝试连接 PostgreSQL。
"""

import pytest


@pytest.fixture(autouse=True)
def _setup_db():
    """覆盖父级 _setup_db，这些测试不需要数据库。"""
    yield
