"""模块 D InteractionService 单元测试。

测试范围：
- 笔记监测配置 CRUD（add/remove/update/list）
- 会话模式切换（auto → human_takeover → auto）
- Captcha 阻断标志检查
- 在线时段判断
- 去重逻辑（存在/不存在/已过期）
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Conversation, MonitoredNote
from app.models.account import Account
from app.schemas.interaction import MonitoredNoteCreateRequest, MonitoredNoteUpdateRequest, OnlineHoursRequest
from app.services import interaction_service as svc


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def merchant_id() -> str:
    return str(uuid4())


@pytest.fixture
def account_id() -> str:
    return str(uuid4())


@pytest.fixture
async def monitored_note(
    db: AsyncSession,
    merchant_id: str,
) -> MonitoredNote:
    # 先创建账号（MonitoredNote 有外键依赖）
    account = Account(
        merchant_id=merchant_id,
        xhs_user_id="test_xhs_account",
        nickname="测试子账号",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    note = MonitoredNote(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_note_id="note_test_001",
        note_title="测试笔记",
        is_active=True,
        check_interval_seconds=60,
        batch_size=3,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


@pytest.fixture
async def conversation(
    db: AsyncSession,
    merchant_id: str,
) -> Conversation:
    # Conversation 有外键到 accounts.id，先创建账号
    account = Account(
        merchant_id=merchant_id,
        xhs_user_id="xhs_conv_account",
        nickname="会话测试账号",
        status="active",
        access_type="browser",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    conv = await svc.get_or_create_conversation(
        merchant_id=merchant_id,
        account_id=account.id,
        xhs_user_id="xhs_user_test",
        db=db,
    )
    return conv


# ─────────────────────────────────────────────────────────────────────────────
# 笔记监测配置 CRUD
# ─────────────────────────────────────────────────────────────────────────────


class TestMonitoredNoteCRUD:
    """笔记监测配置 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_add_monitored_note(self, db: AsyncSession, merchant_id: str, account_id: str) -> None:
        """添加监测笔记配置。"""
        data = MonitoredNoteCreateRequest(
            account_id=uuid4(),
            xhs_note_id="note_add_001",
            note_title="新笔记",
            check_interval_seconds=120,
            batch_size=5,
        )
        note = await svc.add_monitored_note(merchant_id, data, db)
        assert note.xhs_note_id == "note_add_001"
        assert note.is_active is True

    @pytest.mark.asyncio
    async def test_add_duplicate_note_raises(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """同一笔记重复添加应抛出 HTTPException。"""
        data = MonitoredNoteCreateRequest(
            account_id=uuid4(),
            xhs_note_id=monitored_note.xhs_note_id,
            note_title="重复笔记",
        )
        with pytest.raises(HTTPException) as exc_info:
            await svc.add_monitored_note(merchant_id, data, db)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_list_monitored_notes(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """列表查询应返回商家自己的笔记。"""
        notes = await svc.list_monitored_notes(merchant_id, account_id=None, is_active=None, db=db)
        assert len(notes) >= 1
        assert all(n.merchant_id == merchant_id for n in notes)

    @pytest.mark.asyncio
    async def test_list_monitored_notes_by_account(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """按账号过滤。"""
        notes = await svc.list_monitored_notes(merchant_id, account_id, is_active=True, db=db)
        assert all(n.account_id == account_id for n in notes)

    @pytest.mark.asyncio
    async def test_update_monitored_note(
        self,
        db: AsyncSession,
        merchant_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """更新监测笔记配置。"""
        update_data = MonitoredNoteUpdateRequest(
            is_active=False,
            check_interval_seconds=300,
        )
        updated = await svc.update_monitored_note(merchant_id, monitored_note.id, update_data, db)
        assert updated.is_active is False
        assert updated.check_interval_seconds == 300

    @pytest.mark.asyncio
    async def test_remove_monitored_note(
        self,
        db: AsyncSession,
        merchant_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """移除监测笔记。"""
        removed = await svc.remove_monitored_note(merchant_id, monitored_note.id, db)
        assert removed is True
        notes = await svc.list_monitored_notes(merchant_id, None, None, db=db)
        assert all(n.id != monitored_note.id for n in notes)

    @pytest.mark.asyncio
    async def test_remove_nonexistent_raises(
        self,
        db: AsyncSession,
        merchant_id: str,
    ) -> None:
        """删除不存在的笔记应抛 404。"""
        with pytest.raises(HTTPException) as exc_info:
            await svc.remove_monitored_note(merchant_id, str(uuid4()), db)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 会话模式切换
# ─────────────────────────────────────────────────────────────────────────────


class TestConversationModeSwitch:
    """会话模式切换测试。"""

    @pytest.mark.asyncio
    async def test_switch_to_human_takeover(
        self,
        db: AsyncSession,
        merchant_id: str,
        conversation: Conversation,
    ) -> None:
        """切换为人工接管模式。"""
        with patch.object(svc, "send_alert", new_callable=AsyncMock):
            updated = await svc.switch_to_human_takeover(
                merchant_id, conversation.id, reason="用户投诉", db=db
            )
        assert updated.mode == "human_takeover"

    @pytest.mark.asyncio
    async def test_release_human_takeover(
        self,
        db: AsyncSession,
        merchant_id: str,
        conversation: Conversation,
    ) -> None:
        """解除人工接管，恢复自动模式。"""
        with patch.object(svc, "send_alert", new_callable=AsyncMock):
            await svc.switch_to_human_takeover(merchant_id, conversation.id, "test", db=db)

        released = await svc.release_human_takeover(merchant_id, conversation.id, db=db)
        assert released.mode == "auto"

    @pytest.mark.asyncio
    async def test_takeover_nonexistent_raises(
        self,
        db: AsyncSession,
        merchant_id: str,
    ) -> None:
        """对不存在的会话切换模式应抛 404。"""
        with pytest.raises(HTTPException) as exc_info:
            await svc.switch_to_human_takeover(merchant_id, uuid4(), "test", db=db)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Captcha 阻断
# ─────────────────────────────────────────────────────────────────────────────


class TestCaptchaBlock:
    """Captcha 阻断标志测试。"""

    @pytest.mark.asyncio
    async def test_is_captcha_blocked_false_when_not_set(
        self,
        account_id: str,
    ) -> None:
        """未设置阻断时应返回 False。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_instance.exists.return_value = 0
            mock_redis.return_value = mock_instance

            blocked = await svc.is_captcha_blocked(account_id)
            assert blocked is False

    @pytest.mark.asyncio
    async def test_is_captcha_blocked_true_when_set(
        self,
        account_id: str,
    ) -> None:
        """设置阻断时应返回 True。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_instance.exists.return_value = 1
            mock_redis.return_value = mock_instance

            blocked = await svc.is_captcha_blocked(account_id)
            assert blocked is True

    @pytest.mark.asyncio
    async def test_handle_captcha_detected_sets_flag(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """Captcha 检测应设置 Redis 阻断标记并写入 HITL 队列。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis, \
             patch.object(svc, "send_alert", new_callable=AsyncMock):
            mock_instance = AsyncMock()
            mock_redis.return_value = mock_instance

            await svc.handle_captcha_detected(
                account_id=account_id,
                merchant_id=merchant_id,
                trigger_reason="captcha_detected",
                db=db,
            )

            # 验证 Redis set 被调用
            assert mock_instance.set.called

    @pytest.mark.asyncio
    async def test_clear_captcha_flag(
        self,
        account_id: str,
    ) -> None:
        """清除 Captcha 阻断标记。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_redis.return_value = mock_instance

            await svc.clear_captcha_flag(account_id)
            assert mock_instance.delete.called


# ─────────────────────────────────────────────────────────────────────────────
# 在线时段
# ─────────────────────────────────────────────────────────────────────────────


class TestOnlineHours:
    """在线时段判断测试。"""

    @pytest.mark.asyncio
    async def test_no_config_means_online(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """无在线时段配置时默认在线。"""
        await svc.get_or_create_conversation(merchant_id, account_id, "user_1", db=db)
        is_online = await svc.is_within_online_hours(account_id, db)
        assert is_online is True

    @pytest.mark.asyncio
    async def test_outside_hours_returns_false(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """配置时段外返回 False。"""
        conv = await svc.get_or_create_conversation(merchant_id, account_id, "user_2", db=db)

        # 设置时段为当前时间的下一小时（确保测试时不在时段内）
        now = datetime.now(timezone.utc)
        future_start = (now + timedelta(hours=2)).time()
        future_end = (now + timedelta(hours=4)).time()

        await svc.update_online_hours(
            merchant_id,
            conv.id,
            OnlineHoursRequest(
                online_hours_start=future_start.strftime("%H:%M"),
                online_hours_end=future_end.strftime("%H:%M"),
            ),
            db=db,
        )

        is_online = await svc.is_within_online_hours(account_id, db)
        assert is_online is False


# ─────────────────────────────────────────────────────────────────────────────
# 去重逻辑
# ─────────────────────────────────────────────────────────────────────────────


class TestDeduplication:
    """私信去重测试。"""

    @pytest.mark.asyncio
    async def test_first_trigger_not_deduped(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """首次触发不应去重。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = None
            mock_redis.return_value = mock_instance

            result = await svc.check_dm_deduplication(
                merchant_id=merchant_id,
                account_id=account_id,
                xhs_user_id="user_dedup",
                xhs_comment_id="comment_dedup_001",
                intent="ask_price",
                db=db,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_record_then_check_is_deduped(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """记录后再检查应去重。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = "1"  # Redis 已缓存
            mock_redis.return_value = mock_instance

            result = await svc.check_dm_deduplication(
                merchant_id=merchant_id,
                account_id=account_id,
                xhs_user_id="user_dedup2",
                xhs_comment_id="comment_dedup_002",
                intent="ask_price",
                db=db,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_different_comment_not_deduped(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """不同评论 ID 不应去重。"""
        with patch("app.services.interaction_service.get_redis", new_callable=AsyncMock) as mock_redis:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = "1"  # Redis 有缓存
            mock_redis.return_value = mock_instance

            # 相同用户和意图，但不同评论
            result = await svc.check_dm_deduplication(
                merchant_id=merchant_id,
                account_id=account_id,
                xhs_user_id="user_dedup3",
                xhs_comment_id="comment_different",
                intent="ask_price",
                db=db,
            )
            # Redis 缓存 key 包含 xhs_comment_id，不同评论 → 不去重
            assert result is False
