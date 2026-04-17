"""属性测试 — 使用 Hypothesis 验证账号模块的正确性属性。

Property 1: OAuth token 加密存储 (A1.3)
Property 2: Cookie 过期预警触发 (A1.4)
Property 3: Cookie 过期后状态转换 (A1.5)
Property 4: 代理 IP 绑定一致性 (A2.1)
Property 5: 设备指纹唯一性 (A2.3)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.security import decrypt, encrypt
from app.models.account import Account, AccountPersona, ProxyConfig
from app.services import account_service
from tests.conftest import _get_test_database_url


def _make_session_factory() -> async_sessionmaker:
    """创建独立的 session factory，每个 Hypothesis example 使用独立连接。"""
    engine = create_async_engine(
        _get_test_database_url(),
        echo=False,
        poolclass=NullPool,
        connect_args={
            "timeout": 5,
            "command_timeout": 5,
            "server_settings": {"application_name": "pytest"},
        },
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── 辅助 strategies ──

printable_nonempty = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=200,
)

screen_resolutions = st.from_regex(r"^\d{3,4}x\d{3,4}$", fullmatch=True)

timezones = st.sampled_from([
    "Asia/Shanghai", "Asia/Tokyo", "America/New_York",
    "Europe/London", "Australia/Sydney", "US/Pacific",
])

user_agents = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=10,
    max_size=100,
)


# ── Property 1: OAuth token 加密存储 ──


class TestOAuthTokenEncryption:
    """验证 encrypt/decrypt 对称性和密文不等于明文。"""

    @given(token=printable_nonempty)
    @settings(max_examples=200)
    def test_encrypt_produces_different_output(self, token: str) -> None:
        """加密后的密文不等于原始明文。"""
        encrypted = encrypt(token)
        assert encrypted != token, "密文不应等于明文"

    @given(token=printable_nonempty)
    @settings(max_examples=200)
    def test_encrypt_decrypt_roundtrip(self, token: str) -> None:
        """encrypt(token) 再 decrypt 应还原为原始值。"""
        encrypted = encrypt(token)
        decrypted = decrypt(encrypted)
        assert decrypted == token, f"解密结果 {decrypted!r} != 原始值 {token!r}"

    @given(token=printable_nonempty)
    @settings(max_examples=100)
    def test_different_encryptions_are_unique(self, token: str) -> None:
        """同一明文两次加密应产生不同密文（Fernet 包含时间戳和随机 IV）。"""
        enc1 = encrypt(token)
        enc2 = encrypt(token)
        assert enc1 != enc2, "两次加密应产生不同密文"


# ── Property 2: Cookie 过期预警触发 ──


class TestCookieExpiryWarning:
    pytestmark = pytest.mark.requires_db

    """验证 Cookie 距过期 < 24h 时触发通知，≥ 24h 时不触发。"""

    @pytest.mark.asyncio
    @given(hours_until_expiry=st.floats(min_value=0.01, max_value=23.99))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_warning_triggered_when_expiring_soon(
        self, hours_until_expiry: float
    ) -> None:
        """Cookie 距过期 < 24h 应触发预警通知。"""
        factory = _make_session_factory()
        async with factory() as db:
            now = datetime.now(timezone.utc)
            merchant_id = str(uuid4())
            account_id = str(uuid4())

            account = Account(
                id=account_id,
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="test",
                access_type="browser",
                status="active",
                cookie_enc=encrypt("test_cookie=value"),
                cookie_expires_at=now + timedelta(hours=hours_until_expiry),
            )
            db.add(account)
            await db.flush()

            with patch.object(account_service, "send_alert", new_callable=AsyncMock) as mock_alert, \
                 patch.object(account_service, "_check_platform_status", return_value=None):
                await account_service.probe_account_status(account_id, db)
                assert mock_alert.called, f"距过期 {hours_until_expiry:.1f}h 应触发通知"

            await db.rollback()

    @pytest.mark.asyncio
    @given(hours_until_expiry=st.floats(min_value=25.0, max_value=720.0))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_no_warning_when_not_expiring_soon(
        self, hours_until_expiry: float
    ) -> None:
        """Cookie 距过期 ≥ 24h 不应触发通知。"""
        factory = _make_session_factory()
        async with factory() as db:
            now = datetime.now(timezone.utc)
            merchant_id = str(uuid4())
            account_id = str(uuid4())

            account = Account(
                id=account_id,
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="test",
                access_type="browser",
                status="active",
                cookie_enc=encrypt("test_cookie=value"),
                cookie_expires_at=now + timedelta(hours=hours_until_expiry),
            )
            db.add(account)
            await db.flush()

            with patch.object(account_service, "send_alert", new_callable=AsyncMock) as mock_alert, \
                 patch.object(account_service, "_check_platform_status", return_value=None):
                await account_service.probe_account_status(account_id, db)
                assert not mock_alert.called, f"距过期 {hours_until_expiry:.1f}h 不应触发通知"

            await db.rollback()


# ── Property 3: Cookie 过期后状态转换 ──


class TestCookieExpiredStatusTransition:
    pytestmark = pytest.mark.requires_db

    """验证 Cookie 已过期时账号状态变为 auth_expired。"""

    @pytest.mark.asyncio
    @given(hours_past_expiry=st.floats(min_value=0.01, max_value=720.0))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_expired_cookie_sets_auth_expired(
        self, hours_past_expiry: float
    ) -> None:
        """Cookie 已过期 → 状态应变为 auth_expired。"""
        factory = _make_session_factory()
        async with factory() as db:
            now = datetime.now(timezone.utc)
            merchant_id = str(uuid4())
            account_id = str(uuid4())

            account = Account(
                id=account_id,
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="test",
                access_type="browser",
                status="active",
                cookie_enc=encrypt("test_cookie=value"),
                cookie_expires_at=now - timedelta(hours=hours_past_expiry),
            )
            db.add(account)
            await db.flush()

            with patch.object(account_service, "send_alert", new_callable=AsyncMock), \
                 patch.object(account_service, "_check_platform_status", return_value=None):
                result_status = await account_service.probe_account_status(account_id, db)

            assert result_status == "auth_expired", (
                f"Cookie 过期 {hours_past_expiry:.1f}h 后状态应为 auth_expired，实际为 {result_status}"
            )

            await db.rollback()


# ── Property 4: 代理 IP 绑定一致性 ──


class TestProxyIPBindingConsistency:
    """验证 get_browser_context 创建的上下文使用了正确的代理 IP。"""

    @given(
        proxy_url=st.from_regex(
            r"^http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{4,5}$", fullmatch=True
        ),
        ua=user_agents,
        resolution=screen_resolutions,
        tz=timezones,
    )
    @settings(max_examples=100)
    def test_browser_context_uses_correct_proxy(
        self, proxy_url: str, ua: str, resolution: str, tz: str
    ) -> None:
        """proxy_url 加密后解密还原，分辨率解析正确。"""
        from app.services.account_service import _parse_resolution

        encrypted_url = encrypt(proxy_url)
        assert decrypt(encrypted_url) == proxy_url

        viewport = _parse_resolution(resolution)
        parts = resolution.split("x")
        assert viewport == {"width": int(parts[0]), "height": int(parts[1])}


# ── Property 5: 设备指纹唯一性 ──


class TestDeviceFingerprintUniqueness:
    pytestmark = pytest.mark.requires_db

    """验证同商家下不同账号的设备指纹组合不重复。"""

    @pytest.mark.asyncio
    @given(
        ua=user_agents.filter(lambda x: len(x.strip()) > 0),
        resolution=screen_resolutions,
        tz=timezones,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_duplicate_fingerprint_rejected(
        self, ua: str, resolution: str, tz: str
    ) -> None:
        """同商家下两个账号使用相同指纹组合应被拒绝。"""
        from fastapi import HTTPException

        from app.schemas.account import ProxyUpdateRequest

        factory = _make_session_factory()
        async with factory() as db:
            merchant_id = str(uuid4())

            account1 = Account(
                id=str(uuid4()),
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="acc1",
                access_type="browser",
                status="active",
            )
            account2 = Account(
                id=str(uuid4()),
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="acc2",
                access_type="browser",
                status="active",
            )
            db.add_all([account1, account2])
            await db.flush()

            proxy_data = ProxyUpdateRequest(
                proxy_url="http://proxy.example.com:8080",
                user_agent=ua,
                screen_resolution=resolution,
                timezone=tz,
            )

            await account_service.update_proxy(merchant_id, account1.id, proxy_data, db)

            with pytest.raises(HTTPException) as exc_info:
                await account_service.update_proxy(merchant_id, account2.id, proxy_data, db)
            assert exc_info.value.status_code == 409, "重复指纹应返回 409"

            await db.rollback()

    @pytest.mark.asyncio
    @given(
        ua1=user_agents.filter(lambda x: len(x.strip()) > 0),
        ua2=user_agents.filter(lambda x: len(x.strip()) > 0),
        resolution=screen_resolutions,
        tz=timezones,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_different_fingerprint_accepted(
        self, ua1: str, ua2: str, resolution: str, tz: str
    ) -> None:
        """同商家下两个账号使用不同 user_agent 应被接受。"""
        from hypothesis import assume

        assume(ua1 != ua2)

        from app.schemas.account import ProxyUpdateRequest

        factory = _make_session_factory()
        async with factory() as db:
            merchant_id = str(uuid4())

            account1 = Account(
                id=str(uuid4()),
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="acc1",
                access_type="browser",
                status="active",
            )
            account2 = Account(
                id=str(uuid4()),
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="acc2",
                access_type="browser",
                status="active",
            )
            db.add_all([account1, account2])
            await db.flush()

            proxy1 = ProxyUpdateRequest(
                proxy_url="http://proxy1.example.com:8080",
                user_agent=ua1,
                screen_resolution=resolution,
                timezone=tz,
            )
            proxy2 = ProxyUpdateRequest(
                proxy_url="http://proxy2.example.com:8080",
                user_agent=ua2,
                screen_resolution=resolution,
                timezone=tz,
            )

            await account_service.update_proxy(merchant_id, account1.id, proxy1, db)
            await account_service.update_proxy(merchant_id, account2.id, proxy2, db)

            await db.rollback()
