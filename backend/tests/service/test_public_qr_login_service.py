"""公开扫码登录 Service 层单元测试 — _create_jwt_token、public_poll_qr_login_status。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from app.config import settings
from app.services.account_service import (
    _create_jwt_token,
    public_poll_qr_login_status,
)


# ── _create_jwt_token ──


class TestCreateJwtToken:
    """测试 JWT 签发函数。"""

    def test_jwt_contains_correct_sub(self) -> None:
        """JWT sub 字段应为 xhs_user_id。"""
        token = _create_jwt_token("user_123", "昵称", "https://avatar.url")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user_123"

    def test_jwt_contains_nickname_and_avatar(self) -> None:
        """JWT 应包含 nickname 和 avatar 字段。"""
        token = _create_jwt_token("user_456", "测试昵称", "https://img.png")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["nickname"] == "测试昵称"
        assert payload["avatar"] == "https://img.png"

    def test_jwt_avatar_none(self) -> None:
        """avatar 为 None 时 JWT 中 avatar 字段也为 None。"""
        token = _create_jwt_token("user_789", "无头像", None)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["avatar"] is None

    def test_jwt_has_exp_field(self) -> None:
        """JWT 应包含 exp 过期时间字段。"""
        before = datetime.now(timezone.utc).replace(microsecond=0)
        token = _create_jwt_token("user_exp", "过期测试", None)
        after = datetime.now(timezone.utc) + timedelta(seconds=1)

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        expected_min = before + timedelta(minutes=settings.jwt_expire_minutes)
        expected_max = after + timedelta(minutes=settings.jwt_expire_minutes)
        assert expected_min <= exp <= expected_max

    def test_jwt_uses_configured_algorithm(self) -> None:
        """JWT 应使用 settings 中配置的算法签名。"""
        token = _create_jwt_token("user_alg", "算法测试", None)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == settings.jwt_algorithm


# ── public_poll_qr_login_status ──


class TestPublicPollQrLoginStatus:
    """测试公开扫码登录状态轮询函数。"""

    @pytest.mark.asyncio
    async def test_expired_when_redis_key_missing(self) -> None:
        """Redis key 不存在时应返回 expired。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.account_service.get_redis", return_value=mock_redis):
            result = await public_poll_qr_login_status("nonexistent_session")

        assert result["status"] == "expired"
        assert result["token"] is None
        assert result["user"] is None

    @pytest.mark.asyncio
    async def test_returns_cached_success(self) -> None:
        """已成功的 session 应直接返回缓存的 token 和 user。"""
        session_data = json.dumps({
            "status": "success",
            "token": "cached_jwt_token",
            "user": {"nickname": "缓存用户", "avatar": None, "xhs_user_id": "xhs_cached"},
        })
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=session_data)

        with patch("app.services.account_service.get_redis", return_value=mock_redis):
            result = await public_poll_qr_login_status("success_session")

        assert result["status"] == "success"
        assert result["token"] == "cached_jwt_token"
        assert result["user"]["nickname"] == "缓存用户"
        assert result["user"]["xhs_user_id"] == "xhs_cached"

    @pytest.mark.asyncio
    async def test_waiting_when_playwright_unavailable(self) -> None:
        """Playwright 不可用时 waiting 状态应保持 waiting。"""
        session_data = json.dumps({
            "status": "waiting",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=session_data)

        with patch("app.services.account_service.get_redis", return_value=mock_redis), \
             patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            result = await public_poll_qr_login_status("waiting_session")

        assert result["status"] == "waiting"
        assert result["token"] is None
        assert result["user"] is None
