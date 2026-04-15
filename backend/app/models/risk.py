"""Risk control ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base

risk_keyword_category_enum = Enum(
    "platform_banned",
    "contraband",
    "exaggeration",
    "competitor",
    "custom",
    name="risk_keyword_category_enum",
)

risk_match_mode_enum = Enum(
    "exact",
    "fuzzy",
    name="risk_match_mode_enum",
)

risk_severity_enum = Enum(
    "warn",
    "block",
    name="risk_severity_enum",
)

reply_history_source_type_enum = Enum(
    "comment_reply",
    "dm_send",
    name="reply_history_source_type_enum",
)

operation_type_enum = Enum(
    "note_publish",
    "comment_reply",
    "dm_send",
    "comment_inbound",
    "dm_inbound",
    name="operation_type_enum",
)

operation_status_enum = Enum(
    "success",
    "blocked",
    "rewrite_required",
    "manual_review",
    name="operation_status_enum",
)

alert_severity_enum = Enum(
    "info",
    "warning",
    "critical",
    name="alert_severity_enum",
)


class RiskKeyword(Base):
    """System-level and merchant-level risk keywords."""

    __tablename__ = "risk_keywords"
    __table_args__ = (
        UniqueConstraint(
            "merchant_id",
            "keyword",
            "category",
            name="uq_risk_keyword_scope",
        ),
        Index(
            "ix_risk_keywords_merchant_category_active",
            "merchant_id",
            "category",
            "is_active",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=True
    )
    keyword: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(
        risk_keyword_category_enum,
        nullable=False,
    )
    replacement: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_mode: Mapped[str] = mapped_column(
        risk_match_mode_enum,
        nullable=False,
        server_default=text("'exact'"),
    )
    severity: Mapped[str] = mapped_column(
        risk_severity_enum,
        nullable=False,
        server_default=text("'block'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AccountRiskConfig(Base):
    """Per-account risk control configuration."""

    __tablename__ = "account_risk_configs"
    __table_args__ = (Index("ix_account_risk_configs_merchant_id", "merchant_id"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    rest_windows: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    comment_reply_limit_per_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("20"),
    )
    dm_send_limit_per_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("50"),
    )
    note_publish_limit_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("3"),
    )
    dedup_similarity_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.85"),
    )
    competitor_alert_threshold_per_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("10"),
    )
    # This only applies to ORM-managed updates; raw SQL updates must set it explicitly.
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ReplyHistory(Base):
    """Latest outbound replies for deduplication and similarity checks."""

    __tablename__ = "reply_histories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(
        reply_history_source_type_enum,
        nullable=False,
    )
    source_record_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class OperationLog(Base):
    """Audit trail for outbound and inbound risk-related operations."""

    __tablename__ = "operation_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type: Mapped[str] = mapped_column(
        operation_type_enum,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        operation_status_enum,
        nullable=False,
    )
    content_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Alert(Base):
    """Risk alerts emitted for merchant or account level incidents."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(
        alert_severity_enum,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


Index(
    "ix_reply_histories_account_created_at",
    ReplyHistory.account_id,
    ReplyHistory.created_at.desc(),
)

Index(
    "ix_operation_logs_account_type_created_at",
    OperationLog.account_id,
    OperationLog.operation_type,
    OperationLog.created_at.desc(),
)

Index(
    "ix_alerts_merchant_module_created_at",
    Alert.merchant_id,
    Alert.module,
    Alert.created_at.desc(),
)
