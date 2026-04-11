"""AccountService 单元测试 — CRUD、状态机、merchant_id 隔离、代理警告。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt, encrypt
from app.models.account import Account, AccountPersona, ProxyConfig
from app.schemas.account import (
    AccountCreateRequest,
    PersonaUpdateRequest,
    ProxyUpdateRequest,
)
from app.services import account_service


# ── CRUD 正常路径 ──


class TestAccountCRUD:
    """测试账号 CRUD 操作。"""

    @pytest.mark.asyncio
    async def test_create_account(self, db: AsyncSession) -> None:
        """创建账号应返回正确字段。"""
        merchant_id = str(uuid4())
        data = AccountCreateRequest(
            xhs_user_id="xhs_test_001",
            nickname="测试账号",
            access_type="browser",
        )
        account = await account_service.create_account(merchant_id, data, db)

        assert account.merchant_id == merchant_id
        assert account.xhs_user_id == "xhs_test_001"
        assert account.nickname == "测试账号"
        assert account.access_type == "browser"
        assert account.status == "active"

    @pytest.mark.asyncio
    async def test_get_account(self, db: AsyncSession) -> None:
        """获取已创建的账号。"""
        merchant_id = str(uuid4())
        data = AccountCreateRequest(
            xhs_user_id="xhs_get_001",
            nickname="获取测试",
            access_type="oauth",
        )
        created = await account_service.create_account(merchant_id, data, db)
        await db.commit()

        fetched = await account_service.get_account(merchant_id, created.id, db)
        assert fetched.id == created.id
        assert fetched.xhs_user_id == "xhs_get_001"

    @pytest.mark.asyncio
    async def test_list_accounts(self, db: AsyncSession) -> None:
        """列出商家所有账号。"""
        merchant_id = str(uuid4())
        for i in range(3):
            data = AccountCreateRequest(
                xhs_user_id=f"xhs_list_{i}",
                nickname=f"列表测试{i}",
                access_type="rpa",
            )
            await account_service.create_account(merchant_id, data, db)
        await db.flush()

        items, next_cursor, has_more = await account_service.list_accounts(
            merchant_id, limit=10, cursor=None, db=db
        )
        assert len(items) == 3
        assert not has_more

    @pytest.mark.asyncio
    async def test_delete_account(self, db: AsyncSession) -> None:
        """删除账号后应无法再获取。"""
        merchant_id = str(uuid4())
        data = AccountCreateRequest(
            xhs_user_id="xhs_del_001",
            nickname="删除测试",
            access_type="browser",
        )
        account = await account_service.create_account(merchant_id, data, db)
        await db.flush()

        await account_service.delete_account(merchant_id, account.id, db)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await account_service.get_account(merchant_id, account.id, db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_account_limit(self, db: AsyncSession) -> None:
        """超过账号数量上限应返回 403。"""
        merchant_id = str(uuid4())
        original_limit = account_service.DEFAULT_ACCOUNT_LIMIT

        # 临时设置上限为 2
        account_service.DEFAULT_ACCOUNT_LIMIT = 2
        try:
            for i in range(2):
                data = AccountCreateRequest(
                    xhs_user_id=f"xhs_limit_{i}",
                    nickname=f"上限测试{i}",
                    access_type="browser",
                )
                await account_service.create_account(merchant_id, data, db)
            await db.flush()

            with pytest.raises(HTTPException) as exc_info:
                data = AccountCreateRequest(
                    xhs_user_id="xhs_limit_overflow",
                    nickname="超限",
                    access_type="browser",
                )
                await account_service.create_account(merchant_id, data, db)
            assert exc_info.value.status_code == 403
        finally:
            account_service.DEFAULT_ACCOUNT_LIMIT = original_limit


# ── Merchant ID 隔离 ──


class TestMerchantIsolation:
    """测试商家数据隔离。"""

    @pytest.mark.asyncio
    async def test_cannot_access_other_merchant_account(self, db: AsyncSession) -> None:
        """商家 A 不能访问商家 B 的账号。"""
        merchant_a = str(uuid4())
        merchant_b = str(uuid4())

        data = AccountCreateRequest(
            xhs_user_id="xhs_iso_001",
            nickname="商家A账号",
            access_type="browser",
        )
        account = await account_service.create_account(merchant_a, data, db)
        await db.flush()

        # 商家 B 尝试访问商家 A 的账号
        with pytest.raises(HTTPException) as exc_info:
            await account_service.get_account(merchant_b, account.id, db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_only_own_accounts(self, db: AsyncSession) -> None:
        """列表只返回当前商家的账号。"""
        merchant_a = str(uuid4())
        merchant_b = str(uuid4())

        for i in range(2):
            await account_service.create_account(
                merchant_a,
                AccountCreateRequest(
                    xhs_user_id=f"xhs_a_{i}", nickname=f"A{i}", access_type="browser"
                ),
                db,
            )
        await account_service.create_account(
            merchant_b,
            AccountCreateRequest(
                xhs_user_id="xhs_b_0", nickname="B0", access_type="browser"
            ),
            db,
        )
        await db.flush()

        items_a, _, _ = await account_service.list_accounts(merchant_a, 10, None, db)
        items_b, _, _ = await account_service.list_accounts(merchant_b, 10, None, db)

        assert len(items_a) == 2
        assert len(items_b) == 1

    @pytest.mark.asyncio
    async def test_cannot_delete_other_merchant_account(self, db: AsyncSession) -> None:
        """商家 B 不能删除商家 A 的账号。"""
        merchant_a = str(uuid4())
        merchant_b = str(uuid4())

        data = AccountCreateRequest(
            xhs_user_id="xhs_del_iso", nickname="隔离删除", access_type="browser"
        )
        account = await account_service.create_account(merchant_a, data, db)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await account_service.delete_account(merchant_b, account.id, db)
        assert exc_info.value.status_code == 404


# ── 状态机转换 ──


class TestStatusTransitions:
    """测试账号状态机转换。"""

    @pytest.mark.asyncio
    async def test_active_to_auth_expired(self, db: AsyncSession) -> None:
        """Cookie 过期 → active 变为 auth_expired。"""
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="状态测试",
            access_type="browser",
            status="active",
            cookie_enc=encrypt("cookie=test"),
            cookie_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(account)
        await db.flush()

        with patch.object(account_service, "send_alert", new_callable=AsyncMock), \
             patch.object(account_service, "_check_platform_status", return_value=None):
            status = await account_service.probe_account_status(account.id, db)

        assert status == "auth_expired"

    @pytest.mark.asyncio
    async def test_auth_expired_to_active_on_cookie_refresh(self, db: AsyncSession) -> None:
        """刷新 Cookie 后 auth_expired → active。"""
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="恢复测试",
            access_type="browser",
            status="auth_expired",
        )
        db.add(account)
        await db.flush()

        new_expires = datetime.now(timezone.utc) + timedelta(days=30)
        await account_service.update_cookie(
            merchant_id, account.id, "new_cookie=fresh", new_expires, db
        )
        await db.flush()
        await db.refresh(account)

        assert account.status == "active"
        assert account.cookie_enc is not None
        assert decrypt(account.cookie_enc) == "new_cookie=fresh"

    @pytest.mark.asyncio
    async def test_active_to_banned(self, db: AsyncSession) -> None:
        """平台返回 403 → active 变为 banned。"""
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="封禁测试",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch.object(account_service, "send_alert", new_callable=AsyncMock), \
             patch.object(account_service, "_check_platform_status", return_value=403):
            status = await account_service.probe_account_status(account.id, db)

        assert status == "banned"

    @pytest.mark.asyncio
    async def test_active_to_suspended(self, db: AsyncSession) -> None:
        """平台返回 429 → active 变为 suspended。"""
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="限流测试",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch.object(account_service, "send_alert", new_callable=AsyncMock), \
             patch.object(account_service, "_check_platform_status", return_value=429):
            status = await account_service.probe_account_status(account.id, db)

        assert status == "suspended"


# ── 代理未配置警告 ──


class TestProxyWarning:
    """测试未配置代理时的警告逻辑。"""

    @pytest.mark.asyncio
    async def test_no_proxy_logs_warning(self, db: AsyncSession, caplog) -> None:
        """未配置代理的账号创建浏览器上下文时应记录警告。"""
        import logging

        from sqlalchemy.orm import selectinload

        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="无代理",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        # 重新查询并 eagerly load proxy_config
        from sqlalchemy import select

        stmt = (
            select(Account)
            .where(Account.id == account.id)
            .options(selectinload(Account.proxy_config))
        )
        result = await db.execute(stmt)
        account = result.scalar_one()

        # Mock Playwright browser
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        from app.services.account_service import _create_browser_context

        with caplog.at_level(logging.WARNING, logger="app.services.account_service"):
            await _create_browser_context(mock_browser, account, db)

        assert any("no active proxy" in r.message.lower() for r in caplog.records), (
            "未配置代理时应记录 IP 混用风险警告"
        )


# ── OAuth 加密存储 ──


class TestOAuthStorage:
    """测试 OAuth 回调后 token 加密存储。"""

    @pytest.mark.asyncio
    async def test_oauth_token_encrypted(self, db: AsyncSession) -> None:
        """OAuth 回调后 token 应加密存储。"""
        merchant_id = str(uuid4())
        data = AccountCreateRequest(
            xhs_user_id="xhs_oauth_001",
            nickname="OAuth测试",
            access_type="oauth",
        )
        account = await account_service.create_account(merchant_id, data, db)
        await db.flush()

        raw_token = "test_access_token_12345"
        await account_service.handle_oauth_callback(
            merchant_id, account.id, raw_token, db
        )
        await db.flush()
        await db.refresh(account)

        # token 应加密存储
        assert account.oauth_token_enc is not None
        assert account.oauth_token_enc != raw_token
        assert decrypt(account.oauth_token_enc) == raw_token
