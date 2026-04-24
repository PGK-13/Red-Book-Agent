"""模块 D 属性测试 — Hypothesis 驱动的正确性属性验证。

Property 10: 24h 内相同意图评论仅触发 1 次私信（去重正确性）
Property 12: 最近 10 轮消息保留（上下文截断正确性）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.interaction import DMTriggerLog
from app.services import interaction_service as svc


# ── Helper Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def merchant_id() -> str:
    return str(uuid4())


@pytest.fixture
async def db_with_account(
    db: AsyncSession,
    merchant_id: str,
) -> tuple[AsyncSession, str]:
    """创建测试账号，返回 (session, account_id)。供需要 FK 的测试使用。"""
    account = Account(
        merchant_id=merchant_id,
        xhs_user_id="prop_test_account",
        nickname="属性测试账号",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return db, account.id


# ─────────────────────────────────────────────────────────────────────────────
# Property 10: 24h 内相同意图评论仅触发 1 次私信
# Validates: Requirements D1.4, D3.6
# ─────────────────────────────────────────────────────────────────────────────


@given(
    intent=st.sampled_from([
        "ask_price", "complaint", "ask_link",
        "general_inquiry", "purchase_intent", "high_value_bd",
    ])
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property_dedup_24h_one_trigger_per_intent(
    db: AsyncSession,
    merchant_id: str,
    intent: str,
) -> None:
    """同一 (merchant, account, xhs_user, xhs_comment, intent) 在 24h 内仅触发 1 次。"""
    # 需要真实 account_id 作为 FK
    account = Account(
        merchant_id=merchant_id,
        xhs_user_id=f"acct_{uuid4().hex[:8]}",
        nickname="去重测试账号",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    account_id = account.id

    xhs_user_id = str(uuid4())
    xhs_comment_id = str(uuid4())

    # 首次调用 → 不去重
    first_result = await svc.check_dm_deduplication(
        merchant_id=merchant_id,
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
        intent=intent,
        db=db,
    )
    assert first_result is False, "首次调用不应去重"

    # 记录触发
    await svc.record_dm_trigger(
        merchant_id=merchant_id,
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
        intent=intent,
        db=db,
    )
    await db.commit()

    # 后续 100 次调用 → 全部去重
    for _ in range(100):
        result = await svc.check_dm_deduplication(
            merchant_id=merchant_id,
            account_id=account_id,
            xhs_user_id=xhs_user_id,
            xhs_comment_id=xhs_comment_id,
            intent=intent,
            db=db,
        )
        assert result is True, f"24h 内同一意图应去重 (intent={intent})"


@given(
    different_intent=st.sampled_from(["ask_price", "complaint", "ask_link"]),
    same_intent=st.just("ask_price"),
)
@settings(max_examples=30)
@pytest.mark.asyncio
async def test_property_dedup_different_intent_not_dedup(
    db: AsyncSession,
    merchant_id: str,
    different_intent: str,
    same_intent: str,
) -> None:
    """不同意图不应互相去重。"""
    assume(different_intent != same_intent)

    account = Account(
        merchant_id=merchant_id,
        xhs_user_id=f"acct_{uuid4().hex[:8]}",
        nickname="不同意图测试",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    xhs_user_id = str(uuid4())
    xhs_comment_id = str(uuid4())

    await svc.record_dm_trigger(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
        intent=same_intent,
        db=db,
    )
    await db.commit()

    result = await svc.check_dm_deduplication(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
        intent=different_intent,
        db=db,
    )
    assert result is False, "不同意图不应去重"


# ─────────────────────────────────────────────────────────────────────────────
# Property 12: 最近 10 轮消息保留
# Validates: Requirement D5.4
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyContextWindow:
    """上下文窗口 10 轮截断属性。"""

    @pytest.mark.asyncio
    async def test_context_window_truncates_at_10(
        self,
        db: AsyncSession,
        merchant_id: str,
    ) -> None:
        """超过 10 轮时自动截断，最早消息被删除。"""
        account = Account(
            merchant_id=merchant_id,
            xhs_user_id=f"ctx_{uuid4().hex[:8]}",
            nickname="上下文测试账号",
            status="active",
            access_type="browser",
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        conv = await svc.get_or_create_conversation(
            merchant_id=merchant_id,
            account_id=account.id,
            xhs_user_id="ctx_user",
            db=db,
        )

        for i in range(15):
            await svc.append_message(
                conversation_id=str(conv.id),
                role="user",
                content=f"消息 {i}",
                db=db,
            )

        messages, *_ = await svc.list_messages(
            conversation_id=conv.id,
            limit=100,
            cursor=None,
            db=db,
        )

        assert len(messages) == 10, f"超过 10 轮时应截断到 10，实际 {len(messages)}"
        assert messages[0].content == "消息 14"
        assert messages[9].content == "消息 5"

    @pytest.mark.asyncio
    async def test_context_window_under_10_keeps_all(
        self,
        db: AsyncSession,
        merchant_id: str,
    ) -> None:
        """不足 10 轮时保留全部消息。"""
        account = Account(
            merchant_id=merchant_id,
            xhs_user_id=f"ctx2_{uuid4().hex[:8]}",
            nickname="少于10轮测试",
            status="active",
            access_type="browser",
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        conv = await svc.get_or_create_conversation(
            merchant_id=merchant_id,
            account_id=account.id,
            xhs_user_id="ctx_user2",
            db=db,
        )

        for i in range(5):
            await svc.append_message(
                conversation_id=str(conv.id),
                role="user",
                content=f"消息 {i}",
                db=db,
            )

        messages, *_ = await svc.list_messages(
            conversation_id=conv.id,
            limit=100,
            cursor=None,
            db=db,
        )

        assert len(messages) == 5, f"不足 10 轮时应全部保留，实际 {len(messages)}"

    @pytest.mark.asyncio
    async def test_context_window_exactly_10_no_truncation(
        self,
        db: AsyncSession,
        merchant_id: str,
    ) -> None:
        """恰好 10 轮时不截断。"""
        account = Account(
            merchant_id=merchant_id,
            xhs_user_id=f"ctx3_{uuid4().hex[:8]}",
            nickname="恰好10轮测试",
            status="active",
            access_type="browser",
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        conv = await svc.get_or_create_conversation(
            merchant_id=merchant_id,
            account_id=account.id,
            xhs_user_id="ctx_user3",
            db=db,
        )

        for i in range(10):
            await svc.append_message(
                conversation_id=str(conv.id),
                role="user",
                content=f"消息 {i}",
                db=db,
            )

        messages, *_ = await svc.list_messages(
            conversation_id=conv.id,
            limit=100,
            cursor=None,
            db=db,
        )

        assert len(messages) == 10
        assert messages[0].content == "消息 9"


# ─────────────────────────────────────────────────────────────────────────────
# Property 10b: TTL 过期后去重失效
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_property_dedup_expires_after_24h(
    db: AsyncSession,
    merchant_id: str,
) -> None:
    """24h 后去重记录过期，再次触发应不触发去重。"""
    account = Account(
        merchant_id=merchant_id,
        xhs_user_id=f"ttl_{uuid4().hex[:8]}",
        nickname="TTL过期测试",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    past_time = datetime.now(timezone.utc) - timedelta(hours=25)

    log = DMTriggerLog(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_user_id=str(uuid4()),
        xhs_comment_id=str(uuid4()),
        intent="ask_price",
        triggered_at=past_time,
        expires_at=past_time,
    )
    db.add(log)
    await db.flush()

    result = await svc.check_dm_deduplication(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_user_id=log.xhs_user_id,
        xhs_comment_id=log.xhs_comment_id,
        intent="ask_price",
        db=db,
    )

    assert result is False, "已过期的去重记录不应去重"
