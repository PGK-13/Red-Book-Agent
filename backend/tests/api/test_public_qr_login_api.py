"""公开扫码登录路由层单元测试。

验证：
- 两个公开端点无需 Authorization header 即可正常访问（需求 1.2, 2.2）
- 响应格式符合 BaseResponse 包装（需求 4.1, 4.2, 4.3）
- Mock account_service 的公开扫码函数，隔离路由层逻辑
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestPublicQrLoginStartRoute:
    """POST /api/v1/accounts/qr-login/start 路由测试。"""

    @pytest.mark.asyncio
    async def test_start_no_auth_required(self, client: AsyncClient) -> None:
        """无 Authorization header 时请求正常处理（需求 1.2, 5.1）。"""
        mock_result = {
            "session_id": str(uuid4()),
            "qr_image_base64": "iVBORw0KGgoAAAANSUhEUg==",
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_start_base_response_format(self, client: AsyncClient) -> None:
        """响应符合 BaseResponse{code, message, data} 格式（需求 4.1, 4.2）。"""
        session_id = str(uuid4())
        mock_result = {
            "session_id": session_id,
            "qr_image_base64": "iVBORw0KGgoAAAANSUhEUg==",
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        body = resp.json()
        assert body["code"] == 0
        assert body["message"] == "success"
        assert "data" in body

    @pytest.mark.asyncio
    async def test_start_data_fields(self, client: AsyncClient) -> None:
        """data 包含 session_id 和 qr_image_base64（需求 4.2）。"""
        session_id = str(uuid4())
        qr_base64 = "iVBORw0KGgoAAAANSUhEUg=="
        mock_result = {
            "session_id": session_id,
            "qr_image_base64": qr_base64,
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        data = resp.json()["data"]
        assert data["session_id"] == session_id
        assert data["qr_image_base64"] == qr_base64

    @pytest.mark.asyncio
    async def test_start_service_503_propagates(self, client: AsyncClient) -> None:
        """Service 层抛出 503 时路由正确传播（需求 1.4）。"""
        from fastapi import HTTPException, status

        with patch(
            "app.api.v1.qr_login.account_service.public_start_qr_login",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Playwright 未安装",
            ),
        ):
            resp = await client.post(
                "/api/v1/accounts/qr-login/start",
                json={},
            )

        assert resp.status_code == 503


class TestPublicQrLoginStatusRoute:
    """GET /api/v1/accounts/qr-login/status 路由测试。"""

    @pytest.mark.asyncio
    async def test_status_no_auth_required(self, client: AsyncClient) -> None:
        """无 Authorization header 时请求正常处理（需求 2.2, 5.1）。"""
        mock_result = {"status": "waiting", "token": None, "user": None}
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": str(uuid4())},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_status_missing_session_id_returns_422(
        self, client: AsyncClient
    ) -> None:
        """缺少 session_id 参数应返回 422。"""
        resp = await client.get("/api/v1/accounts/qr-login/status")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_status_waiting_base_response_format(
        self, client: AsyncClient
    ) -> None:
        """waiting 状态响应符合 BaseResponse 格式（需求 4.1, 4.3）。"""
        mock_result = {"status": "waiting", "token": None, "user": None}
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": "test-session"},
            )

        body = resp.json()
        assert body["code"] == 0
        assert body["message"] == "success"
        assert "data" in body
        assert body["data"]["status"] == "waiting"
        assert body["data"]["token"] is None
        assert body["data"]["user"] is None

    @pytest.mark.asyncio
    async def test_status_success_with_token_and_user(
        self, client: AsyncClient
    ) -> None:
        """success 状态包含 token 和 user（需求 2.3, 4.3）。"""
        mock_result = {
            "status": "success",
            "token": "eyJhbGciOiJIUzI1NiJ9.test.sig",
            "user": {
                "nickname": "测试商家",
                "avatar": "https://example.com/avatar.png",
                "xhs_user_id": "xhs_123",
            },
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": "test-session"},
            )

        data = resp.json()["data"]
        assert data["status"] == "success"
        assert data["token"] == "eyJhbGciOiJIUzI1NiJ9.test.sig"
        assert data["user"]["nickname"] == "测试商家"
        assert data["user"]["avatar"] == "https://example.com/avatar.png"
        assert data["user"]["xhs_user_id"] == "xhs_123"

    @pytest.mark.asyncio
    async def test_status_expired_response(self, client: AsyncClient) -> None:
        """expired 状态 token 和 user 为 null（需求 2.4, 2.5）。"""
        mock_result = {"status": "expired", "token": None, "user": None}
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": "expired-session"},
            )

        data = resp.json()["data"]
        assert data["status"] == "expired"
        assert data["token"] is None
        assert data["user"] is None

    @pytest.mark.asyncio
    async def test_status_success_user_avatar_null(
        self, client: AsyncClient
    ) -> None:
        """success 状态 user.avatar 可为 null（需求 3.1）。"""
        mock_result = {
            "status": "success",
            "token": "eyJhbGciOiJIUzI1NiJ9.test.sig",
            "user": {
                "nickname": "无头像商家",
                "avatar": None,
                "xhs_user_id": "xhs_456",
            },
        }
        with patch(
            "app.api.v1.qr_login.account_service.public_poll_qr_login_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/accounts/qr-login/status",
                params={"session_id": "test-session"},
            )

        data = resp.json()["data"]
        assert data["status"] == "success"
        assert data["user"]["avatar"] is None
        assert data["user"]["nickname"] == "无头像商家"
