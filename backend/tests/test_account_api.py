"""API 路由层单元测试 — 请求参数校验、响应格式。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import settings


def _make_auth_header(merchant_id: str) -> dict[str, str]:
    """生成带有 merchant_id 的 JWT Authorization header。"""
    token = jwt.encode(
        {"sub": merchant_id},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class TestAccountAPIValidation:
    """测试 API 请求参数校验。"""

    @pytest.mark.asyncio
    async def test_create_account_invalid_access_type(self, client: AsyncClient) -> None:
        """无效的 access_type 应返回 422。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        resp = await client.post(
            "/api/v1/accounts",
            json={
                "xhs_user_id": "xhs_001",
                "nickname": "test",
                "access_type": "invalid_type",
            },
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_account_missing_fields(self, client: AsyncClient) -> None:
        """缺少必填字段应返回 422。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        resp = await client.post(
            "/api/v1/accounts",
            json={"xhs_user_id": "xhs_001"},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_account_success(self, client: AsyncClient) -> None:
        """正常创建账号应返回 200 + BaseResponse 格式。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        resp = await client.post(
            "/api/v1/accounts",
            json={
                "xhs_user_id": "xhs_api_001",
                "nickname": "API测试",
                "access_type": "browser",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["xhs_user_id"] == "xhs_api_001"
        assert body["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent_account(self, client: AsyncClient) -> None:
        """获取不存在的账号应返回 404。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)
        fake_id = str(uuid4())

        resp = await client.get(
            f"/api/v1/accounts/{fake_id}",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_proxy_invalid_resolution(self, client: AsyncClient) -> None:
        """无效的 screen_resolution 格式应返回 422。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        # 先创建账号
        create_resp = await client.post(
            "/api/v1/accounts",
            json={
                "xhs_user_id": "xhs_proxy_val",
                "nickname": "代理校验",
                "access_type": "browser",
            },
            headers=headers,
        )
        account_id = create_resp.json()["data"]["id"]

        resp = await client.put(
            f"/api/v1/accounts/{account_id}/proxy",
            json={
                "proxy_url": "http://proxy:8080",
                "user_agent": "Mozilla/5.0",
                "screen_resolution": "invalid",
                "timezone": "Asia/Shanghai",
            },
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_no_auth_header_returns_403(self, client: AsyncClient) -> None:
        """无 Authorization header 应返回 403。"""
        resp = await client.get("/api/v1/accounts")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_jwt_returns_401(self, client: AsyncClient) -> None:
        """无效 JWT 应返回 401。"""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        resp = await client.get("/api/v1/accounts", headers=headers)
        assert resp.status_code == 401


class TestAccountAPIResponseFormat:
    """测试响应格式符合 BaseResponse / PaginatedResponse 规范。"""

    @pytest.mark.asyncio
    async def test_list_accounts_paginated_format(self, client: AsyncClient) -> None:
        """列表接口应返回 PaginatedResponse 格式。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        resp = await client.get("/api/v1/accounts", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "data" in body
        assert "items" in body["data"]
        assert "has_more" in body["data"]
        assert isinstance(body["data"]["items"], list)

    @pytest.mark.asyncio
    async def test_delete_account_response_format(self, client: AsyncClient) -> None:
        """删除接口应返回 BaseResponse 格式。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        # 创建再删除
        create_resp = await client.post(
            "/api/v1/accounts",
            json={
                "xhs_user_id": "xhs_del_api",
                "nickname": "删除格式",
                "access_type": "browser",
            },
            headers=headers,
        )
        account_id = create_resp.json()["data"]["id"]

        resp = await client.delete(
            f"/api/v1/accounts/{account_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "message" in body

    @pytest.mark.asyncio
    async def test_status_endpoint_response_format(self, client: AsyncClient) -> None:
        """状态接口应返回 AccountStatusResponse 格式。"""
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        create_resp = await client.post(
            "/api/v1/accounts",
            json={
                "xhs_user_id": "xhs_status_api",
                "nickname": "状态格式",
                "access_type": "browser",
            },
            headers=headers,
        )
        account_id = create_resp.json()["data"]["id"]

        resp = await client.get(
            f"/api/v1/accounts/{account_id}/status",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert "status" in data
        assert "cookie_remaining_hours" in data
