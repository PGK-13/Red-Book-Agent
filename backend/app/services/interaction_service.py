"""互动路由业务逻辑 — InteractionService.

所有业务逻辑集中在此 Service 层，API 路由层只做参数校验和响应封装。
所有查询严格按 merchant_id 过滤，确保商家数据隔离。

核心职责：
- 评论监测与意图分类（D1）
- 私信触发与去重（D3）
- 人工接管机制（D4）
- 实时客服 Agent（D5）
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from app.core.rate_limiter import get_redis
from app.models.interaction import (
    Comment,
    Conversation,
    DMTriggerLog,
    HITLQueue,
    IntentLog,
    Message,
    MonitoredNote,
)
from app.schemas.interaction import (
    CommentIntentResponse,
    CommentReplyRequest,
    ConversationModeRequest,
    ConversationResponse,
    DMReplyRequest,
    HITLApproveRequest,
    HITLEditApproveRequest,
    HITLQueueItemResponse,
    HITLRejectRequest,
    IntentLogResponse,
    MessageListRequest,
    MessageResponse,
    MonitoredNoteCreateRequest,
    MonitoredNoteResponse,
    MonitoredNoteUpdateRequest,
    OnlineHoursRequest,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Redis key patterns
_DM_DEDUP_KEY = "dm:dedup:{merchant_id}:{account_id}:{xhs_user_id}:{xhs_comment_id}"
_DM_MSG_DEDUP_KEY = "dm:msg:dedup:{msg_id}"
_SESSION_CONTEXT_KEY = "session:context:{conversation_id}"
_SESSION_PENDING_KEY = "session:pending:{conversation_id}"
_CAPTCHA_FLAG_KEY = "rpa:captcha_flag:{account_id}"
_TOKEN_BUCKET_KEY = "rpa:token_bucket:{account_id}"

# 意图分类置信度阈值
_CONFIDENCE_THRESHOLD = 0.7
# 情绪分数强负面阈值
_STRONG_NEGATIVE_THRESHOLD = -0.8
# 私信去重 TTL（24h）
_DM_DEDUP_TTL = 86400
# 消息防重 TTL（5min）
_DM_MSG_DEDUP_TTL = 300
# Captcha 阻断 TTL（手动清除，不设过期）
# 会话上下文 TTL（24h）
_SESSION_CONTEXT_TTL = 86400
# 待发送消息队列 TTL（30min）
_SESSION_PENDING_TTL = 1800
# HITL 回复字数限制
_HITL_REPLY_MIN = 1
_HITL_REPLY_MAX = 500
# 评论回复字数限制
_COMMENT_REPLY_MIN = 15
_COMMENT_REPLY_MAX = 80


# ── 内部数据类型 ───────────────────────────────────────────────────────────


@dataclass
class IntentClassificationResult:
    """意图分类结果。"""

    intent: str
    confidence: float
    sentiment_score: float
    needs_human_review: bool
    review_reason: str | None = None


@dataclass
class DMResult:
    """私信发送结果。"""

    success: bool
    sent_content: str | None = None
    error_message: str | None = None


# ── 笔记监测配置 ────────────────────────────────────────────────────────


async def add_monitored_note(
    merchant_id: str,
    data: MonitoredNoteCreateRequest,
    db: AsyncSession,
) -> MonitoredNote:
    """商家添加需要监测的笔记。

    Args:
        merchant_id: 商家 ID。
        data: 创建请求。
        db: 数据库会话。

    Returns:
        创建的 MonitoredNote 记录。
    """
    note = MonitoredNote(
        merchant_id=merchant_id,
        account_id=str(data.account_id),
        xhs_note_id=data.xhs_note_id,
        note_title=data.note_title,
        check_interval_seconds=data.check_interval_seconds,
        batch_size=data.batch_size,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def remove_monitored_note(
    merchant_id: str,
    note_id: UUID,
    db: AsyncSession,
) -> None:
    """移除监测笔记配置。

    Args:
        merchant_id: 商家 ID。
        note_id: 笔记配置 ID。
        db: 数据库会话。

    Raises:
        HTTPException: 笔记不存在或不属于该商家。
    """
    stmt = select(MonitoredNote).where(
        and_(
            MonitoredNote.id == str(note_id),
            MonitoredNote.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if not note:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="Monitored note not found")
    await db.delete(note)


async def update_monitored_note(
    merchant_id: str,
    note_id: UUID,
    data: MonitoredNoteUpdateRequest,
    db: AsyncSession,
) -> MonitoredNote:
    """更新监测笔记配置。

    Args:
        merchant_id: 商家 ID。
        note_id: 笔记配置 ID。
        data: 更新内容。
        db: 数据库会话。

    Returns:
        更新后的 MonitoredNote 记录。
    """
    stmt = select(MonitoredNote).where(
        and_(
            MonitoredNote.id == str(note_id),
            MonitoredNote.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if not note:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="Monitored note not found")

    if data.is_active is not None:
        note.is_active = data.is_active
    if data.check_interval_seconds is not None:
        note.check_interval_seconds = data.check_interval_seconds
    if data.batch_size is not None:
        note.batch_size = data.batch_size

    await db.flush()
    await db.refresh(note)
    return note


async def list_monitored_notes(
    merchant_id: str,
    account_id: UUID | None,
    is_active: bool | None,
    db: AsyncSession,
) -> list[MonitoredNote]:
    """获取监测笔记列表。

    Args:
        merchant_id: 商家 ID。
        account_id: 可选，按账号过滤。
        is_active: 可选，按激活状态过滤。
        db: 数据库会话。

    Returns:
        MonitoredNote 列表。
    """
    conditions = [MonitoredNote.merchant_id == merchant_id]
    if account_id is not None:
        conditions.append(MonitoredNote.account_id == str(account_id))
    if is_active is not None:
        conditions.append(MonitoredNote.is_active == is_active)

    stmt = select(MonitoredNote).where(and_(*conditions)).order_by(
        MonitoredNote.created_at.desc()
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 评论处理 ──────────────────────────────────────────────────────────────


async def get_comment_by_id(
    merchant_id: str,
    comment_id: UUID,
    db: AsyncSession,
) -> Comment | None:
    """根据 ID 获取评论。

    Args:
        merchant_id: 商家 ID。
        comment_id: 评论 ID。
        db: 数据库会话。

    Returns:
        Comment 记录或 None。
    """
    stmt = select(Comment).where(
        and_(
            Comment.id == str(comment_id),
            Comment.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_comments(
    merchant_id: str,
    account_id: UUID | None,
    xhs_note_id: str | None,
    reply_status: str | None,
    intent: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    limit: int,
    cursor: str | None,
    db: AsyncSession,
) -> tuple[list[Comment], str | None, bool]:
    """获取评论列表（cursor 分页）。

    Args:
        merchant_id: 商家 ID。
        account_id: 可选，按账号过滤。
        xhs_note_id: 可选，按笔记 ID 过滤。
        reply_status: 可选，按回复状态过滤。
        intent: 可选，按意图过滤。
        start_date: 可选，按开始时间过滤。
        end_date: 可选，按结束时间过滤。
        limit: 每页数量。
        cursor: 分页游标。
        db: 数据库会话。

    Returns:
        (评论列表, 下一页游标, 是否还有更多)。
    """
    conditions = [Comment.merchant_id == merchant_id]
    if account_id is not None:
        conditions.append(Comment.account_id == str(account_id))
    if xhs_note_id is not None:
        conditions.append(Comment.xhs_note_id == xhs_note_id)
    if reply_status is not None:
        conditions.append(Comment.reply_status == reply_status)
    if intent is not None:
        conditions.append(Comment.intent == intent)
    if start_date is not None:
        conditions.append(Comment.created_at >= start_date)
    if end_date is not None:
        conditions.append(Comment.created_at <= end_date)

    if cursor:
        conditions.append(Comment.id < cursor)

    stmt = (
        select(Comment)
        .where(and_(*conditions))
        .order_by(Comment.created_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    comments = list(result.scalars().all())

    has_more = len(comments) > limit
    if has_more:
        comments = comments[:limit]

    next_cursor = comments[-1].id if comments else None
    return comments, next_cursor, has_more


async def update_comment_reply_status(
    comment_id: str,
    reply_status: str,
    db: AsyncSession,
) -> None:
    """更新评论回复状态。

    Args:
        comment_id: 评论 ID。
        reply_status: 新状态。
        db: 数据库会话。
    """
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    if comment:
        comment.reply_status = reply_status
        await db.flush()


# ── 会话管理 ──────────────────────────────────────────────────────────────


async def get_or_create_conversation(
    merchant_id: str,
    account_id: str,
    xhs_user_id: str,
    db: AsyncSession,
) -> Conversation:
    """获取或创建私信会话。

    Args:
        merchant_id: 商家 ID。
        account_id: 商家账号 ID。
        xhs_user_id: 小红书用户 ID。
        db: 数据库会话。

    Returns:
        Conversation 记录。
    """
    stmt = select(Conversation).where(
        and_(
            Conversation.account_id == account_id,
            Conversation.xhs_user_id == xhs_user_id,
        )
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            merchant_id=merchant_id,
            account_id=account_id,
            xhs_user_id=xhs_user_id,
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)

    return conversation


async def get_conversation_by_id(
    merchant_id: str,
    conversation_id: UUID,
    db: AsyncSession,
) -> Conversation | None:
    """根据 ID 获取会话。

    Args:
        merchant_id: 商家 ID。
        conversation_id: 会话 ID。
        db: 数据库会话。

    Returns:
        Conversation 记录或 None。
    """
    stmt = select(Conversation).where(
        and_(
            Conversation.id == str(conversation_id),
            Conversation.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_conversations(
    merchant_id: str,
    account_id: UUID | None,
    mode: str | None,
    limit: int,
    cursor: str | None,
    db: AsyncSession,
) -> tuple[list[Conversation], str | None, bool]:
    """获取私信会话列表（cursor 分页）。

    Args:
        merchant_id: 商家 ID。
        account_id: 可选，按账号过滤。
        mode: 可选，按模式过滤。
        limit: 每页数量。
        cursor: 分页游标。
        db: 数据库会话。

    Returns:
        (会话列表, 下一页游标, 是否还有更多)。
    """
    conditions = [Conversation.merchant_id == merchant_id]
    if account_id is not None:
        conditions.append(Conversation.account_id == str(account_id))
    if mode is not None:
        conditions.append(Conversation.mode == mode)
    if cursor:
        conditions.append(Conversation.id < cursor)

    stmt = (
        select(Conversation)
        .where(and_(*conditions))
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    conversations = list(result.scalars().all())

    has_more = len(conversations) > limit
    if has_more:
        conversations = conversations[:limit]

    next_cursor = conversations[-1].id if conversations else None
    return conversations, next_cursor, has_more


async def switch_to_human_takeover(
    merchant_id: str,
    conversation_id: UUID,
    reason: str,
    db: AsyncSession,
) -> Conversation:
    """切换会话为人工接管模式。

    Args:
        merchant_id: 商家 ID。
        conversation_id: 会话 ID。
        reason: 触发原因。
        db: 数据库会话。

    Returns:
        更新后的 Conversation 记录。
    """
    conversation = await get_conversation_by_id(merchant_id, conversation_id, db)
    if not conversation:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.mode = "human_takeover"
    await db.flush()

    # 发送告警通知
    from app.core.notifications import send_alert

    await send_alert(
        merchant_id=merchant_id,
        alert_type="human_takeover",
        severity="warning",
        message=f"会话 {conversation_id} 触发人工接管，原因：{reason}",
    )

    return conversation


async def release_human_takeover(
    merchant_id: str,
    conversation_id: UUID,
    db: AsyncSession,
) -> Conversation:
    """解除人工接管，恢复自动模式。

    Args:
        merchant_id: 商家 ID。
        conversation_id: 会话 ID。
        db: 数据库会话。

    Returns:
        更新后的 Conversation 记录。
    """
    conversation = await get_conversation_by_id(merchant_id, conversation_id, db)
    if not conversation:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.mode = "auto"
    await db.flush()
    return conversation


async def update_online_hours(
    merchant_id: str,
    conversation_id: UUID,
    data: OnlineHoursRequest,
    db: AsyncSession,
) -> Conversation:
    """配置在线时段。

    Args:
        merchant_id: 商家 ID。
        conversation_id: 会话 ID。
        data: 在线时段配置。
        db: 数据库会话。

    Returns:
        更新后的 Conversation 记录。
    """
    conversation = await get_conversation_by_id(merchant_id, conversation_id, db)
    if not conversation:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="Conversation not found")

    if data.online_hours_start is not None:
        # 解析 HH:MM 格式
        parts = data.online_hours_start.split(":")
        conversation.online_hours_start = datetime.strptime(
            data.online_hours_start, "%H:%M"
        ).time()
    if data.online_hours_end is not None:
        conversation.online_hours_end = datetime.strptime(
            data.online_hours_end, "%H:%M"
        ).time()

    await db.flush()
    await db.refresh(conversation)
    return conversation


# ── 消息处理 ──────────────────────────────────────────────────────────────


async def list_messages(
    conversation_id: UUID,
    limit: int,
    cursor: str | None,
    db: AsyncSession,
) -> tuple[list[Message], str | None, bool]:
    """获取消息列表（cursor 分页）。

    Args:
        conversation_id: 会话 ID。
        limit: 每页数量。
        cursor: 分页游标。
        db: 数据库会话。

    Returns:
        (消息列表, 下一页游标, 是否还有更多)。
    """
    conditions = [Message.conversation_id == str(conversation_id)]
    if cursor:
        conditions.append(Message.id < cursor)

    stmt = (
        select(Message)
        .where(and_(*conditions))
        .order_by(Message.sent_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = messages[-1].id if messages else None
    return messages, next_cursor, has_more


async def append_message(
    conversation_id: str,
    role: Literal["user", "assistant"],
    content: str,
    db: AsyncSession,
    intent: str | None = None,
    confidence: float | None = None,
    sentiment_score: float | None = None,
) -> Message:
    """向会话追加消息，并维护最近 10 轮上下文。

    Args:
        conversation_id: 会话 ID。
        role: 消息角色。
        content: 消息内容。
        intent: 意图分类。
        confidence: 置信度。
        sentiment_score: 情绪分数。
        db: 数据库会话。

    Returns:
        创建的 Message 记录。
    """
    # 写入消息表
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        intent=intent,
        intent_confidence=confidence,
        sentiment_score=sentiment_score,
    )
    db.add(message)
    await db.flush()

    # 更新会话 last_message_at
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.last_message_at = datetime.now(timezone.utc)

    # 上下文截断：保留最近 10 轮
    context_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.desc())
    )
    ctx_result = await db.execute(context_stmt)
    all_messages = list(ctx_result.scalars().all())

    if len(all_messages) > 10:
        # 删除超过 10 轮的旧消息
        messages_to_delete = all_messages[10:]
        for msg in messages_to_delete:
            await db.delete(msg)

    await db.flush()
    await db.refresh(message)
    return message


# ── 去重检查 ──────────────────────────────────────────────────────────────


async def check_dm_deduplication(
    merchant_id: str,
    account_id: str,
    xhs_user_id: str,
    xhs_comment_id: str,
    intent: str,
    db: AsyncSession,
) -> bool:
    """检查 24h 内是否存在相同意图的已触发记录。

    Args:
        merchant_id: 商家 ID。
        account_id: 商家账号 ID。
        xhs_user_id: 小红书用户 ID。
        xhs_comment_id: 评论 ID。
        intent: 意图类型。
        db: 数据库会话。

    Returns:
        True 表示已去重（不触发），False 表示需要触发。
    """
    redis = await get_redis()
    cache_key = _DM_DEDUP_KEY.format(
        merchant_id=merchant_id,
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
    )

    # 先检查 Redis 缓存
    cached = await redis.get(cache_key)
    if cached:
        return True

    # 再检查数据库
    stmt = select(DMTriggerLog).where(
        and_(
            DMTriggerLog.merchant_id == merchant_id,
            DMTriggerLog.account_id == account_id,
            DMTriggerLog.xhs_user_id == xhs_user_id,
            DMTriggerLog.xhs_comment_id == xhs_comment_id,
            DMTriggerLog.intent == intent,
            DMTriggerLog.expires_at > datetime.now(timezone.utc),
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # 回填 Redis
        ttl = int((existing.expires_at - datetime.now(timezone.utc)).total_seconds())
        if ttl > 0:
            await redis.setex(cache_key, ttl, "1")
        return True

    return False


async def record_dm_trigger(
    merchant_id: str,
    account_id: str,
    xhs_user_id: str,
    xhs_comment_id: str,
    intent: str,
    db: AsyncSession,
) -> None:
    """记录私信触发，去重 TTL 24h。

    Args:
        merchant_id: 商家 ID。
        account_id: 商家账号 ID。
        xhs_user_id: 小红书用户 ID。
        xhs_comment_id: 评论 ID。
        intent: 意图类型。
        db: 数据库会话。
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    log = DMTriggerLog(
        merchant_id=merchant_id,
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
        intent=intent,
        triggered_at=now,
        expires_at=expires_at,
    )
    db.add(log)
    await db.flush()

    # 写入 Redis 缓存
    redis = await get_redis()
    cache_key = _DM_DEDUP_KEY.format(
        merchant_id=merchant_id,
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        xhs_comment_id=xhs_comment_id,
    )
    await redis.setex(cache_key, _DM_DEDUP_TTL, "1")


# ── HITL 审核 ──────────────────────────────────────────────────────────────


async def enqueue_hitl(
    merchant_id: str,
    conversation_id: str | None,
    comment_id: str | None,
    trigger_reason: str,
    original_content: str,
    suggested_reply: str | None,
    db: AsyncSession,
) -> HITLQueue:
    """将条目加入 HITL 待审核队列。

    Args:
        merchant_id: 商家 ID。
        conversation_id: 关联会话 ID（私信时）。
        comment_id: 关联评论 ID（评论时）。
        trigger_reason: 触发原因。
        original_content: 原始用户输入。
        suggested_reply: AI 建议回复。
        db: 数据库会话。

    Returns:
        创建的 HITLQueue 记录。
    """
    item = HITLQueue(
        merchant_id=merchant_id,
        conversation_id=conversation_id,
        comment_id=comment_id,
        trigger_reason=trigger_reason,
        original_content=original_content,
        suggested_reply=suggested_reply,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def get_hitl_queue_item(
    merchant_id: str,
    queue_id: UUID,
    db: AsyncSession,
) -> HITLQueue | None:
    """获取 HITL 队列项。

    Args:
        merchant_id: 商家 ID。
        queue_id: 队列项 ID。
        db: 数据库会话。

    Returns:
        HITLQueue 记录或 None。
    """
    stmt = select(HITLQueue).where(
        and_(
            HITLQueue.id == str(queue_id),
            HITLQueue.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_hitl_queue(
    merchant_id: str,
    status: str | None,
    limit: int,
    cursor: str | None,
    db: AsyncSession,
) -> tuple[list[HITLQueue], str | None, bool]:
    """获取 HITL 待审核队列（cursor 分页）。

    Args:
        merchant_id: 商家 ID。
        status: 可选，按状态过滤。
        limit: 每页数量。
        cursor: 分页游标。
        db: 数据库会话。

    Returns:
        (队列列表, 下一页游标, 是否还有更多)。
    """
    conditions = [HITLQueue.merchant_id == merchant_id]
    if status is not None:
        conditions.append(HITLQueue.status == status)
    if cursor:
        conditions.append(HITLQueue.id < cursor)

    stmt = (
        select(HITLQueue)
        .where(and_(*conditions))
        .order_by(HITLQueue.created_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = items[-1].id if items else None
    return items, next_cursor, has_more


async def approve_hitl(
    merchant_id: str,
    queue_id: UUID,
    final_reply: str | None,
    reviewer_id: str,
    db: AsyncSession,
) -> HITLQueue:
    """审核通过：发送回复并更新队列状态。

    Args:
        merchant_id: 商家 ID。
        queue_id: 队列项 ID。
        final_reply: 最终回复（若为空则使用建议回复）。
        reviewer_id: 审核人 ID。
        db: 数据库会话。

    Returns:
        更新后的 HITLQueue 记录。
    """
    item = await get_hitl_queue_item(merchant_id, queue_id, db)
    if not item:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="HITL queue item not found")

    reply_content = final_reply or item.suggested_reply
    if not reply_content:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=400, detail="No reply content available"
        )

    # 根据来源发送回复
    if item.comment_id:
        # 评论回复
        stmt = select(Comment).where(Comment.id == item.comment_id)
        result = await db.execute(stmt)
        comment = result.scalar_one_or_none()
        if comment:
            success, _ = await reply_comment_via_rpa(
                merchant_id=merchant_id,
                account_id=comment.account_id,
                xhs_note_id=comment.xhs_note_id,
                xhs_comment_id=comment.xhs_comment_id,
                reply_content=reply_content,
                db=db,
            )
            if success:
                comment.reply_status = "replied"
                await db.flush()
    elif item.conversation_id:
        # 私信回复
        conv = await get_conversation_by_id(merchant_id, UUID(item.conversation_id), db)
        if conv:
            success, _ = await send_dm_via_rpa(
                merchant_id=merchant_id,
                account_id=conv.account_id,
                xhs_user_id=conv.xhs_user_id,
                content=reply_content,
                db=db,
            )
            # 更新会话 last_message_at
            if success:
                conv.last_message_at = datetime.now(timezone.utc)
                await db.flush()

    item.status = "approved"
    item.final_reply = reply_content
    item.reviewed_by = reviewer_id
    item.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(item)
    return item


async def edit_approve_hitl(
    merchant_id: str,
    queue_id: UUID,
    edited_reply: str,
    reviewer_id: str,
    db: AsyncSession,
) -> HITLQueue:
    """修改后审核通过。

    Args:
        merchant_id: 商家 ID。
        queue_id: 队列项 ID。
        edited_reply: 修改后的回复内容。
        reviewer_id: 审核人 ID。
        db: 数据库会话。

    Returns:
        更新后的 HITLQueue 记录。
    """
    item = await get_hitl_queue_item(merchant_id, queue_id, db)
    if not item:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="HITL queue item not found")

    item.status = "edited"
    item.final_reply = edited_reply
    item.reviewed_by = reviewer_id
    item.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(item)
    return item


async def reject_hitl(
    merchant_id: str,
    queue_id: UUID,
    reviewer_id: str,
    reason: str | None,
    db: AsyncSession,
) -> HITLQueue:
    """审核拒绝。

    Args:
        merchant_id: 商家 ID。
        queue_id: 队列项 ID。
        reviewer_id: 审核人 ID。
        reason: 拒绝原因。
        db: 数据库会话。

    Returns:
        更新后的 HITLQueue 记录。
    """
    item = await get_hitl_queue_item(merchant_id, queue_id, db)
    if not item:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=404, detail="HITL queue item not found")

    item.status = "rejected"
    item.reviewed_by = reviewer_id
    item.reviewed_at = datetime.now(timezone.utc)
    if reason:
        item.suggested_reply = reason  # 暂存拒绝原因
    await db.flush()
    await db.refresh(item)
    return item


# ── Captcha 检测 ───────────────────────────────────────────────────────────


async def is_captcha_blocked(account_id: str) -> bool:
    """检查账号是否被 Captcha 阻断。

    Args:
        account_id: 账号 ID。

    Returns:
        True 表示被阻断。
    """
    redis = await get_redis()
    flag_key = _CAPTCHA_FLAG_KEY.format(account_id=account_id)
    return await redis.exists(flag_key) == 1


async def handle_captcha_detected(
    account_id: str,
    merchant_id: str,
    trigger_reason: str,
    db: AsyncSession,
) -> None:
    """Captcha 检测触发时，暂停账号自动化并加入 HITL 队列。

    Args:
        account_id: 账号 ID。
        merchant_id: 商家 ID。
        trigger_reason: 触发原因（固定为 captcha_detected）。
        db: 数据库会话。
    """
    redis = await get_redis()
    flag_key = _CAPTCHA_FLAG_KEY.format(account_id=account_id)
    await redis.set(flag_key, "1")  # 永不过期，手动清除

    # 加入 HITL 队列
    await enqueue_hitl(
        merchant_id=merchant_id,
        conversation_id=None,
        comment_id=None,
        trigger_reason="captcha_detected",
        original_content="Captcha 阻断，账号自动化已暂停",
        suggested_reply=None,
        db=db,
    )

    # 发送告警
    from app.core.notifications import send_alert

    await send_alert(
        merchant_id=merchant_id,
        alert_type="captcha_detected",
        severity="critical",
        message=f"账号 {account_id} 检测到验证码，自动化操作已暂停",
    )


async def clear_captcha_flag(account_id: str) -> None:
    """清除 Captcha 阻断标记，恢复账号自动化。

    Args:
        account_id: 账号 ID。
    """
    redis = await get_redis()
    flag_key = _CAPTCHA_FLAG_KEY.format(account_id=account_id)
    await redis.delete(flag_key)


# ── 在线时段检查 ────────────────────────────────────────────────────────


async def is_within_online_hours(
    account_id: str,
    db: AsyncSession,
) -> bool:
    """检查当前时间是否在账号配置的在线时段内。

    若会话无配置，返回 True（默认在线）。

    Args:
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        True 表示在在线时段内。
    """
    stmt = select(Conversation).where(Conversation.account_id == account_id)
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    if not conversations:
        return True  # 无配置，默认在线

    now = datetime.now(timezone.utc).time()

    for conv in conversations:
        start = conv.online_hours_start
        end = conv.online_hours_end
        if start is None or end is None:
            return True  # 无配置，默认在线
        if start <= end:
            if start <= now <= end:
                return True
        else:
            # 跨天情况（如 22:00-08:00）
            if now >= start or now <= end:
                return True

    return False


# ── 意图分类（调用 Agent）─────────────────────────────────────────────────


async def classify_comment_intent(
    merchant_id: str,
    content: str,
    ocr_result: str | None,
    db: AsyncSession,
) -> IntentClassificationResult:
    """对评论进行意图分类。

    调用 IntentRouterGraph Agent，输出分类结果。

    Args:
        merchant_id: 商家 ID。
        content: 评论文本。
        ocr_result: OCR 结果（如评论含图片）。
        db: 数据库会话。

    Returns:
        IntentClassificationResult。
    """
    from agent.graphs.intent_router import get_intent_router_graph

    agent = get_intent_router_graph()
    result = await agent.classify(
        source_type="comment",
        content=content,
        ocr_result=ocr_result,
        merchant_id=merchant_id,
    )

    return IntentClassificationResult(
        intent=result.intent or "other",
        confidence=result.confidence or 0.0,
        sentiment_score=result.sentiment_score or 0.0,
        needs_human_review=result.needs_human_review,
        review_reason=result.review_reason,
    )


async def classify_dm_intent(
    merchant_id: str,
    content: str,
    db: AsyncSession,
) -> IntentClassificationResult:
    """对私信进行意图分类。

    调用 IntentRouterGraph Agent，输出分类结果。

    Args:
        merchant_id: 商家 ID。
        content: 私信文本。
        db: 数据库会话。

    Returns:
        IntentClassificationResult。
    """
    from agent.graphs.intent_router import get_intent_router_graph

    agent = get_intent_router_graph()
    result = await agent.classify(
        source_type="message",
        content=content,
        ocr_result=None,
        merchant_id=merchant_id,
    )

    return IntentClassificationResult(
        intent=result.intent or "other",
        confidence=result.confidence or 0.0,
        sentiment_score=result.sentiment_score or 0.0,
        needs_human_review=result.needs_human_review,
        review_reason=result.review_reason,
    )


# ── Humanized Delay ────────────────────────────────────────────────────────


def humanized_delay(
    min_seconds: float = 3.0,
    max_seconds: float = 15.0,
) -> float:
    """返回随机等待秒数，模拟人类操作间隔。

    Args:
        min_seconds: 最小秒数。
        max_seconds: 最大秒数。

    Returns:
        随机等待秒数。
    """
    return random.uniform(min_seconds, max_seconds)


# ── OCR（调用本地 PaddleOCR）──────────────────────────────────────────────


async def perform_ocr(image_url: str) -> tuple[str, float]:
    """对图片 URL 执行 OCR 识别。

    Args:
        image_url: 图片 URL。

    Returns:
        (识别文本, 置信度)。
    """
    from agent.tools.ocr_tool import ocr_image

    return await ocr_image(image_url)


# ── RPA 评论监测 ─────────────────────────────────────────────────────────────


async def check_monitored_notes(
    account_id: str,
    db: AsyncSession,
) -> dict:
    """按令牌桶调度检查账号下所有激活笔记的新评论。

    每批最多处理 batch_size 篇，每篇之间注入随机延迟。
    仅处理增量评论（基于 xhs_comment_id 游标，不依赖索引顺序）。

    Args:
        account_id: 商家子账号 ID。
        db: 数据库会话。

    Returns:
        统计结果：processed_notes, new_comments, triggered_dms。
    """
    from app.services.note_polling_scheduler import NotePollingScheduler

    # 获取账号下的激活笔记
    stmt = select(MonitoredNote).where(
        and_(
            MonitoredNote.account_id == str(account_id),
            MonitoredNote.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    notes = list(result.scalars().all())

    if not notes:
        return {"processed_notes": 0, "new_comments": 0, "triggered_dms": 0}

    processed = 0
    new_comments = 0
    triggered_dms = 0

    async def process_note(note: MonitoredNote) -> None:
        """处理单篇笔记的增量评论。"""
        nonlocal new_comments, triggered_dms

        # Captcha 阻断检查
        if await is_captcha_blocked(account_id):
            return

        # 账号状态检查
        from app.models.account import Account
        acct_stmt = select(Account.status).where(Account.id == account_id)
        acct_result = await db.execute(acct_stmt)
        status = acct_result.scalar_one_or_none()
        if status in {"auth_expired", "banned", "suspended"}:
            return

        # 调用 RPA 获取增量评论
        from agent.tools.playwright_comment_monitor import poll_note_comments

        # 获取账号 Cookie
        cookie = None
        if hasattr(Account, "cookie_enc"):
            from app.core.security import decrypt
            acct_full = await db.get(Account, account_id)
            if acct_full and hasattr(acct_full, "cookie_enc") and acct_full.cookie_enc:
                cookie = decrypt(acct_full.cookie_enc)

        # 从 Redis 加载已知评论 ID（幂等兜底）
        from app.core.rate_limiter import get_redis as _svc_get_redis
        redis_client = await _svc_get_redis()
        known_ids_key = f"comment:known_ids:{note.account_id}:{note.xhs_note_id}"
        known_ids_raw = await redis_client.smembers(known_ids_key)
        known_comment_ids = set(str(cid) for cid in known_ids_raw)

        new_items, poll_time, captcha_detected = await poll_note_comments(
            account_id=account_id,
            xhs_note_id=note.xhs_note_id,
            last_checked_at=note.last_checked_at,
            known_comment_ids=known_comment_ids,
            cookie=cookie,
        )

        if captcha_detected:
            await handle_captcha_detected(
                account_id=account_id,
                merchant_id=note.merchant_id,
                trigger_reason="captcha_detected",
                db=db,
            )
            return

        # 处理增量评论
        for item in new_items:
            # 写入评论表
            comment = Comment(
                merchant_id=note.merchant_id,
                account_id=account_id,
                xhs_note_id=note.xhs_note_id,
                xhs_comment_id=item["xhs_comment_id"],
                xhs_user_id=item["xhs_user_id"],
                content=item["content"],
                image_urls=item.get("image_urls", []),
            )
            db.add(comment)
            await db.flush()

            # OCR（如含图片）
            ocr_result = None
            if item.get("image_urls"):
                ocr_texts = []
                for img_url in item["image_urls"]:
                    text, _ = await perform_ocr(img_url)
                    ocr_texts.append(text)
                ocr_result = "\n".join(ocr_texts) if ocr_texts else None

            # 意图分类
            intent_result = await classify_comment_intent(
                merchant_id=note.merchant_id,
                content=item["content"],
                ocr_result=ocr_result,
                db=db,
            )

            # 更新评论表
            comment.ocr_result = ocr_result
            comment.intent = intent_result.intent
            comment.intent_confidence = intent_result.confidence
            comment.sentiment_score = intent_result.sentiment_score

            # HITL 审核
            if intent_result.needs_human_review:
                await enqueue_hitl(
                    merchant_id=note.merchant_id,
                    conversation_id=None,
                    comment_id=str(comment.id),
                    trigger_reason=intent_result.review_reason or "low_confidence",
                    original_content=item["content"],
                    suggested_reply=None,  # TODO: 调用 RAG 生成建议回复
                    db=db,
                )
            else:
                # 触发私信
                is_deduped = await check_dm_deduplication(
                    merchant_id=note.merchant_id,
                    account_id=account_id,
                    xhs_user_id=item["xhs_user_id"],
                    xhs_comment_id=item["xhs_comment_id"],
                    intent=intent_result.intent,
                    db=db,
                )
                if not is_deduped:
                    # TODO: 生成私信内容并发送
                    # await trigger_dm_for_comment(...)
                    triggered_dms += 1

            new_comments += 1

        # 更新笔记状态：记录本轮轮询时间
        note.last_checked_at = poll_time
        # 将本轮处理的评论 ID 写入 Redis（幂等兜底）
        for item in new_items:
            await redis_client.sadd(known_ids_key, item["xhs_comment_id"])
        await db.flush()

        return note

    # 使用令牌桶调度器执行
    scheduler = NotePollingScheduler()
    processed = await scheduler.run_batch(
        account_id=account_id,
        notes=notes,
        process_fn=process_note,
        batch_size=3,
    )

    return {
        "processed_notes": processed,
        "new_comments": new_comments,
        "triggered_dms": triggered_dms,
    }


async def process_single_note_comments(
    merchant_id: str,
    note_id: str,
    db: AsyncSession,
) -> dict:
    """处理指定笔记的新增评论。

    供手动触发或单独监控使用。

    Args:
        merchant_id: 商家 ID。
        note_id: 监测笔记配置 ID。
        db: 数据库会话。

    Returns:
        处理结果统计。
    """
    # 获取笔记配置
    stmt = select(MonitoredNote).where(MonitoredNote.id == note_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note or note.merchant_id != merchant_id:
        return {"new_comments": 0, "triggered_dms": 0, "error": "Note not found"}

    # 执行单笔记检查
    from agent.tools.playwright_comment_monitor import poll_note_comments

    cookie = None
    from app.models.account import Account
    if hasattr(Account, "cookie_enc"):
        from app.core.security import decrypt
        acct_full = await db.get(Account, note.account_id)
        if acct_full and hasattr(acct_full, "cookie_enc") and acct_full.cookie_enc:
            cookie = decrypt(acct_full.cookie_enc)

    # 从 Redis 加载已知评论 ID（幂等兜底）
    from app.core.rate_limiter import get_redis as _svc_get_redis2
    redis_client2 = await _svc_get_redis2()
    known_ids_key2 = f"comment:known_ids:{note.account_id}:{note.xhs_note_id}"
    known_ids_raw2 = await redis_client2.smembers(known_ids_key2)
    known_comment_ids2 = set(str(cid) for cid in known_ids_raw2)

    new_items, poll_time, captcha_detected = await poll_note_comments(
        account_id=note.account_id,
        xhs_note_id=note.xhs_note_id,
        last_checked_at=note.last_checked_at,
        known_comment_ids=known_comment_ids2,
        cookie=cookie,
    )

    if captcha_detected:
        await handle_captcha_detected(
            account_id=note.account_id,
            merchant_id=merchant_id,
            trigger_reason="captcha_detected",
            db=db,
        )
        return {"new_comments": 0, "triggered_dms": 0, "error": "Captcha detected"}

    triggered_dms = 0

    for item in new_items:
        comment = Comment(
            merchant_id=merchant_id,
            account_id=note.account_id,
            xhs_note_id=note.xhs_note_id,
            xhs_comment_id=item["xhs_comment_id"],
            xhs_user_id=item["xhs_user_id"],
            content=item["content"],
            image_urls=item.get("image_urls", []),
        )
        db.add(comment)
        await db.flush()

        ocr_result = None
        if item.get("image_urls"):
            ocr_texts = []
            for img_url in item["image_urls"]:
                text, _ = await perform_ocr(img_url)
                ocr_texts.append(text)
            ocr_result = "\n".join(ocr_texts) if ocr_texts else None

        intent_result = await classify_comment_intent(
            merchant_id=merchant_id,
            content=item["content"],
            ocr_result=ocr_result,
            db=db,
        )

        if intent_result.needs_human_review:
            await enqueue_hitl(
                merchant_id=merchant_id,
                conversation_id=None,
                comment_id=str(comment.id),
                trigger_reason=intent_result.review_reason or "low_confidence",
                original_content=item["content"],
                suggested_reply=None,
                db=db,
            )
        else:
            is_deduped = await check_dm_deduplication(
                merchant_id=merchant_id,
                account_id=note.account_id,
                xhs_user_id=item["xhs_user_id"],
                xhs_comment_id=item["xhs_comment_id"],
                intent=intent_result.intent,
                db=db,
            )
            if not is_deduped:
                triggered_dms += 1

    note.last_checked_at = poll_time
    # 将本轮处理的评论 ID 写入 Redis（幂等兜底）
    for item in new_items:
        await redis_client2.sadd(known_ids_key2, item["xhs_comment_id"])
    await db.flush()

    return {"new_comments": len(new_items), "triggered_dms": triggered_dms}


# ── RPA 私信 ────────────────────────────────────────────────────────────────


async def send_dm_via_rpa(
    merchant_id: str,
    account_id: str,
    xhs_user_id: str,
    content: str,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """通过 Playwright RPA 发送私信。

    发送前执行风控扫描，频率配额检查，Captcha 检测。

    Args:
        merchant_id: 商家 ID。
        account_id: 商家子账号 ID。
        xhs_user_id: 小红书用户 ID。
        content: 私信内容。
        db: 数据库会话。

    Returns:
        (发送是否成功, 错误信息或 None)。
    """
    # 账号状态检查
    from app.models.account import Account

    acct_stmt = select(Account).where(Account.id == account_id)
    acct_result = await db.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()

    if not account:
        return False, "Account not found"

    if account.status in {"auth_expired", "banned", "suspended"}:
        return False, f"Account status is {account.status}"

    # Captcha 阻断检查
    if await is_captcha_blocked(account_id):
        return False, "Account is captcha blocked"

    # 风控扫描
    from agent.tools.risk_scan import scan_content

    risk_result = await scan_content(content=content, merchant_id=merchant_id)
    if not risk_result.passed:
        return False, f"Risk scan failed: {risk_result.hit_keywords}"

    # 频率配额检查
    from app.services import risk_service

    quota_ok = await risk_service.check_and_reserve_quota(
        merchant_id=merchant_id,
        account_id=account_id,
        action="send_dm",
        db=db,
    )
    if not quota_ok:
        return False, "Rate limit exceeded"

    # 获取账号 Cookie 和代理
    cookie = None
    proxy_url = None
    if hasattr(account, "cookie_enc") and account.cookie_enc:
        from app.core.security import decrypt
        cookie = decrypt(account.cookie_enc)
    if hasattr(account, "proxy_url_enc") and account.proxy_url_enc:
        from app.core.security import decrypt
        proxy_url = decrypt(account.proxy_url_enc)

    # 注入人类化延迟
    import asyncio
    delay = humanized_delay(min_seconds=3.0, max_seconds=15.0)
    await asyncio.sleep(delay)

    # 调用 RPA 发送私信
    from agent.tools.playwright_dm_sender import send_dm

    success, error = await send_dm(
        account_id=account_id,
        xhs_user_id=xhs_user_id,
        content=content,
        cookie=cookie,
        proxy_url=proxy_url,
    )

    return success, error


async def reply_comment_via_rpa(
    merchant_id: str,
    account_id: str,
    xhs_note_id: str,
    xhs_comment_id: str,
    reply_content: str,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """通过 Playwright RPA 发送评论回复。

    发送前执行风控扫描，字数限制 15~80 字。

    Args:
        merchant_id: 商家 ID。
        account_id: 商家子账号 ID。
        xhs_note_id: 小红书笔记 ID。
        xhs_comment_id: 小红书评论 ID。
        reply_content: 回复内容（15~80 字）。
        db: 数据库会话。

    Returns:
        (发送是否成功, 错误信息或 None)。
    """
    # 字数校验
    char_count = len(reply_content.strip())
    if char_count < 15 or char_count > 80:
        return False, f"Reply content must be 15-80 characters, got {char_count}"

    # 账号状态检查
    from app.models.account import Account

    acct_stmt = select(Account).where(Account.id == account_id)
    acct_result = await db.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()

    if not account:
        return False, "Account not found"

    if account.status in {"auth_expired", "banned", "suspended"}:
        return False, f"Account status is {account.status}"

    # Captcha 阻断检查
    if await is_captcha_blocked(account_id):
        return False, "Account is captcha blocked"

    # 风控扫描
    from agent.tools.risk_scan import scan_content

    risk_result = await scan_content(content=reply_content, merchant_id=merchant_id)
    if not risk_result.passed:
        return False, f"Risk scan failed: {risk_result.hit_keywords}"

    # 频率配额检查
    from app.services import risk_service

    quota_ok = await risk_service.check_and_reserve_quota(
        merchant_id=merchant_id,
        account_id=account_id,
        action="reply_comment",
        db=db,
    )
    if not quota_ok:
        return False, "Rate limit exceeded"

    # 获取账号 Cookie 和代理
    cookie = None
    proxy_url = None
    if hasattr(account, "cookie_enc") and account.cookie_enc:
        from app.core.security import decrypt
        cookie = decrypt(account.cookie_enc)
    if hasattr(account, "proxy_url_enc") and account.proxy_url_enc:
        from app.core.security import decrypt
        proxy_url = decrypt(account.proxy_url_enc)

    # 注入人类化延迟
    import asyncio
    delay = humanized_delay(min_seconds=3.0, max_seconds=15.0)
    await asyncio.sleep(delay)

    # 调用 RPA 发送评论回复
    from agent.tools.playwright_comment_replier import send_comment_reply

    success, error = await send_comment_reply(
        account_id=account_id,
        xhs_note_id=xhs_note_id,
        xhs_comment_id=xhs_comment_id,
        reply_content=reply_content,
        cookie=cookie,
        proxy_url=proxy_url,
    )

    return success, error


async def poll_dm_messages(
    account_id: str,
    db: AsyncSession,
) -> dict:
    """通过 Playwright RPA 轮询商家端私信消息。

    检测新私信并写入 messages 表，触发自动回复。

    Args:
        account_id: 商家子账号 ID。
        db: 数据库会话。

    Returns:
        轮询结果统计。
    """
    from app.core.rate_limiter import get_redis

    # 账号状态检查
    from app.models.account import Account

    acct_stmt = select(Account).where(Account.id == account_id)
    acct_result = await db.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()

    if not account:
        return {"new_messages": 0, "replies_sent": 0, "error": "Account not found"}

    if account.status in {"auth_expired", "banned", "suspended"}:
        return {"new_messages": 0, "replies_sent": 0, "error": f"Account status: {account.status}"}

    # Captcha 阻断检查
    if await is_captcha_blocked(account_id):
        return {"new_messages": 0, "replies_sent": 0, "error": "Captcha blocked"}

    # 获取 Redis 已知消息 ID
    redis = await get_redis()
    known_msg_ids_key = f"dm:known_msg_ids:{account_id}"
    known_ids_raw = await redis.smembers(known_msg_ids_key)
    known_msg_ids = set(str(mid) for mid in known_ids_raw)

    # 获取账号 Cookie 和代理
    cookie = None
    proxy_url = None
    if hasattr(account, "cookie_enc") and account.cookie_enc:
        from app.core.security import decrypt
        cookie = decrypt(account.cookie_enc)
    if hasattr(account, "proxy_url_enc") and account.proxy_url_enc:
        from app.core.security import decrypt
        proxy_url = decrypt(account.proxy_url_enc)

    # 调用 RPA 轮询
    from agent.tools.playwright_dm_monitor import poll_dm_messages as rpa_poll_dm

    new_items, captcha_detected = await rpa_poll_dm(
        account_id=account_id,
        cookie=cookie,
        proxy_url=proxy_url,
        known_msg_ids=known_msg_ids,
    )

    if captcha_detected:
        await handle_captcha_detected(
            account_id=account_id,
            merchant_id=account.merchant_id,
            trigger_reason="captcha_detected",
            db=db,
        )
        return {"new_messages": 0, "replies_sent": 0, "error": "Captcha detected"}

    new_messages = 0
    replies_sent = 0

    for item in new_items:
        # 获取或创建会话
        conversation = await get_or_create_conversation(
            merchant_id=account.merchant_id,
            account_id=account_id,
            xhs_user_id=item["xhs_user_id"],
            db=db,
        )

        # 写入消息
        message = await append_message(
            conversation_id=str(conversation.id),
            role="user",
            content=item["content"],
            db=db,
        )

        # 更新 Redis 已知消息 ID
        await redis.sadd(known_msg_ids_key, item["xhs_msg_id"])

        new_messages += 1

        # 触发自动回复（如会话模式为 auto）
        if conversation.mode == "auto":
            intent_result = await classify_dm_intent(
                merchant_id=account.merchant_id,
                content=item["content"],
                db=db,
            )

            if not intent_result.needs_human_review:
                # 生成并发送回复
                from agent.graphs.customer_service import get_customer_service_graph

                svc_graph = get_customer_service_graph()
                result = await svc_graph.reply(
                    conversation_id=str(conversation.id),
                    merchant_id=account.merchant_id,
                    account_id=account_id,
                    xhs_user_id=item["xhs_user_id"],
                    user_message=item["content"],
                    mode=conversation.mode,
                    db=db,
                )

                if result.send_success and result.final_reply:
                    success, _ = await send_dm_via_rpa(
                        merchant_id=account.merchant_id,
                        account_id=account_id,
                        xhs_user_id=item["xhs_user_id"],
                        content=result.final_reply,
                        db=db,
                    )
                    if success:
                        replies_sent += 1
            else:
                await enqueue_hitl(
                    merchant_id=account.merchant_id,
                    conversation_id=str(conversation.id),
                    comment_id=None,
                    trigger_reason=intent_result.review_reason or "low_confidence",
                    original_content=item["content"],
                    suggested_reply=None,
                    db=db,
                )

    return {"new_messages": new_messages, "replies_sent": replies_sent}

