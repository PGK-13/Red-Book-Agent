"""互动与客服 API 路由。

路由层只做参数校验和响应封装，所有业务逻辑委托给 InteractionService。
所有路由注入 CurrentMerchantId 和 DbSession 依赖。
"""

from __future__ import annotations

from uuid import UUID

from app.dependencies import CurrentMerchantId, DbSession
from app.schemas.base import BaseResponse, PaginatedData, PaginatedResponse
from app.schemas.interaction import (
    CommentIntentResponse,
    CommentListRequest,
    CommentReplyRequest,
    CommentResponse,
    ConversationListRequest,
    ConversationModeRequest,
    ConversationResponse,
    HITLApproveRequest,
    HITLEditApproveRequest,
    HITLBatchApproveRequest,
    HITLQueueItemResponse,
    HITLRejectRequest,
    MessageListRequest,
    MessageResponse,
    MonitoredNoteCreateRequest,
    MonitoredNoteResponse,
    MonitoredNoteUpdateRequest,
    OnlineHoursRequest,
)
from app.services import interaction_service as svc
from app.services.interaction_service import IntentLog
from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/interaction", tags=["互动与客服"])


# ── 辅助函数 ───────────────────────────────────────────────────────────


def _to_comment_response(c: any) -> CommentResponse:
    """将 Comment ORM 模型转换为响应 Schema。"""
    return CommentResponse(
        id=c.id,
        account_id=c.account_id,
        xhs_note_id=c.xhs_note_id,
        xhs_comment_id=c.xhs_comment_id,
        xhs_user_id=c.xhs_user_id,
        content=c.content,
        image_urls=c.image_urls or [],
        ocr_result=c.ocr_result,
        intent=c.intent,
        intent_confidence=c.intent_confidence,
        sentiment_score=c.sentiment_score,
        reply_status=c.reply_status,
        deduplicated=c.deduplicated,
        detected_at=c.detected_at,
        created_at=c.created_at,
    )


def _to_conversation_response(c: any) -> ConversationResponse:
    """将 Conversation ORM 模型转换为响应 Schema。"""
    return ConversationResponse(
        id=c.id,
        account_id=c.account_id,
        xhs_user_id=c.xhs_user_id,
        mode=c.mode,
        user_long_term_memory=c.user_long_term_memory,
        online_hours_start=c.online_hours_start,
        online_hours_end=c.online_hours_end,
        last_message_at=c.last_message_at,
        created_at=c.created_at,
    )


def _to_message_response(m: any) -> MessageResponse:
    """将 Message ORM 模型转换为响应 Schema。"""
    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        intent=m.intent,
        intent_confidence=m.intent_confidence,
        sentiment_score=m.sentiment_score,
        sent_at=m.sent_at,
    )


def _to_hitl_item_response(item: any) -> HITLQueueItemResponse:
    """将 HITLQueue ORM 模型转换为响应 Schema。"""
    return HITLQueueItemResponse(
        id=item.id,
        trigger_reason=item.trigger_reason,
        original_content=item.original_content,
        suggested_reply=item.suggested_reply,
        conversation_id=item.conversation_id,
        comment_id=item.comment_id,
        status=item.status,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
    )


def _to_monitored_note_response(n: any) -> MonitoredNoteResponse:
    """将 MonitoredNote ORM 模型转换为响应 Schema。"""
    return MonitoredNoteResponse(
        id=n.id,
        account_id=n.account_id,
        xhs_note_id=n.xhs_note_id,
        note_title=n.note_title,
        is_active=n.is_active,
        check_interval_seconds=n.check_interval_seconds,
        batch_size=n.batch_size,
        last_checked_at=n.last_checked_at,
        last_known_comment_count=n.last_known_comment_count,
        last_seen_comment_id=n.last_seen_comment_id,
        created_at=n.created_at,
    )


# ── 监测笔记配置 ───────────────────────────────────────────────────────


@router.get("/monitored-notes", response_model=PaginatedResponse[MonitoredNoteResponse])
async def list_monitored_notes(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    account_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> PaginatedResponse[MonitoredNoteResponse]:
    """获取监测笔记列表，支持按账号和激活状态筛选。"""
    items = await svc.list_monitored_notes(merchant_id, account_id, is_active, db)
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_monitored_note_response(n) for n in items],
            next_cursor=None,
            has_more=False,
        )
    )


@router.post(
    "/monitored-notes",
    response_model=BaseResponse[MonitoredNoteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_monitored_note(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: MonitoredNoteCreateRequest,
) -> BaseResponse[MonitoredNoteResponse]:
    """添加需要监测的笔记，配置检查间隔和批次大小。"""
    note = await svc.add_monitored_note(merchant_id, body, db)
    return BaseResponse(data=_to_monitored_note_response(note))


@router.put(
    "/monitored-notes/{note_id}",
    response_model=BaseResponse[MonitoredNoteResponse],
)
async def update_monitored_note(
    note_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: MonitoredNoteUpdateRequest,
) -> BaseResponse[MonitoredNoteResponse]:
    """更新监测笔记的配置（激活状态/检查间隔/批次大小）。"""
    note = await svc.update_monitored_note(merchant_id, note_id, body, db)
    return BaseResponse(data=_to_monitored_note_response(note))


@router.delete(
    "/monitored-notes/{note_id}",
    response_model=BaseResponse,
)
async def remove_monitored_note(
    note_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """移除监测笔记配置，删除后该笔记不再被监测。"""
    await svc.remove_monitored_note(merchant_id, note_id, db)
    return BaseResponse(message="监测笔记已移除")


# ── 评论管理 ─────────────────────────────────────────────────────────────


@router.get("/comments", response_model=PaginatedResponse[CommentResponse])
async def list_comments(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: CommentListRequest,
) -> PaginatedResponse[CommentResponse]:
    """获取评论列表，支持按账号/笔记/状态/意图/时间范围筛选。"""
    items, next_cursor, has_more = await svc.list_comments(
        merchant_id=merchant_id,
        account_id=body.account_id,
        xhs_note_id=body.xhs_note_id,
        reply_status=body.reply_status,
        intent=body.intent,
        start_date=body.start_date,
        end_date=body.end_date,
        limit=body.limit,
        cursor=body.cursor,
        db=db,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_comment_response(c) for c in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )
    )


@router.get("/comments/{comment_id}", response_model=BaseResponse[CommentResponse])
async def get_comment(
    comment_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[CommentResponse]:
    """获取单条评论详情，包含 OCR 结果和意图分类信息。"""
    comment = await svc.get_comment_by_id(merchant_id, comment_id, db)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return BaseResponse(data=_to_comment_response(comment))


@router.post(
    "/comments/{comment_id}/classify",
    response_model=BaseResponse[CommentIntentResponse],
)
async def classify_comment(
    comment_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[CommentIntentResponse]:
    """对评论执行 OCR（如含图片）并调用 Agent 进行意图分类，返回意图/置信度/情绪分。"""
    comment = await svc.get_comment_by_id(merchant_id, comment_id, db)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # 执行 OCR（如有图片）
    ocr_result = None
    if comment.image_urls:
        ocr_texts = []
        for url in comment.image_urls:
            text, _ = await svc.perform_ocr(url)
            ocr_texts.append(text)
        ocr_result = "\n".join(ocr_texts) if ocr_texts else None

    # 意图分类
    result = await svc.classify_comment_intent(
        merchant_id=merchant_id,
        content=comment.content,
        ocr_result=ocr_result,
        db=db,
    )

    # 更新评论表的意图字段
    comment.intent = result.intent
    comment.intent_confidence = result.confidence
    comment.sentiment_score = result.sentiment_score
    await db.flush()

    # 写入意图日志
    log = IntentLog(
        merchant_id=merchant_id,
        source_type="comment",
        source_id=comment.id,
        raw_input=comment.content,
        intent=result.intent,
        confidence=result.confidence,
        sentiment_score=result.sentiment_score,
    )
    db.add(log)
    await db.flush()

    return BaseResponse(
        data=CommentIntentResponse(
            comment_id=comment.id,
            intent=result.intent,
            confidence=result.confidence,
            sentiment_score=result.sentiment_score,
            ocr_result=ocr_result,
            needs_human_review=result.needs_human_review,
        )
    )


@router.post("/comments/{comment_id}/reply", response_model=BaseResponse)
async def reply_comment(
    comment_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: CommentReplyRequest,
) -> BaseResponse:
    """发送评论回复，回复内容需在 15~80 字之间，执行风控扫描后通过 RPA 发送。"""
    comment = await svc.get_comment_by_id(merchant_id, comment_id, db)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reply_content = body.reply_content.strip()
    if len(reply_content) < 15 or len(reply_content) > 80:
        raise HTTPException(
            status_code=422,
            detail="Reply content must be between 15 and 80 characters",
        )

    success, error = await svc.reply_comment_via_rpa(
        merchant_id=merchant_id,
        account_id=str(comment.account_id),
        xhs_note_id=comment.xhs_note_id,
        xhs_comment_id=comment.xhs_comment_id,
        reply_content=reply_content,
        db=db,
    )
    if not success:
        raise HTTPException(status_code=500, detail=error or "Failed to send reply")

    return BaseResponse(message="Reply sent")


# ── 会话管理 ─────────────────────────────────────────────────────────────


@router.get(
    "/conversations",
    response_model=PaginatedResponse[ConversationResponse],
)
async def list_conversations(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: ConversationListRequest,
) -> PaginatedResponse[ConversationResponse]:
    """获取私信会话列表，支持按账号和模式（auto/human_takeover/pending）筛选。"""
    items, next_cursor, has_more = await svc.list_conversations(
        merchant_id=merchant_id,
        account_id=body.account_id,
        mode=body.mode,
        limit=body.limit,
        cursor=body.cursor,
        db=db,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_conversation_response(c) for c in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=BaseResponse[ConversationResponse],
)
async def get_conversation(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[ConversationResponse]:
    """获取会话详情，包含当前模式和在线时段配置。"""
    conv = await svc.get_conversation_by_id(merchant_id, conversation_id, db)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return BaseResponse(data=_to_conversation_response(conv))


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
)
async def list_conversation_messages(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: MessageListRequest,
) -> PaginatedResponse[MessageResponse]:
    """获取会话的消息历史记录，按时间倒序返回。"""
    # 验证会话归属
    conv = await svc.get_conversation_by_id(merchant_id, conversation_id, db)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    items, next_cursor, has_more = await svc.list_messages(
        conversation_id=conversation_id,
        limit=body.limit,
        cursor=body.cursor,
        db=db,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_message_response(m) for m in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )
    )


@router.post("/conversations/{conversation_id}/reply", response_model=BaseResponse)
async def reply_conversation(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: DMReplyRequest,
) -> BaseResponse:
    """发送私信回复，通过 RPA 执行风控扫描后发送，写入消息记录。"""
    conv = await svc.get_conversation_by_id(merchant_id, conversation_id, db)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    content = body.message_content.strip()
    if len(content) > 500:
        raise HTTPException(status_code=422, detail="Message too long")

    success, error = await svc.send_dm_via_rpa(
        merchant_id=merchant_id,
        account_id=conv.account_id,
        xhs_user_id=conv.xhs_user_id,
        content=content,
        db=db,
    )
    if not success:
        raise HTTPException(status_code=500, detail=error or "Failed to send message")

    # 写入消息
    await svc.append_message(
        conversation_id=str(conversation_id),
        role="assistant",
        content=content,
        db=db,
    )
    return BaseResponse(message="Message sent")


@router.post(
    "/conversations/{conversation_id}/takeover",
    response_model=BaseResponse,
)
async def take_over_conversation(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """切换指定会话为人工接管模式，暂停自动回复并触发告警通知商家。"""
    await svc.switch_to_human_takeover(
        merchant_id=merchant_id,
        conversation_id=conversation_id,
        reason="manual_takeover",
        db=db,
    )
    return BaseResponse(message="已切换为人工接管模式")


@router.post(
    "/conversations/{conversation_id}/release",
    response_model=BaseResponse,
)
async def release_conversation(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """解除人工接管，恢复指定会话的自动回复模式。"""
    await svc.release_human_takeover(merchant_id, conversation_id, db)
    return BaseResponse(message="已恢复自动模式")


@router.put(
    "/conversations/{conversation_id}/online-hours",
    response_model=BaseResponse[ConversationResponse],
)
async def update_online_hours(
    conversation_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: OnlineHoursRequest,
) -> BaseResponse[ConversationResponse]:
    """配置会话的在线时段，非在线时段内收到消息时发送延迟回复。"""
    conv = await svc.update_online_hours(
        merchant_id, conversation_id, body, db
    )
    return BaseResponse(data=_to_conversation_response(conv))


# ── HITL 审核 ────────────────────────────────────────────────────────────


@router.get("/hitl/queue", response_model=PaginatedResponse[HITLQueueItemResponse])
async def list_hitl_queue(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    status_filter: str
    | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[HITLQueueItemResponse]:
    """获取 HITL 待审核队列，支持按状态筛选。"""
    items, next_cursor, has_more = await svc.list_hitl_queue(
        merchant_id=merchant_id,
        status=status_filter,
        limit=limit,
        cursor=cursor,
        db=db,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_hitl_item_response(i) for i in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )
    )


@router.post("/hitl/{queue_id}/approve", response_model=BaseResponse)
async def approve_hitl(
    queue_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    reviewer_id: CurrentMerchantId,
    body: HITLApproveRequest,
) -> BaseResponse:
    """审核通过指定的 HITL 条目，使用建议回复或指定回复内容发送。"""
    await svc.approve_hitl(
        merchant_id=merchant_id,
        queue_id=queue_id,
        final_reply=body.final_reply,
        reviewer_id=reviewer_id,
        db=db,
    )
    return BaseResponse(message="审核通过")


@router.post("/hitl/{queue_id}/edit-approve", response_model=BaseResponse)
async def edit_approve_hitl(
    queue_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    reviewer_id: CurrentMerchantId,
    body: HITLEditApproveRequest,
) -> BaseResponse:
    """修改建议回复内容后审核通过，使用修改后的内容发送。"""
    await svc.edit_approve_hitl(
        merchant_id=merchant_id,
        queue_id=queue_id,
        edited_reply=body.edited_reply,
        reviewer_id=reviewer_id,
        db=db,
    )
    return BaseResponse(message="修改后审核通过")


@router.post("/hitl/{queue_id}/reject", response_model=BaseResponse)
async def reject_hitl(
    queue_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    reviewer_id: CurrentMerchantId,
    body: HITLRejectRequest,
) -> BaseResponse:
    """拒绝指定的 HITL 条目，记录拒绝原因，不执行任何发送动作。"""
    await svc.reject_hitl(
        merchant_id=merchant_id,
        queue_id=queue_id,
        reviewer_id=reviewer_id,
        reason=body.reason,
        db=db,
    )
    return BaseResponse(message="已拒绝")


@router.post("/hitl/batch-approve", response_model=BaseResponse)
async def batch_approve_hitl(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    reviewer_id: CurrentMerchantId,
    body: HITLBatchApproveRequest,
) -> BaseResponse:
    """批量审核通过，一次最多处理 20 条，全部使用建议回复发送。"""
    if len(body.queue_ids) > 20:
        raise HTTPException(status_code=422, detail="最多一次审核 20 条")

    for queue_id in body.queue_ids:
        await svc.approve_hitl(
            merchant_id=merchant_id,
            queue_id=queue_id,
            final_reply=None,
            reviewer_id=reviewer_id,
            db=db,
        )
    return BaseResponse(message=f"已通过 {len(body.queue_ids)} 条")
