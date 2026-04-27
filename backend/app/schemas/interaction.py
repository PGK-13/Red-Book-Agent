"""Interaction module request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── 枚举类型 ──────────────────────────────────────────────────────────────

CommentIntent = Literal[
    "ask_price",
    "complaint",
    "ask_link",
    "general_inquiry",
    "competitor_mention",
    "other",
]

DMIntent = Literal[
    "ask_price",
    "ask_link",
    "purchase_intent",
    "complaint",
    "high_value_bd",
    "general_inquiry",
    "other",
]

ReplyStatus = Literal["pending", "replied", "manual_review", "skipped"]

ConversationMode = Literal["auto", "human_takeover", "pending"]

HITLTriggerReason = Literal[
    "low_confidence",
    "complaint",
    "competitor_mention",
    "high_value_bd",
    "strong_negative",
    "captcha_detected",
]

HITLStatus = Literal["pending", "approved", "rejected", "edited"]


# ── MonitoredNote 相关 ────────────────────────────────────────────────────


class MonitoredNoteCreateRequest(BaseModel):
    """商家添加需要监测的笔记。"""

    account_id: UUID
    xhs_note_id: str = Field(..., max_length=64)
    note_title: str = Field(..., max_length=256)
    check_interval_seconds: int = Field(default=60, ge=30, le=300)
    batch_size: int = Field(default=3, ge=1, le=10)


class MonitoredNoteUpdateRequest(BaseModel):
    """更新监测笔记配置。"""

    is_active: bool | None = None
    check_interval_seconds: int | None = Field(None, ge=30, le=300)
    batch_size: int | None = Field(None, ge=1, le=10)


class MonitoredNoteResponse(BaseModel):
    """监测笔记响应。"""

    id: UUID
    account_id: UUID
    xhs_note_id: str
    note_title: str
    is_active: bool
    check_interval_seconds: int
    batch_size: int
    last_checked_at: datetime | None
    last_known_comment_count: int
    last_seen_comment_id: str | None
    created_at: datetime


# ── Comment 相关 ──────────────────────────────────────────────────────────


class CommentIntentRequest(BaseModel):
    """手动触发评论意图分类请求。"""

    comment_id: UUID


class CommentIntentResponse(BaseModel):
    """评论意图分类响应。"""

    comment_id: UUID
    intent: CommentIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    ocr_result: str | None = None
    needs_human_review: bool


class CommentReplyRequest(BaseModel):
    """发送评论回复请求。"""

    comment_id: UUID
    reply_content: str = Field(..., min_length=15, max_length=80)
    force: bool = False

    @field_validator("reply_content")
    @classmethod
    def strip_reply(cls, v: str) -> str:
        return v.strip()


class CommentResponse(BaseModel):
    """评论响应。"""

    id: UUID
    account_id: UUID
    xhs_note_id: str
    xhs_comment_id: str
    xhs_user_id: str
    content: str
    image_urls: list[str]
    ocr_result: str | None
    intent: str | None
    intent_confidence: float | None
    sentiment_score: float | None
    reply_status: ReplyStatus
    deduplicated: bool
    detected_at: datetime | None
    created_at: datetime


class CommentListRequest(BaseModel):
    """评论列表查询请求。"""

    account_id: UUID | None = None
    xhs_note_id: str | None = None
    reply_status: ReplyStatus | None = None
    intent: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = Field(default=20, le=100)
    cursor: str | None = None


# ── Conversation / DM 相关 ────────────────────────────────────────────────


class DMReplyRequest(BaseModel):
    """发送私信回复请求。"""

    conversation_id: UUID
    message_content: str = Field(..., min_length=1, max_length=500)
    force: bool = False

    @field_validator("message_content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v.strip()


class ConversationModeRequest(BaseModel):
    """切换会话模式请求。"""

    mode: ConversationMode


class ConversationResponse(BaseModel):
    """会话响应。"""

    id: UUID
    account_id: UUID
    xhs_user_id: str
    mode: ConversationMode
    user_long_term_memory: dict | None
    online_hours_start: datetime | None
    online_hours_end: datetime | None
    last_message_at: datetime | None
    created_at: datetime


class ConversationListRequest(BaseModel):
    """会话列表查询请求。"""

    account_id: UUID | None = None
    mode: ConversationMode | None = None
    limit: int = Field(default=20, le=100)
    cursor: str | None = None


class MessageResponse(BaseModel):
    """消息响应。"""

    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    intent: str | None
    intent_confidence: float | None
    sentiment_score: float | None
    sent_at: datetime


class MessageListRequest(BaseModel):
    """消息列表查询请求。"""

    conversation_id: UUID
    limit: int = Field(default=20, le=100)
    cursor: str | None = None


class OnlineHoursRequest(BaseModel):
    """配置在线时段请求。"""

    online_hours_start: str | None = Field(
        None, description="格式 HH:MM，如 09:00"
    )
    online_hours_end: str | None = Field(
        None, description="格式 HH:MM，如 18:00"
    )


# ── HITL 审核相关 ────────────────────────────────────────────────────────


class HITLApproveRequest(BaseModel):
    """审核通过请求。"""

    queue_id: UUID
    final_reply: str | None = None


class HITLEditApproveRequest(BaseModel):
    """修改后审核通过请求。"""

    queue_id: UUID
    edited_reply: str = Field(..., min_length=1, max_length=500)


class HITLRejectRequest(BaseModel):
    """审核拒绝请求。"""

    queue_id: UUID
    reason: str | None = None


class HITLBatchApproveRequest(BaseModel):
    """批量审核通过请求。"""

    queue_ids: list[UUID] = Field(..., min_length=1, max_length=20)


class HITLQueueItemResponse(BaseModel):
    """HITL 队列项响应。"""

    id: UUID
    trigger_reason: HITLTriggerReason
    original_content: str
    suggested_reply: str | None
    conversation_id: UUID | None
    comment_id: UUID | None
    status: HITLStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime


# ── IntentLog 相关 ────────────────────────────────────────────────────────


class IntentLogResponse(BaseModel):
    """意图识别日志响应。"""

    id: UUID
    source_type: Literal["comment", "message"]
    source_id: UUID
    raw_input: str
    intent: str
    confidence: float
    sentiment_score: float
    llm_latency_ms: int | None
    created_at: datetime
