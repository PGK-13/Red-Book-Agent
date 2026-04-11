"""路由注册顺序与隔离验证测试。

属性 6: 路由隔离 — 公开路由不要求认证
验证: 需求 5.1, 5.2 — 公开路由无需 JWT 即可访问，已认证路由仍需 JWT

使用真实的 main.app 实例（而非独立构建的 FastAPI），
确保 main.py 中的路由注册顺序正确：
  qr_login.router 在 accounts.router 之前，
  /api/v1/accounts/qr-login/start 优先于 /{account_id}/qr-login/start 匹配。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def real_app_client() -> AsyncGenerator[AsyncClient, None]:
    """基于 main.app 的测试客户端，覆盖 DB 依赖避免连接数据库。"""
    from app.db.session import get_db
    from app.main import app

    async def _no_db():
        yield None  # pragma: no cover

    app.dependency_overrides[get_db] = _no_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()


class TestRouteIsolation:
    """验证公开路由与已认证路由的隔离性（属性 6）。"""

    @pytest.mark.asyncio
    async def test_public_start_no_jwt_returns_200(
        self, real_app_client: AsyncClient
    ) -> None:
        """公开 POST /accounts/qr-login/start 无需 JWT 即可访问（需求 5.1）。"""
        mock_result = {
            "session_id": str(uuid4()),
            "qr_image_base64": "iVBORw0KGgoAAAANSUhEUg==",
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await real_app_client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["session_id"] == mock_result["session_id"]

    @pytest.mark.asyncio
    async def test_public_status_no_jwt_returns_200(
        self, real_app_client: AsyncClient
    ) -> None:
        """公开 GET /accounts/qr-login/status 无需 JWT 即可访问（需求 5.1）。"""
        mock_result = {"status": "waiting", "token": None, "user": None}
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await real_app_client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": "test-session"},
            )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "waiting"

    @pytest.mark.asyncio
    async def test_authenticated_qr_start_requires_jwt(
        self, real_app_client: AsyncClient
    ) -> None:
        """已认证 POST /{account_id}/qr-login/start 无 JWT 返回 403（需求 5.2）。"""
        account_id = str(uuid4())
        resp = await real_app_client.post(
            f"/api/v1/accounts/{account_id}/qr-login/start",
        )

        # HTTPBearer 在缺少 Authorization header 时返回 403
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_authenticated_qr_status_requires_jwt(
        self, real_app_client: AsyncClient
    ) -> None:
        """已认证 GET /{account_id}/qr-login/status 无 JWT 返回 403（需求 5.2）。"""
        account_id = str(uuid4())
        resp = await real_app_client.get(
            f"/api/v1/accounts/{account_id}/qr-login/status",
            params={"session_id": "test-session"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_authenticated_list_accounts_requires_jwt(
        self, real_app_client: AsyncClient
    ) -> None:
        """GET /accounts（列表）无 JWT 返回 403，确认认证路由未受影响（需求 5.2）。"""
        resp = await real_app_client.get("/api/v1/accounts")

        assert resp.status_code == 403


class TestRouteRegistrationOrder:
    """验证 main.py 中路由注册顺序正确（需求 5.3, 5.4）。"""

    @pytest.mark.asyncio
    async def test_public_route_matches_before_path_param(
        self, real_app_client: AsyncClient
    ) -> None:
        """公开路由 /accounts/qr-login/start 优先于 /{account_id}/qr-login/start。

        如果注册顺序错误，'qr-login' 会被当作 account_id 路径参数，
        导致进入已认证路由并返回 403。
        """
        mock_result = {
            "session_id": str(uuid4()),
            "qr_image_base64": "iVBORw0KGgoAAAANSUhEUg==",
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await real_app_client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        # 如果路由注册顺序错误，这里会返回 403（被 accounts.router 拦截）
        assert resp.status_code == 200, (
            "路由注册顺序错误：/accounts/qr-login/start 被 /{account_id} 路由拦截，"
            "请确保 qr_login.router 在 accounts.router 之前注册"
        )

    @pytest.mark.asyncio
    async def test_qr_login_router_registered_in_main(self) -> None:
        """验证 qr_login.router 已在 main.app 中注册。"""
        from app.main import app

        qr_login_paths = [
            route.path
            for route in app.routes
            if hasattr(route, "path")
            and "qr-login" in route.path
            and "{account_id}" not in route.path
        ]

        assert "/api/v1/accounts/qr-login/start" in qr_login_paths
        assert "/api/v1/accounts/qr-login/status" in qr_login_paths
