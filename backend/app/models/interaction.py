"""Interaction module ORM models: Comment, Conversation, Message, IntentLog, HITLQueue, DMTriggerLog, MonitoredNote."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.db.session import Base
from sqlalchemy import (
    ARRAY,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

# ── Enum 定义 ──

reply_status_enum = Enum(
    "pending",
    "replied",
    "manual_review",
    "skipped",
    name="reply_status_enum",
)

conversation_mode_enum = Enum(
    "auto",
    "human_takeover",
    "pending",
    name="conversation_mode_enum",
)

message_role_enum = Enum(
    "user",
    "assistant",
    name="message_role_enum",
)

hitl_source_type_enum = Enum(
    "comment",
    "message",
    name="hitl_source_type_enum",
)

hitl_trigger_reason_enum = Enum(
    "low_confidence",
    "complaint",
    "competitor_mention",
    "high_value_bd",
    "strong_negative",
    "captcha_detected",
    name="hitl_trigger_reason_enum",
)

hitl_status_enum = Enum(
    "pending",
    "approved",
    "rejected",
    "edited",
    name="hitl_status_enum",
)


# ── Comment ──


class Comment(Base):
    """评论记录表。存储通过 Playwright RPA 检测到的笔记评论。"""

    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("xhs_comment_id", name="uq_xhs_comment_id"),
        Index("ix_comments_merchant_status_created", "merchant_id", "reply_status", "created_at".desc()),
        Index("ix_comments_account_note_created", "account_id", "xhs_note_id", "created_at".desc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    xhs_note_id: Mapped[str] = mapped_column(String(64), nullable=False)
    xhs_comment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    xhs_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    ocr_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reply_status: Mapped[str] = mapped_column(
        reply_status_enum,
        nullable=False,
        server_default=text("'pending'"),
    )
    deduplicated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    detected_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── Conversation ──


class Conversation(Base):
    """私信会话表。每个商家账号与每个用户之间最多一条会话。"""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("account_id", "xhs_user_id", name="uq_account_xhs_user"),
        Index("ix_conversations_merchant_mode_updated", "merchant_id", "mode", "last_message_at".desc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    xhs_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(
        conversation_mode_enum,
        nullable=False,
        server_default=text("'auto'"),
    )
    user_long_term_memory: Mapped[dict | None] = mapped_column(nullable=True)
    online_hours_start: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    online_hours_end: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── Message ──


class Message(Base):
    """消息记录表。存储会话中的每条消息（用户发/助手回）。"""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_sent_at", "conversation_id", "sent_at".desc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    xhs_msg_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        message_role_enum,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── IntentLog ──


class IntentLog(Base):
    """意图识别日志。记录每次意图分类的原始输入和结果。"""

    __tablename__ = "intent_logs"
    __table_args__ = (
        Index("ix_intent_logs_merchant_created", "merchant_id", "created_at".desc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        hitl_source_type_enum,
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False
    )
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── HITLQueue ──


class HITLQueue(Base):
    """HITL 待审核队列。触发人工审核的条目进入此队列。"""

    __tablename__ = "hitl_queue"
    __table_args__ = (
        Index("ix_hitl_queue_merchant_status_created", "merchant_id", "status", "created_at".desc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    comment_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_reason: Mapped[str] = mapped_column(
        hitl_trigger_reason_enum,
        nullable=False,
    )
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        hitl_status_enum,
        nullable=False,
        server_default=text("'pending'"),
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── DMTriggerLog ──


class DMTriggerLog(Base):
    """私信触发去重日志。记录已触发的私信，用于 24h 内相同意图去重。"""

    __tablename__ = "dm_trigger_logs"
    __table_args__ = (
        Index("ix_dm_trigger_logs_merchant_user_intent_expires", "merchant_id", "xhs_user_id", "intent", "expires_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    xhs_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    xhs_comment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )


# ── MonitoredNote ──


class MonitoredNote(Base):
    """监测笔记配置。商家选择需要监测的笔记列表。"""

    __tablename__ = "monitored_notes"
    __table_args__ = (
        UniqueConstraint("account_id", "xhs_note_id", name="uq_account_xhs_note"),
        Index("ix_monitored_notes_account_active_checked", "account_id", "is_active", "last_checked_at".asc()),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    xhs_note_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note_title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    check_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("60"),
    )
    batch_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("3"),
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_known_comment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
